"""Matplotlib rendering of sweep results to PNG files.

This module will hold the plotting layer: functions that take the NumPy arrays
produced by ``sweeps.py`` and render them as figures written to the ``plots/``
directory (gitignored), or to ``docs/img/`` for the one or two PNGs embedded in the
README. Expected figures are margin versus elevation with the zero-margin line
marked, margin versus bit rate showing where the link closes, and maximum bit rate
versus elevation. All axis labelling, unit annotation, titling, legend placement, and
file naming live here, so that the physics and sweep modules stay free of any
presentation concern and a change to how a figure looks never touches a formula.
"""
