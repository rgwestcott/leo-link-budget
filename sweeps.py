"""Parametric studies over a scenario, returning NumPy arrays and no plots.

This module holds the sweep functions that show where the link opens and closes:
Eb/N0 and margin versus elevation angle, margin versus information bit rate, and
the maximum supportable bit rate at the target margin as a function of elevation.
Each takes a ``Scenario``, varies one parameter across an array of values, and
returns plain NumPy arrays -- nothing is printed, saved or drawn here, so the same
arrays can feed a plot, a test assertion or a table.

The sweeps are vectorised: one evaluation over an array rather than a Python loop
calling ``compute_ledger`` per point. Everything that does not vary with the swept
parameter -- EIRP, and the G/T that may come from either the dish calculation or a
published figure -- is taken from a single ``compute_ledger`` call, so the branchy
part of the chain has exactly one implementation and the two paths cannot drift.
Only the genuinely varying terms are recomputed across the array. A test asserts
the vectorised result equals a per-point ``compute_ledger`` sweep.
"""

import numpy as np

import link_budget as lb

# Default elevation grid: horizon to overhead in half-degree steps. Fine enough to
# place the zero-margin crossing to within a degree when plotted.
DEFAULT_ELEVATION_DEG = np.linspace(0.0, 90.0, 181)

# Default bit-rate grid spans two decades either side of the scenario's own rate,
# logarithmically because Eb/N0 is linear in log rate -- so margin falls as a
# straight line, and the rate at which the link closes is easy to read off.
DEFAULT_RATE_DECADES = 2.0
DEFAULT_RATE_POINTS = 201


def _invariant_terms(scenario):
    """Pull the terms that no sweep varies out of a single ledger evaluation.

    EIRP depends only on transmit-side fields, and G/T only on the receive
    station, so both are constant across an elevation or bit-rate sweep. Taking
    them from :func:`link_budget.compute_ledger` rather than recomputing them here
    means the published-G/T branch has one implementation, not two.

    Args:
        scenario: a Scenario.
    Returns:
        tuple (eirp_dbw [dBW], g_over_t_db_per_k [dB/K]), both scalars.
    """
    ledger = lb.compute_ledger(scenario)
    return ledger["eirp_dbw"], ledger["g_over_t_db_per_k"]


def sweep_elevation(scenario, elevation_deg=None):
    """Sweep elevation angle and return the budget at each point.

    As the satellite drops toward the horizon the slant range grows sharply, path
    loss with it, and margin falls; the elevation at which margin reaches zero is
    the usable edge of the pass.

    Args:
        scenario:      the Scenario to sweep.
        elevation_deg: elevation angles [deg], or None for DEFAULT_ELEVATION_DEG
                       (0 to 90 in half-degree steps).
    Returns:
        dict of NumPy arrays, all the same shape as the elevation grid:
        elevation_deg [deg], slant_range_km [km], fspl_db [dB],
        cn0_dbhz [dB-Hz], ebn0_db [dB], margin_db [dB].
    Reference:
        At 10 deg the s_band_ttc scenario gives margin 11.53 dB.
    """
    elevation_deg = np.asarray(DEFAULT_ELEVATION_DEG if elevation_deg is None
                               else elevation_deg, dtype=float)
    eirp_dbw, g_over_t_db_per_k = _invariant_terms(scenario)

    slant_range_km = lb.slant_range_km(scenario.altitude_km, elevation_deg)
    fspl_db = lb.fspl_db(slant_range_km, scenario.freq_mhz)
    cn0_dbhz = lb.cn0_dbhz(eirp_dbw, fspl_db, scenario.other_losses_db,
                           g_over_t_db_per_k)
    ebn0_db = lb.ebn0_db(cn0_dbhz, scenario.bit_rate_bps)
    margin_db = lb.margin_db(ebn0_db, scenario.required_ebn0_db,
                             scenario.implementation_loss_db)

    return {
        "elevation_deg": elevation_deg,
        "slant_range_km": slant_range_km,
        "fspl_db": fspl_db,
        "cn0_dbhz": cn0_dbhz,
        "ebn0_db": ebn0_db,
        "margin_db": margin_db,
    }


def sweep_bit_rate(scenario, bit_rate_bps=None):
    """Sweep information bit rate at the scenario's elevation.

    Geometry is fixed here, so C/N_0 is a constant and every doubling of rate
    costs 3.01 dB of Eb/N_0. Margin therefore falls linearly against log rate, and
    the crossing point is the fastest the link will carry at this elevation.

    Args:
        scenario:     the Scenario to sweep.
        bit_rate_bps: information bit rates [bit/s], or None for a logarithmic
                      grid spanning DEFAULT_RATE_DECADES either side of the
                      scenario's own rate.
    Returns:
        dict of NumPy arrays, all the same shape as the rate grid:
        bit_rate_bps [bit/s], ebn0_db [dB], margin_db [dB].
        Also carries cn0_dbhz as a scalar, since it does not vary here.
    Reference:
        At 2.0e6 bit/s the s_band_ttc scenario gives Eb/N0 14.53 dB.
    """
    if bit_rate_bps is None:
        centre = np.log10(scenario.bit_rate_bps)
        bit_rate_bps = np.logspace(centre - DEFAULT_RATE_DECADES,
                                   centre + DEFAULT_RATE_DECADES,
                                   DEFAULT_RATE_POINTS)
    bit_rate_bps = np.asarray(bit_rate_bps, dtype=float)

    eirp_dbw, g_over_t_db_per_k = _invariant_terms(scenario)
    slant_range_km = lb.slant_range_km(scenario.altitude_km, scenario.elevation_deg)
    fspl_db = lb.fspl_db(slant_range_km, scenario.freq_mhz)
    cn0_dbhz = lb.cn0_dbhz(eirp_dbw, fspl_db, scenario.other_losses_db,
                           g_over_t_db_per_k)                # scalar: geometry is fixed

    ebn0_db = lb.ebn0_db(cn0_dbhz, bit_rate_bps)
    margin_db = lb.margin_db(ebn0_db, scenario.required_ebn0_db,
                             scenario.implementation_loss_db)

    return {
        "bit_rate_bps": bit_rate_bps,
        "ebn0_db": ebn0_db,
        "margin_db": margin_db,
        "cn0_dbhz": cn0_dbhz,
    }


def sweep_max_rate_vs_elevation(scenario, elevation_deg=None):
    """Sweep elevation and return the rate each angle will carry at target margin.

    The operationally useful form of the elevation sweep: rather than asking
    whether a fixed rate closes, it asks how fast the link could run at each point
    in the pass while still holding the scenario's target margin in reserve.

    Args:
        scenario:      the Scenario to sweep.
        elevation_deg: elevation angles [deg], or None for DEFAULT_ELEVATION_DEG.
    Returns:
        dict of NumPy arrays, all the same shape as the elevation grid:
        elevation_deg [deg], cn0_dbhz [dB-Hz], max_bit_rate_bps [bit/s].
    Reference:
        At 10 deg the s_band_ttc scenario carries about 1.42e7 bit/s at 3 dB margin.
    """
    elevation = sweep_elevation(scenario, elevation_deg)
    max_bit_rate_bps = lb.max_bit_rate_bps(elevation["cn0_dbhz"],
                                           scenario.required_ebn0_db,
                                           scenario.implementation_loss_db,
                                           scenario.target_margin_db)

    return {
        "elevation_deg": elevation["elevation_deg"],
        "cn0_dbhz": elevation["cn0_dbhz"],
        "max_bit_rate_bps": max_bit_rate_bps,
    }
