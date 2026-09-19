"""Tests for the link equations: EIRP, C/N0, Eb/N0, Es/N0, margin and max rate.

Each test pins a reference value from the Physics spec table in CLAUDE.md, at the
tolerance stated there. Two tests go beyond single values: the Es/N0 round-trip
pins that the two conversions are exact inverses, and a substitution test pins
that cn0_dbhz genuinely reads BOLTZMANN_DBW_PER_K_HZ rather than carrying its own
rounded copy of -228.6.
"""

import numpy as np
import pytest

import link_budget as lb


# ---------------------------------------------------------------------------
# eirp_dbw()
# ---------------------------------------------------------------------------
def test_eirp_reference_case():
    """Spec reference: eirp_dbw(0, 3, 1) = 2.0 dBW."""
    assert lb.eirp_dbw(0.0, 3.0, 1.0) == pytest.approx(2.0, abs=1e-12)


def test_eirp_subtracts_transmit_losses():
    """Transmit losses are quoted positive and must reduce EIRP."""
    assert lb.eirp_dbw(0.0, 3.0, 2.0) < lb.eirp_dbw(0.0, 3.0, 1.0)


def test_eirp_is_lossless_sum_when_no_loss():
    assert lb.eirp_dbw(7.0, 6.0, 0.0) == pytest.approx(13.0, abs=1e-12)


def test_eirp_accepts_arrays():
    result = lb.eirp_dbw(np.array([0.0, 7.0]), np.array([3.0, 6.0]), np.array([1.0, 1.5]))
    assert isinstance(result, np.ndarray)
    assert result == pytest.approx([2.0, 11.5], abs=1e-12)


# ---------------------------------------------------------------------------
# cn0_dbhz()
# ---------------------------------------------------------------------------
def test_cn0_reference_case():
    """Spec reference: cn0_dbhz(2, 163.88, 2, 12.82) = 77.54 dB-Hz (+/-0.05)."""
    assert lb.cn0_dbhz(2.0, 163.88, 2.0, 12.82) == pytest.approx(77.54, abs=0.05)


def test_cn0_uses_the_computed_boltzmann_constant(monkeypatch):
    """C/N0 must read BOLTZMANN_DBW_PER_K_HZ, not a typed -228.6.

    Substituting the module constant has to move the answer by exactly the same
    amount. A hardcoded literal in the function body would not budge.
    """
    baseline = lb.cn0_dbhz(2.0, 163.88, 2.0, 12.82)
    monkeypatch.setattr(lb, "BOLTZMANN_DBW_PER_K_HZ", lb.BOLTZMANN_DBW_PER_K_HZ - 10.0)
    assert lb.cn0_dbhz(2.0, 163.88, 2.0, 12.82) == pytest.approx(baseline + 10.0, abs=1e-9)


def test_cn0_adds_about_228_6_db():
    """The k term enters as a subtraction of a negative, i.e. it adds ~228.6 dB."""
    without_k_term = 2.0 - 163.88 - 2.0 + 12.82
    assert lb.cn0_dbhz(2.0, 163.88, 2.0, 12.82) - without_k_term == pytest.approx(228.6, abs=0.01)


def test_cn0_losses_reduce_and_gain_raises():
    baseline = lb.cn0_dbhz(2.0, 163.88, 2.0, 12.82)
    assert lb.cn0_dbhz(2.0, 163.88, 3.0, 12.82) == pytest.approx(baseline - 1.0, abs=1e-9)
    assert lb.cn0_dbhz(2.0, 163.88, 2.0, 13.82) == pytest.approx(baseline + 1.0, abs=1e-9)


def test_cn0_accepts_arrays():
    """The elevation sweep feeds C/N0 an array of path losses."""
    fspl_db = np.array([153.88, 163.88, 173.88])
    result = lb.cn0_dbhz(2.0, fspl_db, 2.0, 12.82)
    assert isinstance(result, np.ndarray)
    assert result[1] == pytest.approx(77.54, abs=0.05)
    assert np.all(np.diff(result) < 0.0)                  # more loss, less C/N0


# ---------------------------------------------------------------------------
# ebn0_db()
# ---------------------------------------------------------------------------
def test_ebn0_reference_case():
    """Spec reference: ebn0_db(77.54, 2e6) = 14.53 dB (+/-0.05)."""
    assert lb.ebn0_db(77.54, 2.0e6) == pytest.approx(14.53, abs=0.05)


def test_ebn0_doubling_rate_costs_three_db():
    """Twice the bits, half the energy each: -3.01 dB."""
    delta_db = lb.ebn0_db(77.54, 4.0e6) - lb.ebn0_db(77.54, 2.0e6)
    assert delta_db == pytest.approx(-lb.db(2.0), abs=1e-9)


