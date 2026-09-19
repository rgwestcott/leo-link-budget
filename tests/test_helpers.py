"""Tests for the constants and dB/power helpers in link_budget.py.

Each test pins a reference value from the Physics spec table in CLAUDE.md, at the
tolerance stated there. Where the table gives no explicit tolerance, the value is
quoted to two decimals and is checked to +/-0.01. The array tests exist because the
sweeps in sweeps.py depend on every physics function accepting NumPy arrays
unchanged, so that property is pinned from the first function onward.
"""

import numpy as np
import pytest

import link_budget as lb


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
def test_earth_radius_km():
    assert lb.EARTH_RADIUS_KM == 6371.0


def test_speed_of_light_m_per_s():
    assert lb.C_M_PER_S == 299_792_458.0


def test_boltzmann_j_per_k():
    assert lb.BOLTZMANN_J_PER_K == 1.380649e-23


def test_boltzmann_dbw_per_k_hz_is_minus_228_6():
    """The familiar -228.6 dBW/K/Hz, to the spec's 0.01 dB tolerance."""
    assert lb.BOLTZMANN_DBW_PER_K_HZ == pytest.approx(-228.6, abs=0.01)


def test_boltzmann_dbw_per_k_hz_is_computed_not_typed():
    """Guards the "constants are computed, not typed" ground rule.

    A hand-typed -228.6 would pass the tolerance test above but fail here, because
    it differs from 10*log10(k) by ~0.0008 dB.
    """
    assert lb.BOLTZMANN_DBW_PER_K_HZ == 10.0 * np.log10(lb.BOLTZMANN_J_PER_K)
    assert lb.BOLTZMANN_DBW_PER_K_HZ != -228.6


def test_t0_k():
    assert lb.T0_K == 290.0


# ---------------------------------------------------------------------------
# db()
# ---------------------------------------------------------------------------
def test_db_of_two_is_3_0103():
    """Spec reference: db(2) = 3.0103 (+/-0.001)."""
    assert lb.db(2) == pytest.approx(3.0103, abs=0.001)


def test_db_of_one_is_zero():
    """A unit ratio is 0 dB by definition."""
    assert lb.db(1) == pytest.approx(0.0, abs=1e-12)


def test_db_uses_power_factor_ten():
    """A factor-of-10 power ratio is 10 dB, not 20 dB."""
    assert lb.db(10) == pytest.approx(10.0, abs=1e-12)


def test_db_accepts_arrays():
    result = lb.db(np.array([1.0, 2.0, 10.0, 100.0]))
    assert result == pytest.approx([0.0, 3.0103, 10.0, 20.0], abs=0.001)


# ---------------------------------------------------------------------------
# lin()
#
# NOTE: CLAUDE.md's table gives the reference value "lin(10) = 100 (+/-1e-9)",
# which contradicts the formula on the same row: 10^(10/10) = 10, not 100.
# The formula is implemented as written and pinned here; the disputed reference
# value is deliberately NOT asserted, pending a correction to CLAUDE.md.
# ---------------------------------------------------------------------------
def test_lin_of_twenty_is_one_hundred():
    """10^(20/10) = 100. This is the input that actually yields the spec's 100."""
    assert lb.lin(20) == pytest.approx(100.0, abs=1e-9)


def test_lin_of_ten_is_ten():
    """10^(10/10) = 10, per the formula on the spec row."""
    assert lb.lin(10) == pytest.approx(10.0, abs=1e-9)


def test_lin_of_zero_is_one():
    assert lb.lin(0) == pytest.approx(1.0, abs=1e-12)


def test_lin_inverts_db():
    """lin and db must round-trip; this is what forces lin(10) == 10."""
    for value in (0.5, 1.0, 2.0, 10.0, 1234.5):
        assert lb.lin(lb.db(value)) == pytest.approx(value, rel=1e-12)


def test_lin_accepts_arrays():
    result = lb.lin(np.array([0.0, 10.0, 20.0, 30.0]))
    assert result == pytest.approx([1.0, 10.0, 100.0, 1000.0], rel=1e-12)


# ---------------------------------------------------------------------------
# dbw_from_w()
# ---------------------------------------------------------------------------
def test_dbw_from_w_of_one_watt_is_zero():
    """Spec reference: dbw_from_w(1) = 0."""
    assert lb.dbw_from_w(1.0) == pytest.approx(0.0, abs=1e-12)


def test_dbw_from_w_of_two_watts_is_3_01():
    """Spec reference: dbw_from_w(2) = 3.01."""
    assert lb.dbw_from_w(2.0) == pytest.approx(3.01, abs=0.01)


def test_dbw_from_w_accepts_arrays():
    result = lb.dbw_from_w(np.array([1.0, 2.0, 5.0]))
    assert result == pytest.approx([0.0, 3.01, 6.99], abs=0.01)


# ---------------------------------------------------------------------------
# dbm_from_dbw()
# ---------------------------------------------------------------------------
def test_dbm_from_dbw_of_zero_is_thirty():
    """Spec reference: dbm_from_dbw(0) = 30."""
    assert lb.dbm_from_dbw(0.0) == pytest.approx(30.0, abs=1e-12)


def test_dbm_from_dbw_offset_is_exactly_thirty():
    """The offset is 10*log10(1000) = 30 dB exactly, at any input level."""
    assert lb.dbm_from_dbw(-17.5) == pytest.approx(12.5, abs=1e-12)


def test_dbm_from_dbw_agrees_with_one_watt_being_thirty_dbm():
    """Cross-check through dbw_from_w: 1 W is 0 dBW is 30 dBm."""
    assert lb.dbm_from_dbw(lb.dbw_from_w(1.0)) == pytest.approx(30.0, abs=1e-12)


def test_dbm_from_dbw_accepts_arrays():
    result = lb.dbm_from_dbw(np.array([0.0, 3.0, 10.0]))
    assert result == pytest.approx([30.0, 33.0, 40.0], abs=1e-12)
