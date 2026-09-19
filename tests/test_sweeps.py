"""Tests for the vectorised parametric sweeps.

The sweeps evaluate the chain over an array rather than calling compute_ledger
once per point, which is faster and exercises the array support the physics tests
pin -- but it is a second path through the same physics, and a second path can
drift from the first. The agreement tests below are the guard: for each sweep, the
vectorised result must equal a per-point compute_ledger sweep to within floating
point, so any future change that moves one and not the other fails here.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import link_budget as lb
import sweeps
from scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
S_BAND_YAML = REPO_ROOT / "scenarios" / "s_band_ttc.yaml"


@pytest.fixture
def s_band():
    return load_scenario(S_BAND_YAML)


def ledger_per_point(scenario, **overrides):
    """Reference implementation: one compute_ledger call per swept value.

    Deliberately the slow, obvious version -- a Python loop over dataclasses.replace
    -- so that it has nothing in common with the vectorised code but the physics
    module itself.
    """
    (field, values), = overrides.items()
    return [lb.compute_ledger(replace(scenario, **{field: float(value)}))
            for value in values]


# ---------------------------------------------------------------------------
# The agreement tests: vectorised == per-point compute_ledger
# ---------------------------------------------------------------------------
def test_elevation_sweep_agrees_with_per_point_ledger(s_band):
    """The elevation sweep must match compute_ledger evaluated point by point."""
    elevations = np.array([0.0, 2.5, 5.0, 10.0, 25.0, 45.0, 70.0, 90.0])
    swept = sweeps.sweep_elevation(s_band, elevations)
    reference = ledger_per_point(s_band, elevation_deg=elevations)

    for key in ("slant_range_km", "fspl_db", "cn0_dbhz", "ebn0_db", "margin_db"):
        expected = [led[key] for led in reference]
        assert swept[key] == pytest.approx(expected, rel=1e-12, abs=1e-12), key


def test_bit_rate_sweep_agrees_with_per_point_ledger(s_band):
    """The bit-rate sweep must match compute_ledger evaluated point by point."""
    rates = np.array([1.0e4, 1.0e5, 2.0e6, 1.0e7, 5.0e7])
    swept = sweeps.sweep_bit_rate(s_band, rates)
    reference = ledger_per_point(s_band, bit_rate_bps=rates)

    for key in ("ebn0_db", "margin_db"):
        expected = [led[key] for led in reference]
        assert swept[key] == pytest.approx(expected, rel=1e-12, abs=1e-12), key

    assert swept["cn0_dbhz"] == pytest.approx(reference[0]["cn0_dbhz"], rel=1e-12)


def test_max_rate_sweep_agrees_with_per_point_ledger(s_band):
    """The max-rate-vs-elevation sweep must match the ledger point by point."""
    elevations = np.array([5.0, 10.0, 30.0, 60.0, 90.0])
    swept = sweeps.sweep_max_rate_vs_elevation(s_band, elevations)
    reference = ledger_per_point(s_band, elevation_deg=elevations)

    expected = [led["max_bit_rate_bps_at_target_margin"] for led in reference]
    assert swept["max_bit_rate_bps"] == pytest.approx(expected, rel=1e-12)


def test_agreement_holds_on_the_published_g_over_t_branch(s_band):
    """The invariant terms come from compute_ledger, so the override path agrees too."""
    published = replace(s_band, g_over_t_db_per_k=15.0)
    elevations = np.array([5.0, 10.0, 45.0, 90.0])

    swept = sweeps.sweep_elevation(published, elevations)
    reference = ledger_per_point(published, elevation_deg=elevations)

    expected = [led["cn0_dbhz"] for led in reference]
    assert swept["cn0_dbhz"] == pytest.approx(expected, rel=1e-12)


def test_agreement_holds_on_the_default_grids(s_band):
    """Agreement is checked on the full default grid, not just a handful of points."""
    swept = sweeps.sweep_elevation(s_band)
    reference = ledger_per_point(s_band, elevation_deg=swept["elevation_deg"])

    expected = [led["margin_db"] for led in reference]
    assert swept["margin_db"] == pytest.approx(expected, rel=1e-12, abs=1e-12)


# ---------------------------------------------------------------------------
# sweep_elevation()
# ---------------------------------------------------------------------------
def test_elevation_sweep_default_grid(s_band):
    swept = sweeps.sweep_elevation(s_band)

    assert swept["elevation_deg"][0] == pytest.approx(0.0)
    assert swept["elevation_deg"][-1] == pytest.approx(90.0)
    assert len(swept["elevation_deg"]) == 181


def test_elevation_sweep_returns_arrays_of_one_shape(s_band):
    swept = sweeps.sweep_elevation(s_band, np.linspace(5.0, 90.0, 18))

    for key, values in swept.items():
        assert isinstance(values, np.ndarray), key
        assert values.shape == (18,), key


def test_elevation_sweep_matches_the_worked_example_at_ten_degrees(s_band):
    """The sweep must reproduce the scenario's own ledger at its own elevation."""
    swept = sweeps.sweep_elevation(s_band, np.array([10.0]))

    assert swept["slant_range_km"][0] == pytest.approx(1694.6, abs=1.0)
    assert swept["fspl_db"][0] == pytest.approx(163.88, abs=0.05)
    assert swept["cn0_dbhz"][0] == pytest.approx(77.54, abs=0.1)
    assert swept["ebn0_db"][0] == pytest.approx(14.53, abs=0.1)
    assert swept["margin_db"][0] == pytest.approx(11.53, abs=0.1)


