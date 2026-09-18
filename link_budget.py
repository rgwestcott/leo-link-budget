"""Pure physics for the LEO downlink budget: no printing, no file I/O, no plotting.

This module will hold the project's constants (mean Earth radius, speed of light,
Boltzmann's constant in both J/K and dBW/K/Hz, and the 290 K noise-figure reference
temperature -- each derived value computed rather than typed as a literal) and one
function per step of the link ledger, in dependency order: the dB/linear helpers,
wavelength and slant range, free-space path loss, dish gain, receiver and system
noise temperatures, G/T, EIRP, C/N0, Eb/N0, the Es/N0 conversions, link margin, and
the maximum-bit-rate solver. It will close with ``compute_ledger(scenario)``, which
runs that chain end to end and returns the ordered ledger dict at full precision.
Every function takes numbers or NumPy arrays and returns the same, using ``numpy``
math so sweeps work without change, and carries a docstring stating its formula,
the units of each argument and of the return value, and one reference value.
"""
