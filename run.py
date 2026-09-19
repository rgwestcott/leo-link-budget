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
from pathlib import Path

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

# Deltas carry an explicit sign, so a column of them reads as "what the second
# scenario costs or buys" rather than as a second set of absolute values.
_DELTA_FORMATS = {
    "db": "{:+.2f}",
    "km": "{:+.1f}",
    "kelvin": "{:+.1f}",
    "rate": "{:+.3g}",
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


def format_delta(base_value, other_value, kind):
    """Round the difference between two ledger values for display.

    Args:
        base_value:  the first scenario's value, or None where it does not apply.
        other_value: the second scenario's value, or None.
        kind:        which rounding rule to use.
    Returns:
        the signed difference as text [str]; "n/a" if either side is absent,
        because a published G/T leaves no gain or temperature to subtract.
    Reference:
        format_delta(163.88, 175.31, "db") == "+11.43"
    """
    if base_value is None or other_value is None:
        return _NOT_APPLICABLE
    return _DELTA_FORMATS[kind].format(other_value - base_value)


def format_comparison(base_ledger, base_name, other_ledger, other_name):
    """Render two ledgers side by side with a delta column.

    The delta is other minus base, so a positive number is what the second
    scenario adds. Reading a budget this way is how a design trade is actually
    judged: the X-band case pays 11.43 dB more path loss than S-band at the same
    range, and the table shows both where that is spent and what buys it back.

    Args:
        base_ledger: the dict returned by compute_ledger for the base scenario.
        base_name:   the base scenario's name [str].
        other_ledger: the same for the scenario being compared against it.
        other_name:  the other scenario's name [str].
    Returns:
        the complete comparison report [str], without a trailing newline.
    """
    rows = []
    for group_index, group in enumerate(LEDGER_DISPLAY):
        for key, label, unit, kind in group:
            rows.append((group_index, label,
                         format_value(base_ledger[key], kind),
                         format_value(other_ledger[key], kind),
                         format_delta(base_ledger[key], other_ledger[key], kind),
                         unit))

    # Column headings share the width calculation, so a long delta never pushes
    # its heading out of alignment with the numbers beneath it.
    label_width = max([len(row[1]) for row in rows] + [len("")])
    base_width = max([len(row[2]) for row in rows] + [len("base")])
    other_width = max([len(row[3]) for row in rows] + [len("other")])
    delta_width = max([len(row[4]) for row in rows] + [len("delta")])

    lines = [
        f"base   {base_name}",
        f"other  {other_name}",
        "=" * max(len(base_name), len(other_name)) + "=======",
        "",
        f"  {'':<{label_width}}  {'base':>{base_width}}  {'other':>{other_width}}  "
        f"{'delta':>{delta_width}}",
    ]

    previous_group = None
    for group_index, label, base_value, other_value, delta, unit in rows:
        if previous_group is not None and group_index != previous_group:
            lines.append("")                              # same grouping as one ledger
        previous_group = group_index
        lines.append(f"  {label:<{label_width}}  {base_value:>{base_width}}  "
                     f"{other_value:>{other_width}}  {delta:>{delta_width}}  {unit}")

    lines.append("")
    lines.append("delta is other minus base")
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
    parser.add_argument("--sweep-elevation", action="store_true",
                        help="plot margin and max bit rate against elevation angle")
    parser.add_argument("--sweep-rate", action="store_true",
                        help="plot margin against information bit rate")
    parser.add_argument("--out", default="plots",
                        help="directory for rendered PNGs (default: plots)")
    parser.add_argument("--compare", metavar="OTHER.yaml",
                        help="print this scenario beside another, with a delta column")
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

    if args.compare:
        try:
            other = load_scenario(args.compare)
        except (FileNotFoundError, ValueError) as error:
            print(f"run.py: {error}", file=sys.stderr)
            return 2
        print(format_comparison(lb.compute_ledger(scenario), scenario.name,
                                lb.compute_ledger(other), other.name))
    else:
        print(format_ledger(lb.compute_ledger(scenario), scenario.name,
                            scenario.target_margin_db))

    if args.sweep_elevation or args.sweep_rate:
        # Imported here rather than at module scope so that printing a ledger
        # never pays for loading matplotlib, which dominates this tool's startup.
        import plots
        import sweeps

        written = []
        if args.sweep_elevation:
            written.append(plots.plot_margin_vs_elevation(
                sweeps.sweep_elevation(scenario), scenario,
                Path(args.out) / "margin_vs_elevation.png"))
            written.append(plots.plot_max_rate_vs_elevation(
                sweeps.sweep_max_rate_vs_elevation(scenario), scenario,
                Path(args.out) / "max_rate_vs_elevation.png"))
        if args.sweep_rate:
            written.append(plots.plot_margin_vs_bit_rate(
                sweeps.sweep_bit_rate(scenario), scenario,
                Path(args.out) / "margin_vs_bit_rate.png"))

        print()
        for path in written:
            print(f"wrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