def test_margin_improves_with_elevation(s_band):
    """Higher elevation is shorter range, less loss, more margin -- monotonically."""
    swept = sweeps.sweep_elevation(s_band)

    assert np.all(np.diff(swept["margin_db"]) > 0.0)
    assert np.all(np.diff(swept["slant_range_km"]) < 0.0)
    assert np.all(np.diff(swept["fspl_db"]) < 0.0)


def test_elevation_sweep_accepts_a_plain_list(s_band):
    """Callers should not have to build an array first."""
    swept = sweeps.sweep_elevation(s_band, [10.0, 20.0])

    assert isinstance(swept["margin_db"], np.ndarray)
    assert swept["margin_db"].shape == (2,)


# ---------------------------------------------------------------------------
# sweep_bit_rate()
# ---------------------------------------------------------------------------
def test_bit_rate_sweep_default_grid_brackets_the_scenario_rate(s_band):
    swept = sweeps.sweep_bit_rate(s_band)

    assert len(swept["bit_rate_bps"]) == sweeps.DEFAULT_RATE_POINTS
    assert swept["bit_rate_bps"][0] < s_band.bit_rate_bps < swept["bit_rate_bps"][-1]
    assert swept["bit_rate_bps"][0] == pytest.approx(s_band.bit_rate_bps / 100.0, rel=1e-9)
    assert swept["bit_rate_bps"][-1] == pytest.approx(s_band.bit_rate_bps * 100.0, rel=1e-9)


def test_bit_rate_sweep_matches_the_worked_example_at_its_own_rate(s_band):
    swept = sweeps.sweep_bit_rate(s_band, np.array([2.0e6]))

    assert swept["ebn0_db"][0] == pytest.approx(14.53, abs=0.1)
    assert swept["margin_db"][0] == pytest.approx(11.53, abs=0.1)


def test_margin_falls_three_db_per_doubling_of_rate(s_band):
    """Eb/N0 is linear in log rate, so margin loses 3.01 dB each time rate doubles."""
    swept = sweeps.sweep_bit_rate(s_band, np.array([1.0e6, 2.0e6, 4.0e6]))
    steps = np.diff(swept["margin_db"])

    assert steps == pytest.approx([-lb.db(2.0), -lb.db(2.0)], abs=1e-9)


def test_bit_rate_sweep_cn0_is_scalar(s_band):
    """Geometry is fixed in a rate sweep, so C/N0 does not vary across it."""
    swept = sweeps.sweep_bit_rate(s_band, np.array([1.0e6, 2.0e6]))

    assert np.ndim(swept["cn0_dbhz"]) == 0


def test_margin_crosses_zero_within_the_default_rate_grid(s_band):
    """The default span is wide enough to show where the link stops closing."""
    swept = sweeps.sweep_bit_rate(s_band)

    assert swept["margin_db"][0] > 0.0
    assert swept["margin_db"][-1] < 0.0


# ---------------------------------------------------------------------------
# sweep_max_rate_vs_elevation()
# ---------------------------------------------------------------------------
def test_max_rate_sweep_shapes(s_band):
    swept = sweeps.sweep_max_rate_vs_elevation(s_band, np.linspace(5.0, 90.0, 18))

    for key, values in swept.items():
        assert isinstance(values, np.ndarray), key
        assert values.shape == (18,), key


def test_max_rate_rises_with_elevation(s_band):
    swept = sweeps.sweep_max_rate_vs_elevation(s_band)

    assert np.all(np.diff(swept["max_bit_rate_bps"]) > 0.0)


def test_max_rate_at_ten_degrees_matches_the_worked_example(s_band):
    swept = sweeps.sweep_max_rate_vs_elevation(s_band, np.array([10.0]))

    assert swept["max_bit_rate_bps"][0] == pytest.approx(1.43e7, rel=0.02)


def test_max_rate_leaves_the_target_margin(s_band):
    """Running at the swept rate must leave exactly the scenario's target margin."""
    swept = sweeps.sweep_max_rate_vs_elevation(s_band, np.array([5.0, 10.0, 45.0]))
    achieved = lb.ebn0_db(swept["cn0_dbhz"], swept["max_bit_rate_bps"])
    margin = lb.margin_db(achieved, s_band.required_ebn0_db, s_band.implementation_loss_db)

    assert margin == pytest.approx([s_band.target_margin_db] * 3, abs=1e-9)


# ---------------------------------------------------------------------------
# The module's ground rule
# ---------------------------------------------------------------------------
def test_sweeps_module_does_not_import_matplotlib():
    """sweeps.py returns arrays; rendering belongs to plots.py."""
    source = (REPO_ROOT / "sweeps.py").read_text(encoding="utf-8")
    assert "matplotlib" not in source
    assert "pyplot" not in source
