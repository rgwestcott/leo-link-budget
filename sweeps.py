"""Parametric studies over a scenario, returning NumPy arrays and no plots.

This module will hold the sweep functions that show where the link opens and closes:
margin and Eb/N0 versus elevation angle from the horizon to overhead, margin versus
information bit rate, and the maximum supportable bit rate at a target margin as a
function of elevation. Each function takes a ``Scenario``, varies one parameter across
an array of values, re-runs the ledger for each point, and returns plain NumPy arrays
of the swept variable alongside the resulting quantities -- nothing is printed, saved,
or drawn here. Keeping the sweeps free of rendering means the same arrays can feed a
plot, a test assertion, or a table, and it relies on the physics functions being
NumPy-friendly so a sweep is a vectorised evaluation rather than a Python loop.
"""