def test_ebn0_at_one_bit_per_second_equals_cn0():
    """10*log10(1) = 0, so the whole carrier-to-noise density lands in one bit."""
    assert lb.ebn0_db(77.54, 1.0) == pytest.approx(77.54, abs=1e-12)


def test_ebn0_accepts_arrays():
    """The rate sweep feeds Eb/N0 an array of bit rates."""
    bit_rates_bps = np.array([1.0e6, 2.0e6, 4.0e6])
    result = lb.ebn0_db(77.54, bit_rates_bps)
    assert isinstance(result, np.ndarray)
    assert result[1] == pytest.approx(14.53, abs=0.05)
    assert np.all(np.diff(result) < 0.0)                  # faster, less energy per bit


# ---------------------------------------------------------------------------
# esn0_from_ebn0_db() and ebn0_from_esn0_db()
# ---------------------------------------------------------------------------
def test_esn0_qpsk_rate_one_half_is_unchanged():
    """Spec reference: esn0_from_ebn0_db(1.0, 2, 0.5) = 1.0 dB.

    m*r = 2*0.5 = 1, so 10*log10(1) = 0 and the two are numerically equal --
    the one case where the distinction is invisible.
    """
    assert lb.esn0_from_ebn0_db(1.0, 2, 0.5) == pytest.approx(1.0, abs=1e-12)


def test_esn0_qpsk_rate_three_quarters():
    """Spec reference: esn0_from_ebn0_db(2.27, 2, 0.75) = 4.03 dB (+/-0.01).

    This is the DVB-S2 QPSK 3/4 operating point used by the X-band case.
    """
    assert lb.esn0_from_ebn0_db(2.27, 2, 0.75) == pytest.approx(4.03, abs=0.01)


def test_ebn0_from_esn0_reverses_the_dvb_s2_point():
    """The same operating point read the other way: 4.03 dB Es/N0 -> 2.27 dB Eb/N0."""
    assert lb.ebn0_from_esn0_db(4.03, 2, 0.75) == pytest.approx(2.27, abs=0.01)


def test_esn0_ebn0_round_trip():
    """Spec requirement: the two conversions round-trip within 1e-9.

    Swept over both directions and across the modulation and coding combinations
    the project uses, so the inverse is pinned as an identity rather than at a
    single point.
    """
    for bits_per_symbol in (1, 2, 3, 4):
        for code_rate in (0.25, 0.5, 0.75, 0.9, 1.0):
            for ebn0 in (-2.0, 0.0, 1.5, 2.27, 14.53):
                esn0 = lb.esn0_from_ebn0_db(ebn0, bits_per_symbol, code_rate)
                assert lb.ebn0_from_esn0_db(esn0, bits_per_symbol, code_rate) == pytest.approx(
                    ebn0, abs=1e-9)

                back = lb.esn0_from_ebn0_db(
                    lb.ebn0_from_esn0_db(esn0, bits_per_symbol, code_rate),
                    bits_per_symbol, code_rate)
                assert back == pytest.approx(esn0, abs=1e-9)


def test_esn0_accepts_arrays():
    result = lb.esn0_from_ebn0_db(np.array([1.0, 2.27]), 2, np.array([0.5, 0.75]))
    assert isinstance(result, np.ndarray)
    assert result == pytest.approx([1.0, 4.03], abs=0.01)


# ---------------------------------------------------------------------------
# margin_db()
# ---------------------------------------------------------------------------
def test_margin_reference_case():
    """Spec reference: margin_db(14.53, 1.5, 1.5) = 11.53 dB (+/-0.05)."""
    assert lb.margin_db(14.53, 1.5, 1.5) == pytest.approx(11.53, abs=0.05)


def test_margin_charges_implementation_loss_against_the_requirement():
    """A 1.5 dB implementation loss must cost exactly 1.5 dB of margin."""
    with_loss = lb.margin_db(14.53, 1.5, 1.5)
    without_loss = lb.margin_db(14.53, 1.5, 0.0)
    assert without_loss - with_loss == pytest.approx(1.5, abs=1e-12)


def test_margin_is_zero_when_exactly_at_threshold():
    """The closure boundary: achieved equals requirement plus implementation loss."""
    assert lb.margin_db(3.0, 1.5, 1.5) == pytest.approx(0.0, abs=1e-12)


def test_margin_goes_negative_below_threshold():
    assert lb.margin_db(2.0, 1.5, 1.5) < 0.0


