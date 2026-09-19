"""Matplotlib rendering of sweep results to PNG files.

This module holds the plotting layer: functions that take the NumPy arrays
produced by ``sweeps.py`` and render them to PNG, normally into the gitignored
``plots/`` directory or into ``docs/img/`` for the figures the README embeds. All
axis labelling, unit annotation, titling and file naming live here, so the physics
and sweep modules stay free of any presentation concern and a change to how a
figure looks never touches a formula.

Each figure carries one series, so none needs a legend -- the title names the
quantity and the axis labels carry the units. The threshold lines (zero margin,
the scenario's own operating point) are drawn recessively and labelled directly,
so the reader never has to match a colour to a key.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")                                     # render to file, never to a window

import matplotlib.pyplot as plt                           # noqa: E402  (must follow use())
import numpy as np                                        # noqa: E402

# Light-surface colours. One series per figure, so only one series colour is
# needed; text and grid wear ink colours rather than the series colour, which
# keeps identity with the line and legibility with the labels.
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
SERIES = "#2a78d6"
GRID = "#dcdbd6"
THRESHOLD = "#8a8880"

FIGSIZE = (8.0, 4.5)
DPI = 140
LINEWIDTH = 2.0


def _new_axes(title, subtitle, xlabel, ylabel):
    """Create a figure and axes with this project's chart styling applied.

    Args:
        title:    the headline, naming the quantity plotted [str].
        subtitle: the scenario the figure describes [str].
        xlabel:   x-axis label, including units [str].
        ylabel:   y-axis label, including units [str].
    Returns:
        tuple (figure, axes).
    """
    figure, axes = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    figure.patch.set_facecolor(SURFACE)
    axes.set_facecolor(SURFACE)

    axes.set_title(title, color=TEXT_PRIMARY, fontsize=13, fontweight="semibold",
                   loc="left", pad=18)
    # The scenario name sits above the axes as a subtitle rather than in the title,
    # so the headline stays readable at README width.
    axes.text(0.0, 1.03, subtitle, transform=axes.transAxes,
              color=TEXT_SECONDARY, fontsize=9.5)

    axes.set_xlabel(xlabel, color=TEXT_SECONDARY, fontsize=10)
    axes.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=10)

    axes.grid(True, color=GRID, linewidth=0.8, alpha=0.9)  # recessive, behind the data
    axes.set_axisbelow(True)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(GRID)
    axes.tick_params(colors=TEXT_SECONDARY, labelsize=9.5, length=0)

    return figure, axes


def _save(figure, path):
    """Write a figure to disk, creating the directory if needed, and close it.

    Args:
        figure: the matplotlib figure to write.
        path:   destination PNG path [str or pathlib.Path].
    Returns:
        the path written [pathlib.Path].
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor=figure.get_facecolor(), bbox_inches="tight")
    plt.close(figure)                                     # free the figure, not just the window
    return path


def _mark_zero_margin(axes, label_x):
    """Draw and label the zero-margin line: above it the link closes, below it it does not.

    Args:
        axes:    the axes to draw on.
        label_x: x position for the text label, in data coordinates.
    """
    axes.axhline(0.0, color=THRESHOLD, linewidth=1.2, linestyle="--")
    axes.text(label_x, 0.0, "  link closes above this line", color=TEXT_SECONDARY,
              fontsize=9, va="bottom")


def plot_margin_vs_elevation(sweep, scenario, path):
    """Render link margin against elevation angle.

    Margin falls steeply near the horizon, where a degree of elevation buys a
    large reduction in slant range, and flattens toward zenith, where it buys
    almost none. The scenario's own elevation is marked so the figure can be read
    against the printed ledger.

    Args:
        sweep:    the dict returned by :func:`sweeps.sweep_elevation`.
        scenario: the Scenario the sweep describes.
        path:     destination PNG path.
    Returns:
        the path written [pathlib.Path].
    """
    figure, axes = _new_axes("Link margin vs elevation", scenario.name,
                             "Elevation above horizon (deg)", "Margin (dB)")

    axes.plot(sweep["elevation_deg"], sweep["margin_db"],
              color=SERIES, linewidth=LINEWIDTH)
    axes.set_xlim(0.0, 90.0)
    axes.set_xticks(np.arange(0.0, 91.0, 10.0))
    _mark_zero_margin(axes, 1.0)

    # One direct label, at the scenario's own operating point, so the figure ties
    # back to the ledger without numbering every point on the curve.
    operating_margin = float(np.interp(scenario.elevation_deg,
                                       sweep["elevation_deg"], sweep["margin_db"]))
    axes.plot([scenario.elevation_deg], [operating_margin], "o",
              color=SERIES, markersize=8, zorder=5)
    axes.annotate(f"{scenario.elevation_deg:.0f} deg: {operating_margin:.1f} dB",
                  xy=(scenario.elevation_deg, operating_margin),
                  xytext=(10, -14), textcoords="offset points",
                  color=TEXT_PRIMARY, fontsize=9.5)

    return _save(figure, path)


