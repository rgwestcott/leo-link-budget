"""Tests for the Scenario dataclass and the YAML loader.

The loader's job is to fail loudly on a malformed input file, because a typo in a
scenario is the likeliest way to get a confidently wrong link budget: a wrong
formula announces itself, a key silently left at a stale value does not. These
tests cover the worked example loading correctly, and both failure modes the spec
requires -- an unknown key and a missing one.
"""

from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest
import yaml

import link_budget as lb
from scenario import Scenario, load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
S_BAND_YAML = REPO_ROOT / "scenarios" / "s_band_ttc.yaml"

# The schema exactly as the Scenario section of CLAUDE.md gives it, in order.
EXPECTED_FIELD_ORDER = [
    "name",
    "altitude_km",
    "elevation_deg",
    "freq_mhz",
    "p_tx_dbw",
    "g_tx_dbi",
    "l_tx_db",
    "other_losses_db",
    "rx_dish_diameter_m",
    "rx_efficiency",
    "t_ant_k",
    "lna_nf_db",
    "g_over_t_db_per_k",
    "bit_rate_bps",
    "bits_per_symbol",
    "code_rate",
    "required_ebn0_db",
    "implementation_loss_db",
    "target_margin_db",
]


@pytest.fixture
def raw_s_band():
    """The worked example parsed straight from YAML, for mutating into bad copies."""
    with S_BAND_YAML.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_scenario(tmp_path, mapping, filename="case.yaml"):
    """Write a scenario mapping to a temporary YAML file and return its path."""
    path = tmp_path / filename
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(mapping, handle, sort_keys=False)
    return path


# ---------------------------------------------------------------------------
# The dataclass itself
# ---------------------------------------------------------------------------
def test_field_names_and_order_match_the_spec():
    """The spec fixes both the key names and their order."""
    assert [field.name for field in fields(Scenario)] == EXPECTED_FIELD_ORDER


def test_scenario_is_frozen():
    """A scenario states a fact about a link; sweeps derive new ones rather than edit."""
    case = load_scenario(S_BAND_YAML)
    with pytest.raises(FrozenInstanceError):
        case.altitude_km = 600.0


# ---------------------------------------------------------------------------
# Loading the worked example
# ---------------------------------------------------------------------------
def test_load_s_band_ttc_field_values():
    """Every field of scenarios/s_band_ttc.yaml, against the spec's worked example."""
    case = load_scenario(S_BAND_YAML)

    assert case.name == "S-band TT&C downlink, 500 km, 10 deg elevation"
    assert case.altitude_km == pytest.approx(500.0)
    assert case.elevation_deg == pytest.approx(10.0)
    assert case.freq_mhz == pytest.approx(2200.0)
    assert case.p_tx_dbw == pytest.approx(0.0)
    assert case.g_tx_dbi == pytest.approx(3.0)
    assert case.l_tx_db == pytest.approx(1.0)
    assert case.other_losses_db == pytest.approx(2.0)
    assert case.rx_dish_diameter_m == pytest.approx(3.0)
    assert case.rx_efficiency == pytest.approx(0.6)
    assert case.t_ant_k == pytest.approx(75.0)
    assert case.lna_nf_db == pytest.approx(1.0)
    assert case.g_over_t_db_per_k is None
    assert case.bit_rate_bps == pytest.approx(2.0e6)
    assert case.bits_per_symbol == 2
    assert case.code_rate == pytest.approx(0.5)
    assert case.required_ebn0_db == pytest.approx(1.5)
    assert case.implementation_loss_db == pytest.approx(1.5)
    assert case.target_margin_db == pytest.approx(3.0)


def test_load_s_band_ttc_field_types():
    """Declared types must actually hold: float everywhere but name and bits_per_symbol."""
    case = load_scenario(S_BAND_YAML)

    assert isinstance(case.name, str)
    assert isinstance(case.bits_per_symbol, int)
    assert case.g_over_t_db_per_k is None

    float_fields = [name for name in EXPECTED_FIELD_ORDER
                    if name not in ("name", "bits_per_symbol", "g_over_t_db_per_k")]
    for name in float_fields:
        assert isinstance(getattr(case, name), float), f"{name} is not a float"


def test_bit_rate_survives_yaml_1_1_exponent_form():
    """bit_rate_bps must be a number, not the string PyYAML hands over.

    PyYAML implements YAML 1.1, whose float resolver requires a signed exponent,
    so the spec's literal "2.0e6" parses as the str '2.0e6'. The loader coerces
    it; without that, the value would reach a log10 as text.
    """
    with S_BAND_YAML.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    assert isinstance(raw["bit_rate_bps"], str)           # the quirk, pinned

    case = load_scenario(S_BAND_YAML)
    assert isinstance(case.bit_rate_bps, float)
    assert case.bit_rate_bps == pytest.approx(2.0e6)


