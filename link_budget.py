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
        lin(10) = 10.0
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


# ---------------------------------------------------------------------------
# Wavelength
# ---------------------------------------------------------------------------
def wavelength_m(freq_mhz):
    """Free-space wavelength of a radio frequency.

        lambda = c / f

    The 1e6 converts the MHz argument to hertz. Frequency is in MHz everywhere in
    this project and never in GHz, so the conversion lives here rather than at
    each call site.

    Args:
        freq_mhz: carrier frequency [MHz]. Scalar or NumPy array. Must be positive.
    Returns:
        wavelength [m]. NumPy scalar or array.
    Reference:
        wavelength_m(2200) ≈ 0.13627 m  (S-band TT&C downlink)
    """
    freq_hz = np.multiply(freq_mhz, 1.0e6)                # MHz -> Hz
    return C_M_PER_S / freq_hz


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def slant_range_km(altitude_km, elevation_deg):
    """Straight-line distance from ground station to satellite.

    Law of cosines on the Earth-center / ground-station / satellite triangle;
    the angle at the ground station is 90° + elevation:

        d = sqrt((R_E + h)^2 - (R_E * cos(eps))^2) - R_E * sin(eps)

    Slant range grows sharply as the satellite drops toward the horizon: the
    same 500 km orbit is 500 km away overhead but over 2000 km away at 5°,
    which is what drives the elevation sweep in sweeps.py.

    Args:
        altitude_km:   orbit altitude above mean Earth surface [km]
        elevation_deg: satellite elevation above local horizon [deg]
                       (0 = horizon, 90 = directly overhead)
                       Either argument may be a NumPy array.
    Returns:
        slant range [km]. Equals altitude_km at 90° elevation.
    Reference:
        slant_range_km(500, 10) ≈ 1694.6 km
    """
    eps = np.radians(elevation_deg)                       # trig wants radians
    r_sat = EARTH_RADIUS_KM + altitude_km                 # orbit radius from Earth center
    return (np.sqrt(r_sat**2 - (EARTH_RADIUS_KM * np.cos(eps))**2)
            - EARTH_RADIUS_KM * np.sin(eps))


# ---------------------------------------------------------------------------
# Path loss
# ---------------------------------------------------------------------------
def fspl_db(distance_km, freq_mhz):
    """Free-space path loss over a slant range, in the physical form.

        FSPL = 20 * log10(4 * pi * d / lambda)      with d in metres

    This is spreading loss only: the 1/(4*pi*d^2) dilution of power over a sphere,
    expressed relative to the wavelength-sized effective aperture of an isotropic
    receiver. It excludes atmosphere, rain, polarization and pointing, which enter
    the ledger separately as other_losses_db.

    The familiar engineering shortcut

        FSPL ≈ 20*log10(d_km) + 20*log10(f_MHz) + 32.45

    is the same expression with the unit conversions folded into the constant
    32.45. It is quoted here as a cross-check only; this function implements the
    physical form above, so nothing depends on a rounded constant.

    Args:
        distance_km: slant range from ground station to satellite [km].
                     Scalar or NumPy array. Must be positive.
        freq_mhz:    carrier frequency [MHz]. Scalar or NumPy array.
    Returns:
        free-space path loss [dB], a positive number to be subtracted in the ledger.
    Reference:
        fspl_db(1694.6, 2200) ≈ 163.88 dB
    """
    distance_m = np.multiply(distance_km, 1000.0)         # km -> m, to match lambda
    lambda_m = wavelength_m(freq_mhz)                     # never a hardcoded constant
    return 20.0 * np.log10(4.0 * np.pi * distance_m / lambda_m)


# ---------------------------------------------------------------------------
# Antenna gain
# ---------------------------------------------------------------------------
def dish_gain_dbi(diameter_m, freq_mhz, efficiency=0.6):
    """Boresight gain of a circular parabolic reflector.

        G = 10 * log10(eta_a * (pi * D / lambda)^2)

    The (pi*D/lambda)^2 term is the gain an ideal uniformly illuminated aperture
    would have; the aperture efficiency eta_a discounts it for the real feed's
    illumination taper, spillover, blockage and surface tolerance. Gain rises as
    the square of both diameter and frequency, which is why the X-band case
    recovers much of the extra path loss it pays.

    Args:
        diameter_m: physical reflector diameter [m]. Scalar or NumPy array.
        freq_mhz:   carrier frequency [MHz]. Scalar or NumPy array.
        efficiency: aperture efficiency eta_a [dimensionless, 0..1].
                    0.6 is typical for a well-fed prime-focus dish.
    Returns:
        boresight gain [dBi], i.e. relative to an isotropic radiator.
    Reference:
        dish_gain_dbi(3.0, 2200.0, 0.6) ≈ 34.58 dBi
    """
    lambda_m = wavelength_m(freq_mhz)                     # never a hardcoded constant
    aperture_ratio = np.pi * diameter_m / lambda_m        # circumference in wavelengths
    return db(efficiency * aperture_ratio**2)             # ideal aperture gain, discounted


