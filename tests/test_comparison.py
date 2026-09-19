"""Tests for the X-band comparison case and the --compare report.

The headline assertion is the one CLAUDE.md pins for the comparison: at equal
slant range, X-band pays 11.43 dB more free-space path loss than S-band. That
number is the whole reason the comparison exists -- it is the price of the band,
before anything is bought back with a bigger antenna or more power -- so it is
tested against the scenario files rather than against hand-typed frequencies.

The rest covers the X-band scenario loading correctly and the side-by-side
report: that every delta really is other minus base, and that a value missing on
either side produces "n/a" rather than a subtraction against nothing.
"""

from pathlib import Path

import pytest

import link_budget as lb
import run
from scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
S_BAND_YAML = REPO_ROOT / "scenarios" / "s_band_ttc.yaml"
X_BAND_YAML = REPO_ROOT / "scenarios" / "x_band_payload.yaml"


@pytest.fixture
def s_band():
    return load_scenario(S_BAND_YAML)


@pytest.fixture
def x_band():
    return load_scenario(X_BAND_YAML)


# ---------------------------------------------------------------------------
# The X-band scenario file
# ---------------------------------------------------------------------------
def test_x_band_scenario_field_values(x_band):
    """Every field of scenarios/x_band_payload.yaml, against the spec."""
    assert x_band.name == "X-band payload downlink, 500 km, 10 deg elevation"
    assert x_band.altitude_km == pytest.approx(500.0)
    assert x_band.elevation_deg == pytest.approx(10.0)
    assert x_band.freq_mhz == pytest.approx(8200.0)
    assert x_band.p_tx_dbw == pytest.approx(7.0)
    assert x_band.g_tx_dbi == pytest.approx(6.0)
    assert x_band.l_tx_db == pytest.approx(1.5)
    assert x_band.other_losses_db == pytest.approx(3.0)
    assert x_band.rx_dish_diameter_m == pytest.approx(3.0)
    assert x_band.rx_efficiency == pytest.approx(0.6)
    assert x_band.t_ant_k == pytest.approx(60.0)
    assert x_band.lna_nf_db == pytest.approx(1.5)
    assert x_band.g_over_t_db_per_k is None
    assert x_band.bit_rate_bps == pytest.approx(50.0e6)
    assert x_band.bits_per_symbol == 2
    assert x_band.code_rate == pytest.approx(0.75)
    assert x_band.required_ebn0_db == pytest.approx(2.3)
    assert x_band.implementation_loss_db == pytest.approx(1.5)
    assert x_band.target_margin_db == pytest.approx(3.0)


def test_x_band_bit_rate_survives_the_yaml_1_1_exponent_form(x_band):
    """50.0e6 is another unsigned exponent, so it too arrives as a string."""
    assert isinstance(x_band.bit_rate_bps, float)
    assert x_band.bit_rate_bps == pytest.approx(5.0e7)


def test_x_band_required_ebn0_matches_the_dvb_s2_operating_point(x_band):
    """The file's comment derives 2.3 dB from Es/N0 4.03 dB at QPSK rate 3/4."""
    ebn0 = lb.ebn0_from_esn0_db(4.03, x_band.bits_per_symbol, x_band.code_rate)

    assert ebn0 == pytest.approx(2.27, abs=0.01)
    assert x_band.required_ebn0_db == pytest.approx(2.3, abs=0.05)


# ---------------------------------------------------------------------------
# The band's price: the 11.43 dB figure
# ---------------------------------------------------------------------------
def test_the_two_cases_share_a_slant_range(s_band, x_band):
    """The 11.43 dB claim is "at equal range", so that premise is checked first."""
    assert s_band.altitude_km == pytest.approx(x_band.altitude_km)
    assert s_band.elevation_deg == pytest.approx(x_band.elevation_deg)

    s_range = lb.compute_ledger(s_band)["slant_range_km"]
    x_range = lb.compute_ledger(x_band)["slant_range_km"]
    assert x_range == pytest.approx(s_range, rel=1e-12)


def test_x_band_fspl_exceeds_s_band_by_11_43_db(s_band, x_band):
    """Spec: at equal slant range, X-band FSPL exceeds S-band by 11.43 dB (+/-0.05)."""
    s_fspl = lb.compute_ledger(s_band)["fspl_db"]
    x_fspl = lb.compute_ledger(x_band)["fspl_db"]

    assert x_fspl - s_fspl == pytest.approx(11.43, abs=0.05)


def test_the_fspl_penalty_is_the_frequency_ratio(s_band, x_band):
    """The penalty is 20log10(f_X / f_S) and nothing else -- range cancels."""
    expected_db = 20.0 * lb.np.log10(x_band.freq_mhz / s_band.freq_mhz)
    s_fspl = lb.compute_ledger(s_band)["fspl_db"]
    x_fspl = lb.compute_ledger(x_band)["fspl_db"]

    assert x_fspl - s_fspl == pytest.approx(expected_db, abs=1e-9)