def test_loaded_scenario_feeds_the_physics():
    """The loaded values reproduce the worked example's C/N0 and margin."""
    case = load_scenario(S_BAND_YAML)

    eirp = lb.eirp_dbw(case.p_tx_dbw, case.g_tx_dbi, case.l_tx_db)
    path_loss = lb.fspl_db(lb.slant_range_km(case.altitude_km, case.elevation_deg),
                           case.freq_mhz)
    g_rx = lb.dish_gain_dbi(case.rx_dish_diameter_m, case.freq_mhz, case.rx_efficiency)
    t_sys = lb.system_noise_temp_k(case.t_ant_k, lb.receiver_noise_temp_k(case.lna_nf_db))
    cn0 = lb.cn0_dbhz(eirp, path_loss, case.other_losses_db,
                      lb.g_over_t_db_per_k(g_rx, t_sys))
    ebn0 = lb.ebn0_db(cn0, case.bit_rate_bps)

    assert cn0 == pytest.approx(77.54, abs=0.1)
    assert ebn0 == pytest.approx(14.53, abs=0.1)
    assert lb.margin_db(ebn0, case.required_ebn0_db,
                        case.implementation_loss_db) == pytest.approx(11.53, abs=0.1)


def test_load_scenario_accepts_a_string_path():
    """Paths arrive from argparse as strings."""
    assert load_scenario(str(S_BAND_YAML)).freq_mhz == pytest.approx(2200.0)


# ---------------------------------------------------------------------------
# Failure: an unknown key
# ---------------------------------------------------------------------------
def test_misspelled_key_raises_value_error(tmp_path, raw_s_band):
    """A misspelled key must raise, not be silently ignored."""
    raw_s_band["altitude_kms"] = raw_s_band.pop("altitude_km")   # the classic typo
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError):
        load_scenario(path)


def test_misspelled_key_error_names_both_the_typo_and_the_gap(tmp_path, raw_s_band):
    """A misspelling is one unknown key plus one missing key; the message says both.

    Naming only one of the two would send the reader looking in the wrong place.
    """
    raw_s_band["altitude_kms"] = raw_s_band.pop("altitude_km")
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError) as excinfo:
        load_scenario(path)

    message = str(excinfo.value)
    assert "altitude_kms" in message
    assert "altitude_km" in message
    assert "unknown" in message.lower()
    assert "missing" in message.lower()


def test_extra_unknown_key_raises(tmp_path, raw_s_band):
    """An added key that no field matches is an error, even with nothing missing."""
    raw_s_band["rain_margin_db"] = 1.0
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError, match="rain_margin_db"):
        load_scenario(path)


# ---------------------------------------------------------------------------
# Failure: a missing key
# ---------------------------------------------------------------------------
def test_missing_key_raises_value_error(tmp_path, raw_s_band):
    """A dropped key must raise rather than fall back to a default."""
    del raw_s_band["required_ebn0_db"]
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError, match="required_ebn0_db"):
        load_scenario(path)


@pytest.mark.parametrize("dropped", EXPECTED_FIELD_ORDER)
def test_every_field_is_required(tmp_path, raw_s_band, dropped):
    """No field may be omitted -- checked one at a time across the whole schema."""
    del raw_s_band[dropped]
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError, match=dropped):
        load_scenario(path)


def test_missing_key_message_lists_all_gaps(tmp_path, raw_s_band):
    """Several missing keys are reported together, not one run at a time."""
    for name in ("t_ant_k", "lna_nf_db", "code_rate"):
        del raw_s_band[name]
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError) as excinfo:
        load_scenario(path)

    message = str(excinfo.value)
    for name in ("t_ant_k", "lna_nf_db", "code_rate"):
        assert name in message


# ---------------------------------------------------------------------------
# Failure: bad values
# ---------------------------------------------------------------------------
def test_null_in_a_non_nullable_field_raises(tmp_path, raw_s_band):
    """Only g_over_t_db_per_k may be null; a null elsewhere is a mistake."""
    raw_s_band["t_ant_k"] = None
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError, match="t_ant_k"):
        load_scenario(path)


def test_non_numeric_value_raises_naming_the_key(tmp_path, raw_s_band):
    raw_s_band["altitude_km"] = "five hundred"
    path = write_scenario(tmp_path, raw_s_band)

    with pytest.raises(ValueError, match="altitude_km"):
        load_scenario(path)


def test_published_g_over_t_is_accepted(tmp_path, raw_s_band):
    """A non-null G/T is the operator-published override, and must load as a float."""
    raw_s_band["g_over_t_db_per_k"] = 12.82
    path = write_scenario(tmp_path, raw_s_band)

    case = load_scenario(path)
    assert isinstance(case.g_over_t_db_per_k, float)
    assert case.g_over_t_db_per_k == pytest.approx(12.82)


def test_non_mapping_yaml_raises(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- not\n- a mapping\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_scenario(path)


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_scenario(tmp_path / "does_not_exist.yaml")