# ---------------------------------------------------------------------------
# Noise temperatures
# ---------------------------------------------------------------------------
def receiver_noise_temp_k(nf_db):
    """Equivalent input noise temperature of a receiver, from its noise figure.

        T_rx = T_0 * (10^(NF/10) - 1)

    Noise is bookkept as a temperature because a resistor at physical temperature
    T delivers a noise power spectral density of exactly k*T watts per hertz, so
    any noise source — an amplifier, the sky, the ground — can be quoted as the
    temperature of the resistor that would produce the same power, which makes
    contributions from wildly different physical origins simply add. The LNA sits
    at the antenna rather than at the far end of the feed because the Friis
    cascade divides each later stage's noise contribution by the total gain ahead
    of it, so once the first amplifier has supplied enough gain, everything
    downstream — cable, filter, receiver — is suppressed to near irrelevance.

    The -1 subtracts the noise of the T_0 source the noise figure is defined
    against, leaving only the noise the receiver itself adds.

    Args:
        nf_db: receiver noise figure [dB], referenced to T_0 = 290 K.
               Scalar or NumPy array.
    Returns:
        equivalent input noise temperature [K]. Zero for a noiseless (0 dB) receiver.
    Reference:
        receiver_noise_temp_k(1.0) ≈ 75.09 K; receiver_noise_temp_k(0.0) = 0.0 K
    """
    return T0_K * (lin(nf_db) - 1.0)                      # -1 removes the reference source


def system_noise_temp_k(t_ant_k, t_rx_k):
    """Total system noise temperature referred to the antenna terminals.

        T_sys = T_ant + T_rx

    The terms add directly because each is already the temperature of an
    equivalent resistor at the same reference plane, and uncorrelated noise powers
    sum. T_ant carries what the antenna sees (cosmic background, atmosphere, and
    ground spillover into the sidelobes); T_rx carries what the receiver adds.

    Args:
        t_ant_k: antenna noise temperature [K], elevation- and site-dependent.
                 Scalar or NumPy array.
        t_rx_k:  receiver equivalent input noise temperature [K], from
                 :func:`receiver_noise_temp_k`. Scalar or NumPy array.
    Returns:
        system noise temperature at the antenna terminals [K].
    Reference:
        system_noise_temp_k(75.0, 75.09) = 150.09 K
    """
    return np.add(t_ant_k, t_rx_k)                        # uncorrelated noise powers add


# ---------------------------------------------------------------------------
# Figure of merit
# ---------------------------------------------------------------------------
def g_over_t_db_per_k(g_rx_dbi, t_sys_k):
    """Ground-station figure of merit: receive gain over system noise temperature.

        G/T = G_rx - 10 * log10(T_sys)

    This is the single number that characterises a receiving station, because the
    ledger only ever uses gain and noise together: raising gain 1 dB and doubling
    T_sys 3 dB are equivalent trades. Operators publish G/T directly, which is why
    Scenario allows it to override the dish-and-noise calculation.

    Args:
        g_rx_dbi: receive antenna boresight gain [dBi]. Scalar or NumPy array.
        t_sys_k:  system noise temperature [K], from :func:`system_noise_temp_k`.
                  Scalar or NumPy array. Must be positive.
    Returns:
        figure of merit [dB/K].
    Reference:
        g_over_t_db_per_k(34.58, 150.09) ≈ 12.82 dB/K
    """
    return np.subtract(g_rx_dbi, db(t_sys_k))             # gain and noise always travel together