def test_margin_accepts_arrays():
    """The elevation sweep asks where margin crosses zero."""
    ebn0_db = np.array([2.0, 3.0, 14.53])
    result = lb.margin_db(ebn0_db, 1.5, 1.5)
    assert isinstance(result, np.ndarray)
    assert result == pytest.approx([-1.0, 0.0, 11.53], abs=0.05)


# ---------------------------------------------------------------------------
# max_bit_rate_bps()
# ---------------------------------------------------------------------------
def test_max_bit_rate_reference_case():
    """Spec reference: max_bit_rate_bps(77.54, 1.5, 1.5, 3.0) = 1.43e7 bit/s (+/-2%)."""
    assert lb.max_bit_rate_bps(77.54, 1.5, 1.5, 3.0) == pytest.approx(1.43e7, rel=0.02)


def test_max_bit_rate_defaults_to_three_db_target_margin():
    """The spec gives target_margin_db=3.0 as the default."""
    assert lb.max_bit_rate_bps(77.54, 1.5, 1.5) == pytest.approx(
        lb.max_bit_rate_bps(77.54, 1.5, 1.5, 3.0), rel=1e-12)


def test_max_bit_rate_doubles_per_three_db_of_cn0():
    """Rate is linear in power: +3.01 dB of C/N0 buys twice the bits."""
    faster = lb.max_bit_rate_bps(77.54 + lb.db(2.0), 1.5, 1.5, 3.0)
    assert faster == pytest.approx(2.0 * lb.max_bit_rate_bps(77.54, 1.5, 1.5, 3.0), rel=1e-12)


def test_max_bit_rate_is_consistent_with_margin():
    """Running at R_max must leave exactly the target margin.

    This is the round-trip that ties the solver back to the forward chain: take
    the rate the solver returns, push it through ebn0_db and margin_db, and the
    result must be the target margin that was asked for.
    """
    target_margin_db = 3.0
    rate_bps = lb.max_bit_rate_bps(77.54, 1.5, 1.5, target_margin_db)
    achieved_ebn0_db = lb.ebn0_db(77.54, rate_bps)
    assert lb.margin_db(achieved_ebn0_db, 1.5, 1.5) == pytest.approx(target_margin_db, abs=1e-9)


def test_max_bit_rate_zero_target_margin_gives_more_rate():
    assert lb.max_bit_rate_bps(77.54, 1.5, 1.5, 0.0) > lb.max_bit_rate_bps(77.54, 1.5, 1.5, 3.0)


def test_max_bit_rate_accepts_arrays():
    cn0_dbhz = np.array([74.53, 77.54, 80.55])
    result = lb.max_bit_rate_bps(cn0_dbhz, 1.5, 1.5, 3.0)
    assert isinstance(result, np.ndarray)
    assert result[1] == pytest.approx(1.43e7, rel=0.02)
    assert np.all(np.diff(result) > 0.0)                  # more C/N0, more bits


# ---------------------------------------------------------------------------
# The full chain, end to end
# ---------------------------------------------------------------------------
def test_s_band_chain_from_geometry_to_margin():
    """The worked example, run unrounded from altitude and elevation to margin.

    Every value below is the spec's expected ledger for scenarios/s_band_ttc.yaml.
    Running it chained rather than from the spec's rounded intermediates is what
    catches an error at a seam between two otherwise-correct functions.
    """
    eirp = lb.eirp_dbw(0.0, 3.0, 1.0)
    range_km = lb.slant_range_km(500.0, 10.0)
    path_loss = lb.fspl_db(range_km, 2200.0)
    g_rx = lb.dish_gain_dbi(3.0, 2200.0, 0.6)
    t_sys = lb.system_noise_temp_k(75.0, lb.receiver_noise_temp_k(1.0))
    g_t = lb.g_over_t_db_per_k(g_rx, t_sys)
    cn0 = lb.cn0_dbhz(eirp, path_loss, 2.0, g_t)
    ebn0 = lb.ebn0_db(cn0, 2.0e6)

    assert eirp == pytest.approx(2.0, abs=1e-12)
    assert range_km == pytest.approx(1694.6, abs=1.0)
    assert path_loss == pytest.approx(163.88, abs=0.05)
    assert g_rx == pytest.approx(34.58, abs=0.05)
    assert t_sys == pytest.approx(150.1, abs=0.05)
    assert g_t == pytest.approx(12.82, abs=0.05)
    assert cn0 == pytest.approx(77.54, abs=0.1)
    assert ebn0 == pytest.approx(14.53, abs=0.1)
    assert lb.margin_db(ebn0, 1.5, 1.5) == pytest.approx(11.53, abs=0.1)
    assert lb.max_bit_rate_bps(cn0, 1.5, 1.5, 3.0) == pytest.approx(1.43e7, rel=0.02)
