"""Command-line entry point: print a link budget ledger for a scenario file.

This module ties the other modules together. Given a scenario YAML path it loads
the scenario, calls ``compute_ledger``, and prints the ledger as an aligned table
in the order the spec fixes -- rounding for display only (two decimals for dB, one
for kilometres and kelvin, three significant figures for bit rates) while the
underlying values stay at full precision. Argument parsing, formatting and exit
codes belong here; no physics does. Later steps add the sweep flags and the
scenario comparison.
"""

import argparse
import sys

import link_budget as lb
from scenario import load_scenario

# How each ledger key is displayed: the label to print, its unit, and which
# rounding rule applies. The groups mirror the ledger order in CLAUDE.md, and the
# blank line between them is what makes the output read as a budget rather than a
# list -- transmit terms, then the path, then the receive station, then the
# results of combining them.
LEDGER_DISPLAY = (
    (
        ("p_tx_dbw", "Transmit power", "dBW", "db"),
        ("g_tx_dbi", "Transmit antenna gain", "dBi", "db"),
        ("l_tx_db", "Transmit losses", "dB", "db"),
        ("eirp_dbw", "EIRP", "dBW", "db"),
    ),
    (
        ("slant_range_km", "Slant range", "km", "km"),
        ("fspl_db", "Free-space path loss", "dB", "db"),
        ("other_losses_db", "Other losses", "dB", "db"),
    ),
    (
        ("g_rx_dbi", "Receive antenna gain", "dBi", "db"),
        ("t_sys_k", "System noise temperature", "K", "kelvin"),
        ("g_over_t_db_per_k", "G/T", "dB/K", "db"),
        ("minus_10log_k_dbw_per_k_hz", "-10log10(k)", "dBW/K/Hz", "db"),
    ),
    (
        ("cn0_dbhz", "C/N0", "dB-Hz", "db"),
    ),
    (
        ("bit_rate_bps", "Bit rate", "bit/s", "rate"),
        ("ten_log_bit_rate_db", "10log10(bit rate)", "dB", "db"),
        ("ebn0_db", "Eb/N0", "dB", "db"),
    ),
    (
        ("ebn0_required_total_db", "Required Eb/N0 + impl loss", "dB", "db"),
    ),
    (
        ("margin_db", "Margin", "dB", "db"),
    ),
    (
        ("max_bit_rate_bps_at_target_margin", "Max bit rate at target margin",
         "bit/s", "rate"),
    ),
)

# Rounding rules from the spec. Bit rates get three significant figures rather
# than a fixed number of decimals, because they span kilobits to hundreds of
# megabits across the scenarios this tool is meant to compare.
_FORMATS = {
    "db": "{:.2f}",
    "km": "{:.1f}",
    "kelvin": "{:.1f}",
    "rate": "{:.3g}",
}

# Printed where a published G/T means the dish gain and system temperature were
# never computed, so that a blank is never mistaken for a zero.
_NOT_APPLICABLE = "n/a"


def format_value(value, kind):
    """Round one ledger value for display.

    Args:
        value: the full-precision ledger value, or None when it does not apply.
        kind:  which rounding rule to use -- "db", "km", "kelvin" or "rate".
    Returns:
        the rounded value as text [str]; "n/a" for None.
    Reference:
        format_value(163.8774, "db") == "163.88"
    """
    if value is None:
        return _NOT_APPLICABLE
    return _FORMATS[kind].format(value)


def format_ledger(ledger, name, target_margin_db):
    """Render a ledger as the aligned table the CLI prints.

    Kept separate from printing so the output can be tested as a string, and so
    a later step can put two of these side by side for --compare.

    Args:
        ledger:           the dict returned by :func:`link_budget.compute_ledger`.
        name:             the scenario's name, printed as the heading [str].
        target_margin_db: the margin the max-rate figure holds in reserve [dB],
                          named in the closing line so the number is not read as
                          an unconditional capacity.
    Returns:
        the complete report [str], without a trailing newline.
    """
    rows = [(label, format_value(ledger[key], kind), unit)
            for group in LEDGER_DISPLAY for key, label, unit, kind in group]
    label_width = max(len(label) for label, _, _ in rows)
    value_width = max(len(value) for _, value, _ in rows)

    lines = [name, "=" * len(name), ""]
    for group in LEDGER_DISPLAY:
        for key, label, unit, kind in group:
            value = format_value(ledger[key], kind)
            lines.append(f"  {label:<{label_width}}  {value:>{value_width}}  {unit}")
        lines.append("")                                  # blank line between groups

    target_rate = ledger["max_bit_rate_bps_at_target_margin"]
    lines.append(f"Max bit rate at {target_margin_db:.2f} dB margin: "
                 f"{target_rate:.3g} bit/s ({target_rate / 1e6:.3g} Mbit/s)")
    return "\n".join(lines)


def build_parser():
    """Build the command-line parser.

    Returns:
        a configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Compute and print a LEO downlink link budget from a scenario file.",
    )
    parser.add_argument("scenario", help="path to a scenario YAML file, e.g. "
                                         "scenarios/s_band_ttc.yaml")
    return parser


def main(argv=None):
    """Load a scenario, compute its ledger and print it.

    Args:
        argv: command-line arguments, or None to read sys.argv.
    Returns:
        process exit code [int]: 0 on success, 2 if the scenario could not be read.
    """
    args = build_parser().parse_args(argv)

    try:
        scenario = load_scenario(args.scenario)
    except (FileNotFoundError, ValueError) as error:
        # A bad scenario file is the expected failure here, and its message
        # already names the file and the offending keys; a traceback would bury it.
        print(f"run.py: {error}", file=sys.stderr)
        return 2

    print(format_ledger(lb.compute_ledger(scenario), scenario.name,
                        scenario.target_margin_db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