def plot_margin_vs_bit_rate(sweep, scenario, path):
    """Render link margin against information bit rate, at the scenario's elevation.

    Geometry is fixed, so margin falls as a straight line against log rate -- 3.01
    dB per doubling -- and the zero crossing is the fastest the link will carry.

    Args:
        sweep:    the dict returned by :func:`sweeps.sweep_bit_rate`.
        scenario: the Scenario the sweep describes.
        path:     destination PNG path.
    Returns:
        the path written [pathlib.Path].
    """
    figure, axes = _new_axes(
        "Link margin vs bit rate",
        f"{scenario.name} - fixed at {scenario.elevation_deg:.0f} deg elevation",
        "Information bit rate (bit/s)", "Margin (dB)")

    axes.plot(sweep["bit_rate_bps"], sweep["margin_db"],
              color=SERIES, linewidth=LINEWIDTH)
    axes.set_xscale("log")
    _mark_zero_margin(axes, sweep["bit_rate_bps"][0])

    # Label where the link stops closing: the rate at which margin reaches zero.
    margin = sweep["margin_db"]
    if margin[0] > 0.0 > margin[-1]:
        closing_rate_bps = float(np.interp(0.0, margin[::-1], sweep["bit_rate_bps"][::-1]))
        axes.axvline(closing_rate_bps, color=THRESHOLD, linewidth=1.2, linestyle=":")
        axes.annotate(f"closes at {closing_rate_bps / 1e6:.3g} Mbit/s",
                      xy=(closing_rate_bps, 0.0), xytext=(8, 12),
                      textcoords="offset points", color=TEXT_PRIMARY, fontsize=9.5)

    return _save(figure, path)


def plot_max_rate_vs_elevation(sweep, scenario, path):
    """Render the rate the link will carry at target margin, against elevation.

    The operational form of the elevation sweep: not whether a fixed rate closes,
    but how fast the link could run at each point in the pass.

    Args:
        sweep:    the dict returned by :func:`sweeps.sweep_max_rate_vs_elevation`.
        scenario: the Scenario the sweep describes.
        path:     destination PNG path.
    Returns:
        the path written [pathlib.Path].
    """
    figure, axes = _new_axes(
        f"Maximum bit rate at {scenario.target_margin_db:.0f} dB margin",
        scenario.name,
        "Elevation above horizon (deg)", "Maximum information bit rate (Mbit/s)")

    axes.plot(sweep["elevation_deg"], sweep["max_bit_rate_bps"] / 1e6,
              color=SERIES, linewidth=LINEWIDTH)
    axes.set_xlim(0.0, 90.0)
    axes.set_xticks(np.arange(0.0, 91.0, 10.0))
    axes.set_yscale("log")

    return _save(figure, path)


def render_all(scenario, out_dir):
    """Render every sweep figure for one scenario into a directory.

    Args:
        scenario: the Scenario to plot.
        out_dir:  destination directory; created if it does not exist.
    Returns:
        list of paths written [list of pathlib.Path], in render order.
    """
    import sweeps                                         # local: keeps plots importable alone

    out_dir = Path(out_dir)
    return [
        plot_margin_vs_elevation(sweeps.sweep_elevation(scenario), scenario,
                                 out_dir / "margin_vs_elevation.png"),
        plot_margin_vs_bit_rate(sweeps.sweep_bit_rate(scenario), scenario,
                                out_dir / "margin_vs_bit_rate.png"),
        plot_max_rate_vs_elevation(sweeps.sweep_max_rate_vs_elevation(scenario), scenario,
                                   out_dir / "max_rate_vs_elevation.png"),
    ]
