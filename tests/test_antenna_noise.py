"""Tests for dish gain, noise temperatures and the G/T figure of merit.

Each test pins a reference value from the Physics spec table in CLAUDE.md, at the
tolerance stated there. The chain test at the end runs the real receive path --
dish gain and noise figure through to G/T -- because the spec's G/T reference is
quoted on rounded inputs, and only the chained form catches a unit or reference-
plane error at the seams between the four functions.
"""

import numpy as np
import pytest

import link_budget as lb


# ---------------------------------------------------------------------------
# dish_gain_dbi()
# ---------------------------------------------------------------------------
def test_dish_gain_three_metre_s_band():
    """Spec reference: dish_gain_dbi(3, 2200, 0.6) = 34.58 dBi (+/-0.05)."""
    assert lb.dish_gain_dbi(3.0, 2200.0, 0.6) == pytest.approx(34.58, abs=0.05)


def test_dish_gain_efficiency_defaults_to_point_six():
    """The spec gives efficiency=0.6 as the default; omitting it must not change the result."""
    assert lb.dish_gain_dbi(3.0, 2200.0) == pytest.approx(lb.dish_gain_dbi(3.0, 2200.0, 0.6),
                                                          rel=1e-12)


def test_dish_gain_scales_as_diameter_squared():
    """Doubling diameter quadruples aperture area: +6.02 dB."""
    delta_db = lb.dish_gain_dbi(6.0, 2200.0) - lb.dish_gain_dbi(3.0, 2200.0)
    assert delta_db == pytest.approx(lb.db(4.0), abs=1e-9)


def test_dish_gain_scales_as_frequency_squared():
    """Doubling frequency also quadruples gain, for the same physical dish."""
    delta_db = lb.dish_gain_dbi(3.0, 4400.0) - lb.dish_gain_dbi(3.0, 2200.0)
    assert delta_db == pytest.approx(lb.db(4.0), abs=1e-9)


def test_dish_gain_efficiency_enters_linearly_in_db():
    """Halving aperture efficiency costs exactly 3.01 dB."""
    delta_db = lb.dish_gain_dbi(3.0, 2200.0, 0.6) - lb.dish_gain_dbi(3.0, 2200.0, 0.3)
    assert delta_db == pytest.approx(lb.db(2.0), abs=1e-9)


def test_dish_gain_accepts_arrays():
    result = lb.dish_gain_dbi(np.array([3.0, 6.0]), 2200.0)
    assert isinstance(result, np.ndarray)
    assert result[0] == pytest.approx(34.58, abs=0.05)


# ---------------------------------------------------------------------------
# receiver_noise_temp_k()
# ---------------------------------------------------------------------------
def test_receiver_noise_temp_one_db_noise_figure():
    """Spec reference: receiver_noise_temp_k(1.0) = 75.09 K (+/-0.05)."""
    assert lb.receiver_noise_temp_k(1.0) == pytest.approx(75.09, abs=0.05)


def test_receiver_noise_temp_zero_db_is_noiseless():
    """Spec reference: receiver_noise_temp_k(0.0) = 0.0 K.

    A 0 dB noise figure means the receiver adds nothing of its own; the -1 in the
    formula is exactly what makes this come out at zero rather than at T_0.
    """
    assert lb.receiver_noise_temp_k(0.0) == pytest.approx(0.0, abs=1e-12)


def test_receiver_noise_temp_three_db_is_about_t0():
    """A 3.01 dB noise figure doubles the noise, so T_rx = T_0."""
    assert lb.receiver_noise_temp_k(lb.db(2.0)) == pytest.approx(lb.T0_K, rel=1e-12)


def test_receiver_noise_temp_increases_with_noise_figure():
    temps_k = lb.receiver_noise_temp_k(np.array([0.0, 0.5, 1.0, 2.0, 3.0]))
    assert np.all(np.diff(temps_k) > 0.0)


def test_receiver_noise_temp_accepts_arrays():
    result = lb.receiver_noise_temp_k(np.array([0.0, 1.0, 1.5]))
    assert isinstance(result, np.ndarray)
    assert result == pytest.approx([0.0, 75.09, 119.64], abs=0.05)


# ---------------------------------------------------------------------------
# system_noise_temp_k()
# ---------------------------------------------------------------------------
def test_system_noise_temp_adds_terms():
    """Spec reference: system_noise_temp_k(75, 75.09) = 150.09 K."""
    assert lb.system_noise_temp_k(75.0, 75.09) == pytest.approx(150.09, abs=1e-9)


def test_system_noise_temp_with_noiseless_receiver_is_antenna_only():
    assert lb.system_noise_temp_k(75.0, 0.0) == pytest.approx(75.0, abs=1e-12)


def test_system_noise_temp_accepts_arrays():
    """The elevation sweep varies antenna temperature as the dish tips toward the horizon."""
    t_ant_k = np.array([40.0, 75.0, 120.0])
    result = lb.system_noise_temp_k(t_ant_k, 75.09)
    assert isinstance(result, np.ndarray)
    assert result == pytest.approx([115.09, 150.09, 195.09], abs=1e-9)


# ---------------------------------------------------------------------------
# g_over_t_db_per_k()
# ---------------------------------------------------------------------------
def test_g_over_t_s_band_ground_station():
    """Spec reference: g_over_t_db_per_k(34.58, 150.09) = 12.82 dB/K (+/-0.05)."""
    assert lb.g_over_t_db_per_k(34.58, 150.09) == pytest.approx(12.82, abs=0.05)


def test_g_over_t_at_one_kelvin_is_just_gain():
    """10*log10(1) = 0, so G/T collapses to G_rx."""
    assert lb.g_over_t_db_per_k(34.58, 1.0) == pytest.approx(34.58, abs=1e-12)


def test_g_over_t_trades_gain_against_noise():
    """+3.01 dB of gain and a doubling of T_sys cancel exactly."""
    baseline = lb.g_over_t_db_per_k(34.58, 150.09)
    traded = lb.g_over_t_db_per_k(34.58 + lb.db(2.0), 2.0 * 150.09)
    assert traded == pytest.approx(baseline, abs=1e-12)


def test_g_over_t_accepts_arrays():
    t_sys_k = np.array([115.09, 150.09, 195.09])
    result = lb.g_over_t_db_per_k(34.58, t_sys_k)
    assert isinstance(result, np.ndarray)
    assert result.shape == t_sys_k.shape
    assert np.all(np.diff(result) < 0.0)                  # hotter system, worse figure of merit


# ---------------------------------------------------------------------------
# The receive chain end to end
# ---------------------------------------------------------------------------
def test_receive_chain_reaches_spec_g_over_t():
    """3 m dish, 2200 MHz, T_ant 75 K, LNA NF 1 dB -> G/T = 12.82 dB/K (+/-0.05).

    Runs the unrounded chain the ledger will use, rather than the spec's rounded
    intermediate values, so a mismatch at any seam shows up here.
    """
    g_rx_dbi = lb.dish_gain_dbi(3.0, 2200.0, 0.6)
    t_rx_k = lb.receiver_noise_temp_k(1.0)
    t_sys_k = lb.system_noise_temp_k(75.0, t_rx_k)

    assert g_rx_dbi == pytest.approx(34.58, abs=0.05)
    assert t_sys_k == pytest.approx(150.1, abs=0.05)
    assert lb.g_over_t_db_per_k(g_rx_dbi, t_sys_k) == pytest.approx(12.82, abs=0.05)
