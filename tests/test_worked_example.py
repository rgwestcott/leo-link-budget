"""End-to-end test of the worked example, from scenario file to printed ledger.

CLAUDE.md pins the S-band TT&C case at C/N0 77.5 dB-Hz, Eb/N0 14.5 dB and margin
11.5 dB, each within 0.1 dB. Those three assertions are the point of this file:
every function can be individually correct and the budget still wrong if the
chain is wired up in the wrong order or a term is used twice. The remaining tests
cover the ledger's contract -- its key order, the published-G/T branch -- and the
CLI's display rounding.
"""

from pathlib import Path

import pytest

import link_budget as lb
import run
from scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
S_BAND_YAML = REPO_ROOT / "scenarios" / "s_band_ttc.yaml"


@pytest.fixture
def s_band_ledger():
    return lb.compute_ledger(load_scenario(S_BAND_YAML))


# ---------------------------------------------------------------------------
# The three numbers the spec pins
# ---------------------------------------------------------------------------
def test_worked_example_cn0(s_band_ledger):
    """Spec: the S-band scenario gives C/N0 = 77.5 dB-Hz (+/-0.1)."""
    assert s_band_ledger["cn0_dbhz"] == pytest.approx(77.5, abs=0.1)


def test_worked_example_ebn0(s_band_ledger):
    """Spec: the S-band scenario gives Eb/N0 = 14.5 dB (+/-0.1)."""
    assert s_band_ledger["ebn0_db"] == pytest.approx(14.5, abs=0.1)


def test_worked_example_margin(s_band_ledger):
    """Spec: the S-band scenario gives margin = 11.5 dB (+/-0.1)."""
    assert s_band_ledger["margin_db"] == pytest.approx(11.5, abs=0.1)


# ---------------------------------------------------------------------------
# The rest of the expected ledger
# ---------------------------------------------------------------------------
def test_worked_example_full_ledger(s_band_ledger):
    """Every line of the expected ledger quoted in CLAUDE.md's worked example."""
    assert s_band_ledger["eirp_dbw"] == pytest.approx(2.0, abs=0.01)
    assert s_band_ledger["slant_range_km"] == pytest.approx(1694.6, abs=1.0)
    assert s_band_ledger["fspl_db"] == pytest.approx(163.88, abs=0.05)
    assert s_band_ledger["g_rx_dbi"] == pytest.approx(34.58, abs=0.05)
    assert s_band_ledger["t_sys_k"] == pytest.approx(150.1, abs=0.05)
    assert s_band_ledger["g_over_t_db_per_k"] == pytest.approx(12.82, abs=0.05)
    assert s_band_ledger["ebn0_required_total_db"] == pytest.approx(3.0, abs=0.01)
    assert s_band_ledger["max_bit_rate_bps_at_target_margin"] == pytest.approx(
        1.43e7, rel=0.02)


def test_boltzmann_line_is_the_negated_constant(s_band_ledger):
    """The ledger's k line is the negation of the computed constant, not a literal."""
    assert s_band_ledger["minus_10log_k_dbw_per_k_hz"] == pytest.approx(
        -lb.BOLTZMANN_DBW_PER_K_HZ, abs=1e-12)
    assert s_band_ledger["minus_10log_k_dbw_per_k_hz"] == pytest.approx(228.6, abs=0.01)


def test_ledger_is_internally_consistent(s_band_ledger):
    """The ledger must add up: each derived line follows from the ones above it."""
    led = s_band_ledger

    assert led["eirp_dbw"] == pytest.approx(
        led["p_tx_dbw"] + led["g_tx_dbi"] - led["l_tx_db"], abs=1e-9)
    assert led["g_over_t_db_per_k"] == pytest.approx(
        led["g_rx_dbi"] - lb.db(led["t_sys_k"]), abs=1e-9)
    assert led["cn0_dbhz"] == pytest.approx(
        led["eirp_dbw"] - led["fspl_db"] - led["other_losses_db"]
        + led["g_over_t_db_per_k"] + led["minus_10log_k_dbw_per_k_hz"], abs=1e-9)
    assert led["ten_log_bit_rate_db"] == pytest.approx(lb.db(led["bit_rate_bps"]), abs=1e-9)
    assert led["ebn0_db"] == pytest.approx(
        led["cn0_dbhz"] - led["ten_log_bit_rate_db"], abs=1e-9)
    assert led["margin_db"] == pytest.approx(
        led["ebn0_db"] - led["ebn0_required_total_db"], abs=1e-9)


# ---------------------------------------------------------------------------
# The ledger's contract
# ---------------------------------------------------------------------------
def test_ledger_keys_match_the_spec_order(s_band_ledger):
    """Exactly the spec's keys, in exactly the spec's order."""
    assert list(s_band_ledger) == list(lb.LEDGER_KEYS)