def test_the_dish_buys_back_exactly_what_the_band_costs(s_band, x_band):
    """The same 3 m dish gains 11.43 dB at X-band, cancelling the path-loss penalty.

    Gain goes as f^2 and path loss as f^2, so for a fixed physical aperture the
    two move together. What actually makes the X-band case tight is the higher
    bit rate, not the frequency.
    """
    s_led = lb.compute_ledger(s_band)
    x_led = lb.compute_ledger(x_band)

    fspl_penalty = x_led["fspl_db"] - s_led["fspl_db"]
    gain_gained = x_led["g_rx_dbi"] - s_led["g_rx_dbi"]

    assert gain_gained == pytest.approx(fspl_penalty, abs=1e-9)


def test_x_band_margin_is_deliberately_tight(x_band):
    """Spec: the X-band case lands around 4.5 dB of margin."""
    assert lb.compute_ledger(x_band)["margin_db"] == pytest.approx(4.5, abs=0.2)


# ---------------------------------------------------------------------------
# format_delta()
# ---------------------------------------------------------------------------
def test_format_delta_signs_the_difference():
    assert run.format_delta(163.88, 175.31, "db") == "+11.43"
    assert run.format_delta(175.31, 163.88, "db") == "-11.43"


def test_format_delta_is_other_minus_base():
    assert run.format_delta(10.0, 4.0, "db") == "-6.00"


def test_format_delta_uses_each_kinds_rounding():
    assert run.format_delta(1694.6, 1700.0, "km") == "+5.4"
    assert run.format_delta(150.1, 179.6, "kelvin") == "+29.5"
    assert run.format_delta(2.0e6, 5.0e7, "rate") == "+4.8e+07"


def test_format_delta_reports_n_a_when_either_side_is_missing():
    """A published G/T leaves no gain or temperature to subtract."""
    assert run.format_delta(None, 34.58, "db") == "n/a"
    assert run.format_delta(34.58, None, "db") == "n/a"
    assert run.format_delta(None, None, "db") == "n/a"


# ---------------------------------------------------------------------------
# format_comparison()
# ---------------------------------------------------------------------------
@pytest.fixture
def comparison(s_band, x_band):
    return run.format_comparison(lb.compute_ledger(s_band), s_band.name,
                                 lb.compute_ledger(x_band), x_band.name)


def test_comparison_names_both_scenarios(comparison, s_band, x_band):
    assert s_band.name in comparison
    assert x_band.name in comparison


def test_comparison_has_the_three_columns(comparison):
    assert "base" in comparison
    assert "other" in comparison
    assert "delta" in comparison
    assert "delta is other minus base" in comparison


def test_comparison_shows_the_band_penalty(comparison):
    """The 11.43 dB figure must be visible in the delta column."""
    fspl_line = next(line for line in comparison.splitlines()
                     if "Free-space path loss" in line)

    assert "163.88" in fspl_line
    assert "175.31" in fspl_line
    assert "+11.43" in fspl_line


def test_comparison_covers_every_ledger_row(comparison):
    """No line may be dropped when two ledgers are shown together."""
    for group in run.LEDGER_DISPLAY:
        for _, label, _, _ in group:
            assert label in comparison


def test_every_delta_equals_other_minus_base(s_band, x_band):
    """Checked against the ledgers themselves, not against the rendered text."""
    base = lb.compute_ledger(s_band)
    other = lb.compute_ledger(x_band)

    for group in run.LEDGER_DISPLAY:
        for key, label, _, kind in group:
            expected = run._DELTA_FORMATS[kind].format(other[key] - base[key])
            assert run.format_delta(base[key], other[key], kind) == expected, label


def test_comparison_handles_a_published_g_over_t(s_band, x_band):
    """One side with a published G/T leaves two rows as n/a, not a bogus delta."""
    from dataclasses import replace

    report = run.format_comparison(
        lb.compute_ledger(s_band), s_band.name,
        lb.compute_ledger(replace(x_band, g_over_t_db_per_k=20.0)), x_band.name)
    gain_line = next(line for line in report.splitlines()
                     if "Receive antenna gain" in line)

    assert "n/a" in gain_line


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------
def test_compare_flag_prints_the_comparison(capsys):
    exit_code = run.main([str(S_BAND_YAML), "--compare", str(X_BAND_YAML)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "base" in captured.out
    assert "delta is other minus base" in captured.out
    assert "+11.43" in captured.out


def test_compare_flag_replaces_the_single_ledger(capsys):
    """With --compare the report is the comparison, not a table plus a table."""
    run.main([str(S_BAND_YAML), "--compare", str(X_BAND_YAML)])
    captured = capsys.readouterr()

    assert captured.out.count("Free-space path loss") == 1


def test_compare_reports_a_bad_other_file(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("altitude_km: 500.0\n", encoding="utf-8")

    exit_code = run.main([str(S_BAND_YAML), "--compare", str(bad)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "missing key" in captured.err.lower()


def test_compare_reports_a_missing_other_file(tmp_path, capsys):
    exit_code = run.main([str(S_BAND_YAML), "--compare", str(tmp_path / "nope.yaml")])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.err != ""
