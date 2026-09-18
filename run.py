"""Command-line entry point: print a ledger, run sweeps, compare scenarios.

This module will hold the CLI that ties the other modules together. Given a scenario
YAML path it will load the scenario, call ``compute_ledger``, and print the ledger as
a readable table in the spec's order -- rounding for display only (two decimals for
dB, one for kilometres and kelvin, three significant figures for bit rates) while the
underlying values stay at full precision. Flags will add the parametric studies
(``--sweep-elevation``, ``--sweep-rate``) with an ``--out`` directory for the rendered
PNGs, and ``--compare`` will place a second scenario's ledger beside the first so the
S-band TT&C and X-band payload cases can be read line by line against each other.
Argument parsing, formatting, and exit codes belong here; no physics does.
"""