def test_ledger_key_order_is_the_documented_sequence(s_band_ledger):
    """The ledger order written out, so a reordering fails loudly."""
    assert list(s_band_ledger) == [
        "p_tx_dbw", "g_tx_dbi", "l_tx_db", "eirp_dbw",
        "slant_range_km", "fspl_db", "other_losses_db",
        "g_rx_dbi", "t_sys_k", "g_over_t_db_per_k", "minus_10log_k_dbw_per_k_hz",
        "cn0_dbhz",
        "bit_rate_bps", "ten_log_bit_rate_db", "ebn0_db",
        "ebn0_required_total_db",
        "margin_db",
        "max_bit_rate_bps_at_target_margin",
    ]


def test_computed_g_over_t_path_fills_dish_and_noise(s_band_ledger):
    """With g_over_t_db_per_k null, the dish and noise lines are computed."""
    assert s_band_ledger["g_rx_dbi"] is not None
    assert s_band_ledger["t_sys_k"] is not None


# ---------------------------------------------------------------------------
# The published-G/T override
# ---------------------------------------------------------------------------
def test_published_g_over_t_is_used_verbatim():
    """A published G/T is taken as given, and the dish and noise lines report None.

    A published figure of merit does not decompose into a gain and a temperature
    the tool can claim to know, so reporting a computed pair beside it would be
    inventing detail the operator never supplied.
    """
    from dataclasses import replace

    scenario = replace(load_scenario(S_BAND_YAML), g_over_t_db_per_k=20.0)
    ledger = lb.compute_ledger(scenario)

    assert ledger["g_over_t_db_per_k"] == pytest.approx(20.0, abs=1e-12)
    assert ledger["g_rx_dbi"] is None
    assert ledger["t_sys_k"] is None
    assert list(ledger) == list(lb.LEDGER_KEYS)           # order unchanged on this branch


def test_published_g_over_t_changes_the_budget():
    """The override must actually drive C/N0, not sit unused beside a computed value."""
    from dataclasses import replace

    base = load_scenario(S_BAND_YAML)
    computed = lb.compute_ledger(base)
    overridden = lb.compute_ledger(replace(base, g_over_t_db_per_k=
                                           computed["g_over_t_db_per_k"] + 3.0))

    assert overridden["cn0_dbhz"] == pytest.approx(computed["cn0_dbhz"] + 3.0, abs=1e-9)


# ---------------------------------------------------------------------------
# CLI display
# ---------------------------------------------------------------------------
def test_format_value_rounding_rules():
    """Spec: 2 decimals for dB, 1 for km and K, 3 significant figures for rates."""
    assert run.format_value(163.8774128659441, "db") == "163.88"
    assert run.format_value(1694.567221154679, "km") == "1694.6"
    assert run.format_value(150.0883694203085, "kelvin") == "150.1"
    assert run.format_value(14247079.651539218, "rate") == "1.42e+07"


def test_format_value_renders_none_as_not_applicable():
    """A published G/T leaves two lines blank; they must not read as zero."""
    assert run.format_value(None, "db") == "n/a"
    assert run.format_value(None, "kelvin") == "n/a"


def test_display_covers_every_ledger_key():
    """No ledger line may be silently dropped from the printed table."""
    displayed = [key for group in run.LEDGER_DISPLAY for key, _, _, _ in group]
    assert displayed == list(lb.LEDGER_KEYS)


def test_report_contains_name_and_key_values(s_band_ledger):
    scenario = load_scenario(S_BAND_YAML)
    report = run.format_ledger(s_band_ledger, scenario.name, scenario.target_margin_db)

    assert scenario.name in report
    assert "163.88" in report                             # FSPL, 2 decimals
    assert "1694.6" in report                             # slant range, 1 decimal
    assert "150.1" in report                              # T_sys, 1 decimal
    assert "77.54" in report                              # C/N0
    assert "11.53" in report                              # margin
    assert "Max bit rate at 3.00 dB margin" in report     # closing line names the margin


def test_report_shows_n_a_for_published_g_over_t():
    from dataclasses import replace

    scenario = replace(load_scenario(S_BAND_YAML), g_over_t_db_per_k=20.0)
    report = run.format_ledger(lb.compute_ledger(scenario), scenario.name,
                               scenario.target_margin_db)

    assert "n/a" in report


# ---------------------------------------------------------------------------
# CLI behaviour
# ---------------------------------------------------------------------------
def test_main_prints_ledger_and_exits_zero(capsys):
    exit_code = run.main([str(S_BAND_YAML)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "S-band TT&C downlink" in captured.out
    assert "C/N0" in captured.out
    assert "Margin" in captured.out


def test_main_reports_a_bad_scenario_on_stderr(tmp_path, capsys):
    """A malformed scenario exits non-zero with a readable message, not a traceback."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("altitude_km: 500.0\n", encoding="utf-8")

    exit_code = run.main([str(bad)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "missing key" in captured.err.lower()


def test_main_reports_a_missing_file_on_stderr(tmp_path, capsys):
    exit_code = run.main([str(tmp_path / "nope.yaml")])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.err != ""
