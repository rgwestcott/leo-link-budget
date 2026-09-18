"""Scenario definition and YAML loading for the link budget.

This module will hold the frozen ``Scenario`` dataclass -- the complete set of inputs
one link case needs, in the order given by the spec: name, geometry (altitude and
elevation), transmitter (frequency, transmit power, antenna gain, transmit losses),
path losses, receiver (dish diameter and efficiency, antenna and LNA noise, with an
optional published G/T that overrides the dish-and-noise calculation), and the data
and modem terms (bit rate, bits per symbol, code rate, required Eb/N0, implementation
loss, target margin). Alongside it will live ``load_scenario(path)``, which parses a
YAML file from ``scenarios/`` into that dataclass and raises ``ValueError`` naming any
key that is unknown or missing, so a malformed scenario fails loudly at load time
rather than silently producing a plausible-looking ledger.
"""