# ---------------------------------------------------------------------------
# Transmit side
# ---------------------------------------------------------------------------
def eirp_dbw(p_tx_dbw, g_tx_dbi, l_tx_db):
    """Effective isotropic radiated power.

        EIRP = P_tx + G_tx - L_tx

    The power an isotropic radiator would need in order to put the same flux on
    boresight as this transmitter and antenna do. Collapsing the whole transmit
    chain into one number is what lets the ledger treat everything upstream of
    the antenna as a single term.

    Args:
        p_tx_dbw: transmitter output power [dBW].
        g_tx_dbi: transmit antenna boresight gain [dBi].
        l_tx_db:  losses between transmitter and antenna [dB, positive] --
                  cable, connectors, filter and transmit pointing error.
                  Any argument may be a NumPy array.
    Returns:
        effective isotropic radiated power [dBW].
    Reference:
        eirp_dbw(0.0, 3.0, 1.0) = 2.0 dBW
    """
    return np.subtract(np.add(p_tx_dbw, g_tx_dbi), l_tx_db)   # losses quoted positive


# ---------------------------------------------------------------------------
# Carrier-to-noise density
# ---------------------------------------------------------------------------
def cn0_dbhz(eirp_dbw, fspl_db, other_losses_db, g_over_t_db_per_k):
    """Carrier power to noise power spectral density ratio.

        C/N_0 = EIRP - FSPL - L_other + G/T - 10*log10(k)

    C/N_0 is used rather than C/N because dividing by the noise density instead
    of the noise power takes bandwidth out of the expression entirely, and
    bandwidth is not known until a modem, symbol rate and filter roll-off have
    been chosen -- which happens long after the RF chain is fixed. C/N_0 is
    therefore the last quantity that belongs purely to the link, and every
    modem-dependent figure (Eb/N_0, Es/N_0, margin) is derived from it
    afterwards.

    The final term is a subtraction of a negative number, so it adds roughly
    228.6 dB. It is taken from BOLTZMANN_DBW_PER_K_HZ, which is computed from k;
    no rounded constant appears here.

    Args:
        eirp_dbw:          effective isotropic radiated power [dBW].
        fspl_db:           free-space path loss [dB, positive].
        other_losses_db:   atmosphere, rain, polarization, pointing, misc
                           [dB, positive].
        g_over_t_db_per_k: receive station figure of merit [dB/K].
                           Any argument may be a NumPy array.
    Returns:
        carrier-to-noise-density ratio [dB-Hz].
    Reference:
        cn0_dbhz(2.0, 163.88, 2.0, 12.82) is about 77.54 dB-Hz
    """
    c_over_t_db = (np.subtract(np.subtract(eirp_dbw, fspl_db), other_losses_db)
                   + g_over_t_db_per_k)                   # C/T at the receiver
    return c_over_t_db - BOLTZMANN_DBW_PER_K_HZ           # C/T -> C/N_0, via -(-228.599)


# ---------------------------------------------------------------------------
# Energy per bit
# ---------------------------------------------------------------------------
def ebn0_db(cn0_dbhz, bit_rate_bps):
    """Energy per bit to noise density ratio.

        Eb/N_0 = C/N_0 - 10*log10(R_b)

    Spreading the carrier power across more bits per second leaves less energy in
    each one, so every doubling of rate costs 3.01 dB.

    bit_rate_bps is INFORMATION bits per second -- the useful payload rate,
    before any forward-error-correction overhead or channel coding is applied.
    The required Eb/N_0 compared against this must therefore also be quoted per
    information bit; a figure quoted per channel bit differs by 10*log10(code
    rate), which is 3 dB at rate 1/2 and would silently swing the margin by that
    much in whichever direction the mismatch runs.

    Args:
        cn0_dbhz:     carrier-to-noise-density ratio [dB-Hz].
        bit_rate_bps: information bit rate [bit/s]. Must be positive.
                      Either argument may be a NumPy array.
    Returns:
        energy per information bit over noise density [dB].
    Reference:
        ebn0_db(77.54, 2.0e6) is about 14.53 dB
    """
    return np.subtract(cn0_dbhz, db(bit_rate_bps))        # 10*log10(R_b), power-style


