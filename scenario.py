"""Scenario definition and YAML loading for the link budget.

This module holds the frozen ``Scenario`` dataclass -- the complete set of inputs
one link case needs, in the order given by the spec: name, geometry, transmitter,
path losses, receiver, and the data and modem terms. Alongside it lives
``load_scenario(path)``, which parses a YAML file from ``scenarios/`` into that
dataclass and raises ``ValueError`` naming any key that is unknown or missing, so
a malformed scenario fails loudly at load time rather than silently producing a
plausible-looking ledger. Values are coerced to the declared field types on the
way in, which matters more than it looks: PyYAML follows YAML 1.1, where an
exponent must carry an explicit sign, so ``2.0e6`` arrives as the string
``'2.0e6'`` rather than a float.
"""

from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Scenario:
    """One fully specified link case: every input the ledger needs, and nothing else.

    Frozen because a scenario is a statement of fact about a link, not a mutable
    working value; the sweeps derive new scenarios rather than editing one in
    place. Field order matches the Scenario schema in CLAUDE.md and the order of
    the worked example YAML.

    Attributes:
        name:                   human-readable label for the case.
        altitude_km:            orbit altitude above mean Earth surface [km].
        elevation_deg:          satellite elevation above local horizon [deg].
        freq_mhz:               carrier frequency [MHz].
        p_tx_dbw:               transmitter output power [dBW].
        g_tx_dbi:               transmit antenna boresight gain [dBi].
        l_tx_db:                transmitter-to-antenna losses [dB, positive].
        other_losses_db:        atmosphere, polarization, pointing, misc [dB, positive].
        rx_dish_diameter_m:     ground station reflector diameter [m].
        rx_efficiency:          ground station aperture efficiency [0..1].
        t_ant_k:                antenna noise temperature [K].
        lna_nf_db:              low-noise amplifier noise figure [dB].
        g_over_t_db_per_k:      published station figure of merit [dB/K], or None
                                to compute it from the dish and noise terms above.
        bit_rate_bps:           information bit rate [bit/s].
        bits_per_symbol:        channel bits per modulation symbol [dimensionless].
        code_rate:              information bits per channel bit [0..1].
        required_ebn0_db:       threshold Eb/N0 [dB, per information bit].
        implementation_loss_db: modem shortfall against theory [dB, positive].
        target_margin_db:       margin held in reserve by the max-rate solver [dB].
    """

    name: str
    altitude_km: float
    elevation_deg: float
    freq_mhz: float
    p_tx_dbw: float
    g_tx_dbi: float
    l_tx_db: float
    other_losses_db: float
    rx_dish_diameter_m: float
    rx_efficiency: float
    t_ant_k: float
    lna_nf_db: float
    g_over_t_db_per_k: float | None
    bit_rate_bps: float
    bits_per_symbol: int
    code_rate: float
    required_ebn0_db: float
    implementation_loss_db: float
    target_margin_db: float


# Fields whose value may legitimately be null in YAML. g_over_t_db_per_k is null
# whenever the station's figure of merit is to be computed from the dish diameter,
# efficiency and noise temperatures rather than taken from an operator's datasheet.
_NULLABLE_FIELDS = frozenset({"g_over_t_db_per_k"})

# The one field that is text, and the one that counts whole bits. Everything else
# is a float, so the coercion below only needs these two exceptions.
_STR_FIELDS = frozenset({"name"})
_INT_FIELDS = frozenset({"bits_per_symbol"})


def _coerce_field(field_name, raw_value):
    """Convert one raw YAML value to the type the Scenario field declares.

    Coercion is not cosmetic. PyYAML implements YAML 1.1, whose float resolver
    requires a signed exponent, so the spec's ``bit_rate_bps: 2.0e6`` is handed
    over as the string ``'2.0e6'``. Without this step that string would be stored
    in a field annotated ``float`` -- dataclasses do not check types at runtime --
    and would fail much later, inside a log10, with an error naming neither the
    key nor the file.

    Args:
        field_name: the Scenario field being filled [str].
        raw_value:  whatever PyYAML produced for that key.
    Returns:
        the value converted to the field's declared type.
    Raises:
        ValueError: naming the field, if the value cannot be converted.
    """
    if raw_value is None:
        if field_name in _NULLABLE_FIELDS:
            return None                                   # a genuine "not published"
        raise ValueError(f"scenario key {field_name!r} must not be null")

    try:
        if field_name in _STR_FIELDS:
            return str(raw_value)
        if field_name in _INT_FIELDS:
            return int(raw_value)
        return float(raw_value)                           # every remaining field is a float
    except (TypeError, ValueError):
        raise ValueError(
            f"scenario key {field_name!r} has value {raw_value!r}, "
            f"which cannot be read as a number"
        ) from None


def load_scenario(path):
    """Read a scenario YAML file into a :class:`Scenario`.

    Every key in the schema must be present and no others may appear. Both
    failures raise ValueError naming the offending keys, because the usual way to
    get a wrong link budget is not a wrong formula but a typo in an input file
    that silently leaves a term at its default.

    Args:
        path: path to a scenario YAML file [str or pathlib.Path].
    Returns:
        a frozen :class:`Scenario` with every field coerced to its declared type.
    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the file is not a YAML mapping, if any key is unknown or
            missing, or if any value cannot be read as its declared type. The
            message names the keys at fault.
    Reference:
        load_scenario("scenarios/s_band_ttc.yaml").bit_rate_bps == 2.0e6
    """
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping of scenario keys, "
                         f"got {type(raw).__name__}")

    expected_names = [field.name for field in fields(Scenario)]

    # Report both failure modes together: fixing a typo one run at a time is
    # tedious, and a misspelling usually shows up as one unknown plus one missing.
    unknown = [key for key in raw if key not in expected_names]
    missing = [name for name in expected_names if name not in raw]
    if unknown or missing:
        problems = []
        if unknown:
            problems.append("unknown key(s): " + ", ".join(repr(k) for k in sorted(unknown)))
        if missing:
            problems.append("missing key(s): " + ", ".join(repr(k) for k in missing))
        raise ValueError(f"{path}: " + "; ".join(problems))

    values = {name: _coerce_field(name, raw[name]) for name in expected_names}
    return Scenario(**values)
