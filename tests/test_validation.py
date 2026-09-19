"""Pins agreement with a published link budget.

The reference is the downlink column of Table 3 in R. Baktur, "CubeSat Link Budget:
Elements, calculations, and examples," IEEE Antennas and Propagation Magazine, vol.
64, no. 6, Dec. 2022, DOI 10.1109/MAP.2022.3201250 -- a budget developed for the DICE
mission. Its inputs live in scenarios/validation_dice_downlink.yaml and the line-by-
line comparison is in docs/validation.md.

The two assertions that matter are C/N0 and link margin, each within 0.3 dB. Those
are the totals: every term has to be interpreted the same way for them to agree, so
a change that quietly alters a constant, drops a loss, or shifts a convention will
show up here even when the unit tests still pass.
"""

from pathlib import Path

import pytest

import link_budget as lb
import run
from scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATION_YAML = REPO_ROOT / "scenarios" / "validation_dice_downlink.yaml"

# The tolerance the validation document commits to.
TOLERANCE_DB = 0.3

# The reference's downlink column, as transcribed in docs/validation.md.
REFERENCE = {
    "p_tx_dbw": 0.0,
    "g_tx_dbi": -3.5,
    "l_tx_db": 0.5,
    "eirp_dbw": -4.0,
    "fspl_db": 151.57,
    "other_losses_db": 1.5,
    "g_over_t_db_per_k": 9.03,
    "cn0_dbhz": 80.56,
    "ten_log_bit_rate_db": 61.76,
    "ebn0_db": 18.8,
    "ebn0_required_total_db": 11.6,
    "margin_db": 7.2,
}


@pytest.fixture
def validation_scenario():
    return load_scenario(VALIDATION_YAML)


@pytest.fixture
def validation_ledger(validation_scenario):
    return lb.compute_ledger(validation_scenario)


# ---------------------------------------------------------------------------
# The two headline assertions
# ---------------------------------------------------------------------------
def test_reference_cn0_within_tolerance(validation_ledger):
    """C/N0 must match the published budget within 0.3 dB."""
    assert validation_ledger["cn0_dbhz"] == pytest.approx(80.56, abs=TOLERANCE_DB)


def test_reference_margin_within_tolerance(validation_ledger):
    """Link margin must match the published budget within 0.3 dB."""
    assert validation_ledger["margin_db"] == pytest.approx(7.2, abs=TOLERANCE_DB)


# ---------------------------------------------------------------------------
# Every other line of the published budget
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key,reference_db", sorted(REFERENCE.items()))
def test_every_reference_line_within_tolerance(validation_ledger, key, reference_db):
    """Each dB line of the reference budget, one test apiece."""
    assert validation_ledger[key] == pytest.approx(reference_db, abs=TOLERANCE_DB)


def test_slant_range_reproduces_the_reference_path_length(validation_ledger):
    """The reference states 1944 km; altitude and elevation were chosen to match it.

    Pinned in kilometres rather than dB because this is a geometry input, not a
    budget line: the tolerance that matters is its effect on path loss, checked below.
    """
    assert validation_ledger["slant_range_km"] == pytest.approx(1944.0, abs=1.0)


def test_path_length_difference_costs_almost_nothing(validation_ledger):
    """The 0.32 km range difference must not move path loss meaningfully."""
    at_reference_range = lb.fspl_db(1944.0, 465.0)

    assert validation_ledger["fspl_db"] == pytest.approx(at_reference_range, abs=0.01)


# ---------------------------------------------------------------------------
# The noise chain, which the published-G/T path bypasses
# ---------------------------------------------------------------------------
def test_receiver_noise_temperature_matches_the_reference(validation_scenario):
    """The reference's 3.08 dB noise figure gives its stated 300 K, to 1 K."""
    t_rx_k = lb.receiver_noise_temp_k(validation_scenario.lna_nf_db)

    assert t_rx_k == pytest.approx(300.0, abs=1.0)


def test_system_noise_temperature_matches_the_reference(validation_scenario):
    """T_ant 200 K plus the receiver's contribution gives the reference's 500 K."""
    t_sys_k = lb.system_noise_temp_k(
        validation_scenario.t_ant_k,
        lb.receiver_noise_temp_k(validation_scenario.lna_nf_db))

    assert t_sys_k == pytest.approx(500.0, abs=1.0)
    assert lb.db(t_sys_k) == pytest.approx(lb.db(500.0), abs=0.01)


def test_g_over_t_recomputed_from_the_reference_gain(validation_scenario):
    """36.02 dB of effective gain over the computed T_sys reproduces G/T to 0.01 dB.

    The scenario takes G/T as published, so this is the only place the tool's own
    G/T calculation is checked against the reference rather than against the spec.
    """
    t_sys_k = lb.system_noise_temp_k(
        validation_scenario.t_ant_k,
        lb.receiver_noise_temp_k(validation_scenario.lna_nf_db))

    assert lb.g_over_t_db_per_k(36.02, t_sys_k) == pytest.approx(9.03, abs=0.01)


def test_noise_density_matches_the_reference(validation_scenario):
    """10*log10(k*T_sys) reproduces the reference's -201.61 dBW/Hz."""
    noise_density = lb.BOLTZMANN_DBW_PER_K_HZ + lb.db(500.0)

    assert noise_density == pytest.approx(-201.61, abs=0.01)


# ---------------------------------------------------------------------------
# The scenario file itself
# ---------------------------------------------------------------------------
def test_scenario_name_carries_the_citation(validation_scenario):
    """The source must travel with the numbers, not only in the docs."""
    name = validation_scenario.name

    assert "Baktur" in name
    assert "10.1109/MAP.2022.3201250" in name


def test_scenario_uses_the_published_g_over_t(validation_scenario):
    """The reference's ground antenna is an array, so G/T is taken, not computed."""
    assert validation_scenario.g_over_t_db_per_k == pytest.approx(9.03)


def test_ledger_reports_dish_and_noise_lines_as_absent(validation_ledger):
    """With G/T published, those two lines must be None rather than invented."""
    assert validation_ledger["g_rx_dbi"] is None
    assert validation_ledger["t_sys_k"] is None


def test_validation_scenario_runs_through_the_cli(capsys):
    exit_code = run.main([str(VALIDATION_YAML)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Baktur" in captured.out
    assert "7.20" in captured.out                         # the reference's link margin


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------
def test_validation_doc_exists_and_cites_the_source():
    """docs/validation.md must carry the citation and the tolerance it claims."""
    doc = (REPO_ROOT / "docs" / "validation.md").read_text(encoding="utf-8")

    assert "10.1109/MAP.2022.3201250" in doc
    assert "Baktur" in doc
    assert "0.3 dB" in doc
