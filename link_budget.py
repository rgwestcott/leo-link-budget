"""Pure physics for the LEO downlink budget: no printing, no file I/O, no plotting.

This module holds the project's constants and one function per step of the link
ledger, in dependency order: the dB/linear helpers, wavelength and slant range,
free-space path loss, dish gain, receiver and system noise temperatures, G/T, EIRP,
C/N0, Eb/N0, the Es/N0 conversions, link margin, and the maximum-bit-rate solver.
It closes with ``compute_ledger(scenario)``, which runs that chain end to end and
returns the ordered ledger dict at full precision. Every function takes numbers or
NumPy arrays and returns the same, using ``numpy`` math so sweeps work without
change, and carries a docstring stating its formula, the units of each argument and
of the return value, and one reference value.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0
"""Mean Earth radius [km]. Spherical-Earth assumption for slant-range geometry."""

C_M_PER_S = 299_792_458.0
"""Speed of light in vacuum [m/s]. Exact by SI definition of the metre."""

BOLTZMANN_J_PER_K = 1.380649e-23
"""Boltzmann's constant k [J/K]. Exact by SI definition of the kelvin."""

# Computed from k, never typed as the familiar -228.6 literal: the ledger subtracts
# this term to turn a noise temperature into a noise power spectral density, and a
# rounded literal would quietly bias every C/N0 in the project by ~0.001 dB.
BOLTZMANN_DBW_PER_K_HZ = 10.0 * np.log10(BOLTZMANN_J_PER_K)
"""Boltzmann's constant in log units [dBW/K/Hz], i.e. 10*log10(k) ≈ -228.599."""

T0_K = 290.0
"""Reference temperature for noise figure [K]. The IEEE standard T0."""


# ---------------------------------------------------------------------------
# Decibel helpers
# ---------------------------------------------------------------------------
def db(x):
    """Convert a linear power ratio to decibels.

        dB = 10 * log10(x)

    Power ratios use the factor 10; amplitude ratios would use 20. Everything in
    this project is a power quantity, so 10 is correct throughout.

    Args:
        x: linear power ratio [dimensionless], or a power in watts to get dBW.
           Scalar or NumPy array. Must be positive.
    Returns:
        the same quantity in decibels [dB]. NumPy scalar or array.
    Reference:
        db(2) ≈ 3.0103 dB
    """
    return 10.0 * np.log10(x)                             # power ratio: factor 10, not 20


def lin(x_db):
    """Convert decibels back to a linear power ratio. Inverse of :func:`db`.

        x = 10^(x_db / 10)

    Args:
        x_db: a power quantity in decibels [dB]. Scalar or NumPy array.
    Returns:
        the equivalent linear power ratio [dimensionless]. NumPy scalar or array.
    Reference:
        lin(10) = 100.0
    """
    return np.power(10.0, np.divide(x_db, 10.0))          # np.power keeps arrays working


# ---------------------------------------------------------------------------
# Power conversions
# ---------------------------------------------------------------------------
def dbw_from_w(p_w):
    """Express an absolute power in dBW, i.e. decibels relative to one watt.

        P_dBW = 10 * log10(p_w / 1 W)

    The 1 W reference is what makes the result absolute rather than a bare ratio;
    it is written out below so the unit cancellation is visible.

    Args:
        p_w: transmit or received power [W]. Scalar or NumPy array. Must be positive.
    Returns:
        the same power [dBW]. NumPy scalar or array.
    Reference:
        dbw_from_w(1.0) = 0.0 dBW; dbw_from_w(2.0) ≈ 3.01 dBW
    """
    reference_power_w = 1.0                               # the "W" in dBW, stated explicitly
    return db(p_w / reference_power_w)


def dbm_from_dbw(p_dbw):
    """Convert dBW to dBm by shifting the reference from 1 W to 1 mW.

        P_dBm = P_dBW + 30

    The offset is 10*log10(1 W / 1 mW) = 10*log10(1000) = 30 dB exactly.

    Args:
        p_dbw: power referenced to one watt [dBW]. Scalar or NumPy array.
    Returns:
        the same power referenced to one milliwatt [dBm]. NumPy scalar or array.
    Reference:
        dbm_from_dbw(0.0) = 30.0 dBm
    """
    dbw_to_dbm_offset_db = 30.0                           # 10*log10(1 W / 1 mW)
    return np.add(p_dbw, dbw_to_dbm_offset_db)            # np.add keeps arrays working