# ---------------------------------------------------------------------------
# Symbol energy conversions
# ---------------------------------------------------------------------------
def esn0_from_ebn0_db(ebn0_db, bits_per_symbol, code_rate):
    """Convert energy per information bit to energy per transmitted symbol.

        Es/N_0 = Eb/N_0 + 10*log10(m * r)

    Each symbol carries m channel bits, of which a fraction r is information, so
    a symbol carries m*r information bits' worth of energy. Modem datasheets and
    standards tables (DVB-S2 in particular) quote required Es/N_0, while the
    ledger works in Eb/N_0; this is the bridge between them.

    Args:
        ebn0_db:         energy per information bit over noise density [dB].
        bits_per_symbol: m, channel bits per modulation symbol [dimensionless]
                         -- 1 for BPSK, 2 for QPSK, 3 for 8PSK.
        code_rate:       r, information bits per channel bit [dimensionless, 0..1].
                         Any argument may be a NumPy array.
    Returns:
        energy per symbol over noise density [dB].
    Reference:
        esn0_from_ebn0_db(1.0, 2, 0.5) = 1.0 dB;
        esn0_from_ebn0_db(2.27, 2, 0.75) is about 4.03 dB
    """
    return np.add(ebn0_db, db(np.multiply(bits_per_symbol, code_rate)))


def ebn0_from_esn0_db(esn0_db, bits_per_symbol, code_rate):
    """Convert energy per symbol back to energy per information bit.

        Eb/N_0 = Es/N_0 - 10*log10(m * r)

    Exact inverse of esn0_from_ebn0_db; use it to bring a required Es/N_0 from a
    standards table into the ledger's per-information-bit convention.

    Args:
        esn0_db:         energy per symbol over noise density [dB].
        bits_per_symbol: m, channel bits per modulation symbol [dimensionless].
        code_rate:       r, information bits per channel bit [dimensionless, 0..1].
                         Any argument may be a NumPy array.
    Returns:
        energy per information bit over noise density [dB].
    Reference:
        ebn0_from_esn0_db(4.03, 2, 0.75) is about 2.27 dB; round-trips within 1e-9
    """
    return np.subtract(esn0_db, db(np.multiply(bits_per_symbol, code_rate)))


# ---------------------------------------------------------------------------
# Margin and maximum rate
# ---------------------------------------------------------------------------
def margin_db(ebn0_db, required_ebn0_db, implementation_loss_db):
    """Link margin: how much worse the link may get before it stops closing.

        Margin = Eb/N_0 - (Eb/N_0_required + L_impl)

    The implementation loss is added to the requirement rather than subtracted
    from the achieved value; the arithmetic is identical, but it keeps the
    theoretical threshold and the hardware's shortfall against it as two
    separately auditable numbers. A positive margin means the link closes.

    Args:
        ebn0_db:                achieved energy per information bit over noise
                                density [dB].
        required_ebn0_db:       theoretical threshold for the chosen modulation,
                                coding and target BER [dB, per information bit].
        implementation_loss_db: modem shortfall against theory [dB, positive].
                                Any argument may be a NumPy array.
    Returns:
        link margin [dB]. Positive closes, negative does not.
    Reference:
        margin_db(14.53, 1.5, 1.5) = 11.53 dB
    """
    required_total_db = np.add(required_ebn0_db, implementation_loss_db)
    return np.subtract(ebn0_db, required_total_db)


def max_bit_rate_bps(cn0_dbhz, required_ebn0_db, implementation_loss_db,
                     target_margin_db=3.0):
    """Highest information bit rate that still leaves a target margin.

        R_max = 10^[(C/N_0 - Eb/N_0_required - L_impl - M_target) / 10]

    Solves the Eb/N_0 chain for rate instead of evaluating it at a fixed rate:
    whatever C/N_0 is left once the requirement, the implementation loss and the
    desired margin have been paid for is spent on bits per second. This is the
    quantity that answers how much data a pass can return, and it scales linearly
    in power -- every extra 3.01 dB of C/N_0 doubles it.

    Args:
        cn0_dbhz:               carrier-to-noise-density ratio [dB-Hz].
        required_ebn0_db:       threshold Eb/N_0 [dB, per information bit].
        implementation_loss_db: modem shortfall against theory [dB, positive].
        target_margin_db:       margin to hold in reserve [dB]; 3.0 by default.
                                Any argument may be a NumPy array.
    Returns:
        maximum information bit rate [bit/s].
    Reference:
        max_bit_rate_bps(77.54, 1.5, 1.5, 3.0) is about 1.43e7 bit/s
    """
    spare_cn0_dbhz = (cn0_dbhz - required_ebn0_db
                      - implementation_loss_db - target_margin_db)
    return lin(spare_cn0_dbhz)                            # spare dB-Hz -> bit/s
