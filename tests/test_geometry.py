"""Tests for wavelength, slant-range geometry and free-space path loss.

Each test pins a reference value from the Physics spec table in CLAUDE.md, at the
tolerance stated there. Two tests go further than a single value: one checks
fspl_db against the 20log10(d_km) + 20log10(f_MHz) + 32.45 engineering shortcut,
which is an independent derivation of the same quantity, and one pins that
slant_range_km is array-shaped, since the elevation sweep depends on it.
"""

import numpy as np
import pytest

import link_budget as lb


# ---------------------------------------------------------------------------
# wavelength_m()
# ---------------------------------------------------------------------------
def test_wavelength_at_s_band():
    """Spec reference: wavelength_m(2200) = 0.13627 m (+/-1e-4)."""
    assert lb.wavelength_m(2200.0) == pytest.approx(0.13627, abs=1e-4)


def test_wavelength_equals_c_over_f():
    """The definition itself, independent of the MHz bookkeeping."""
    assert lb.wavelength_m(2200.0) == pytest.approx(lb.C_M_PER_S / 2.2e9, rel=1e-12)


def test_wavelength_is_inverse_in_frequency():
    """Doubling frequency halves wavelength."""
    assert lb.wavelength_m(4400.0) == pytest.approx(lb.wavelength_m(2200.0) / 2.0, rel=1e-12)


def test_wavelength_accepts_arrays():
    result = lb.wavelength_m(np.array([2200.0, 8200.0]))
    assert result == pytest.approx([0.13627, 0.036560], abs=1e-4)


# ---------------------------------------------------------------------------
# slant_range_km()
# ---------------------------------------------------------------------------
def test_slant_range_at_zenith_equals_altitude():
    """Spec reference: slant_range_km(500, 90) = 500.0 (+/-1e-6).

    Directly overhead the triangle collapses and slant range is just altitude.
    """
    assert lb.slant_range_km(500.0, 90.0) == pytest.approx(500.0, abs=1e-6)


def test_slant_range_at_ten_degrees():
    """Spec reference: slant_range_km(500, 10) = 1694.6 km (+/-1.0)."""
    assert lb.slant_range_km(500.0, 10.0) == pytest.approx(1694.6, abs=1.0)


def test_slant_range_at_five_degrees():
    """Spec reference: slant_range_km(500, 5) = 2077.1 km (+/-1.0)."""
    assert lb.slant_range_km(500.0, 5.0) == pytest.approx(2077.1, abs=1.0)


def test_slant_range_decreases_with_elevation():
    """Range is monotonic in elevation: farthest at the horizon, nearest overhead."""
    ranges = lb.slant_range_km(500.0, np.array([0.0, 5.0, 10.0, 30.0, 60.0, 90.0]))
    assert np.all(np.diff(ranges) < 0.0)


def test_slant_range_array_returns_same_shape():
    """The elevation sweep passes an array of angles and expects an array back."""
    elevations_deg = np.array([0.0, 5.0, 10.0, 30.0, 60.0, 90.0])
    ranges_km = lb.slant_range_km(500.0, elevations_deg)
    assert isinstance(ranges_km, np.ndarray)
    assert ranges_km.shape == elevations_deg.shape


def test_slant_range_array_matches_scalar_elementwise():
    """Vectorised evaluation must equal looping, or the sweeps would drift."""
    elevations_deg = np.array([5.0, 10.0, 30.0, 90.0])
    vectorised = lb.slant_range_km(500.0, elevations_deg)
    elementwise = [lb.slant_range_km(500.0, e) for e in elevations_deg]
    assert vectorised == pytest.approx(elementwise, rel=1e-12)


# ---------------------------------------------------------------------------
# fspl_db()
# ---------------------------------------------------------------------------
def test_fspl_at_s_band_ten_degrees():
    """Spec reference: fspl_db(1694.6, 2200) = 163.88 dB (+/-0.05)."""
    assert lb.fspl_db(1694.6, 2200.0) == pytest.approx(163.88, abs=0.05)


def test_fspl_agrees_with_32_45_shortcut():
    """Spec requirement: the physical form matches the shortcut within 0.01 dB.

    20log10(4*pi*d/lambda) with d in metres and the folded-constant form
    20log10(d_km) + 20log10(f_MHz) + 32.45 are the same expression; the residual
    is the rounding in 32.45 itself. Checked across the project's band and
    range of interest, not just at one point.
    """
    for distance_km in (500.0, 1694.6, 2077.1):
        for freq_mhz in (2200.0, 8200.0):
            shortcut_db = (20.0 * np.log10(distance_km)
                           + 20.0 * np.log10(freq_mhz)
                           + 32.45)
            assert lb.fspl_db(distance_km, freq_mhz) == pytest.approx(shortcut_db, abs=0.01)


def test_fspl_x_band_exceeds_s_band_by_11_43_db():
    """Spec reference: X-band costs 11.43 dB (+/-0.05) more than S-band at equal range."""
    delta_db = lb.fspl_db(1694.6, 8200.0) - lb.fspl_db(1694.6, 2200.0)
    assert delta_db == pytest.approx(11.43, abs=0.05)


def test_fspl_doubles_range_costs_six_db():
    """Inverse-square law: twice the distance is 6.02 dB more loss."""
    delta_db = lb.fspl_db(2000.0, 2200.0) - lb.fspl_db(1000.0, 2200.0)
    assert delta_db == pytest.approx(lb.db(4.0), abs=1e-9)


def test_fspl_accepts_arrays():
    """The elevation sweep feeds fspl_db an array of slant ranges."""
    distances_km = np.array([500.0, 1694.6, 2077.1])
    losses_db = lb.fspl_db(distances_km, 2200.0)
    assert isinstance(losses_db, np.ndarray)
    assert losses_db.shape == distances_km.shape
    assert losses_db[1] == pytest.approx(163.88, abs=0.05)


def test_fspl_chains_from_slant_range():
    """The ledger's real path: elevation -> slant range -> path loss."""
    range_km = lb.slant_range_km(500.0, 10.0)
    assert lb.fspl_db(range_km, 2200.0) == pytest.approx(163.88, abs=0.05)
