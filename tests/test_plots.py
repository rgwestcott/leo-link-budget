"""Tests for the PNG rendering layer.

A plot is hard to assert on directly, so these tests work at two levels. The
figure-level tests capture the matplotlib figure before it is written -- by
patching plots._save -- and check what actually got drawn: that the line carries
the sweep's own arrays, that the axes are labelled and scaled as intended, and
that a single-series figure carries no legend. The file-level tests then confirm
the bytes on disk are a real PNG of sensible size, that the output directory is
created, and that no figure is left open, since a leaked figure is the usual way a
batch of renders exhausts memory.

Nothing here asserts on appearance. Colour and layout are judged by looking at the
output; what is pinned is that the picture is of the right data.
"""

from pathlib import Path

import numpy as np
import pytest

import matplotlib.pyplot as plt

import plots
import sweeps
from scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
S_BAND_YAML = REPO_ROOT / "scenarios" / "s_band_ttc.yaml"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def s_band():
    return load_scenario(S_BAND_YAML)


@pytest.fixture
def captured_figure(monkeypatch):
    """Capture the figure a plot function builds, instead of writing it.

    plots._save writes the figure and closes it, which puts it out of reach of a
    test. Patching _save keeps the figure alive so its contents can be inspected,
    and hands back the same path the real function would have returned.
    """
    captured = {}

    def fake_save(figure, path):
        captured["figure"] = figure
        captured["path"] = Path(path)
        return Path(path)

    monkeypatch.setattr(plots, "_save", fake_save)
    return captured


def only_axes(captured):
    """The single axes of a captured figure."""
    return captured["figure"].axes[0]


def series_line(axes):
    """The data line of a single-series figure: the first Line2D drawn on it."""
    return axes.lines[0]


# ---------------------------------------------------------------------------
# What actually gets drawn: margin vs elevation
# ---------------------------------------------------------------------------
def test_margin_vs_elevation_draws_the_sweep_arrays(s_band, captured_figure, tmp_path):
    """The plotted line must carry the sweep's own numbers, not a re-derivation."""
    sweep = sweeps.sweep_elevation(s_band)
    plots.plot_margin_vs_elevation(sweep, s_band, tmp_path / "m.png")

    line = series_line(only_axes(captured_figure))
    assert line.get_xdata() == pytest.approx(sweep["elevation_deg"])
    assert line.get_ydata() == pytest.approx(sweep["margin_db"])


def test_margin_vs_elevation_is_labelled(s_band, captured_figure, tmp_path):
    """Axis labels carry the units; the title names the quantity."""
    plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                   tmp_path / "m.png")
    axes = only_axes(captured_figure)

    assert "margin" in axes.get_title("left").lower()
    assert "elevation" in axes.get_title("left").lower()
    assert "deg" in axes.get_xlabel().lower()
    assert "dB" in axes.get_ylabel()


def test_margin_vs_elevation_names_the_scenario(s_band, captured_figure, tmp_path):
    """The subtitle states which case the curve describes."""
    plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                   tmp_path / "m.png")
    texts = [text.get_text() for text in only_axes(captured_figure).texts]

    assert any(s_band.name in text for text in texts)


def test_margin_vs_elevation_marks_zero_margin(s_band, captured_figure, tmp_path):
    """The closure threshold must be drawn, or the curve has no reference."""
    plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                   tmp_path / "m.png")
    axes = only_axes(captured_figure)

    horizontal = [line for line in axes.lines
                  if len(set(np.round(line.get_ydata(), 12))) == 1]
    assert any(line.get_ydata()[0] == pytest.approx(0.0) for line in horizontal)


def test_margin_vs_elevation_marks_the_operating_point(s_band, captured_figure, tmp_path):
    """One direct label at the scenario's own elevation ties the figure to the ledger."""
    sweep = sweeps.sweep_elevation(s_band)
    plots.plot_margin_vs_elevation(sweep, s_band, tmp_path / "m.png")
    axes = only_axes(captured_figure)

    markers = [line for line in axes.lines if line.get_marker() == "o"]
    assert len(markers) == 1
    assert markers[0].get_xdata()[0] == pytest.approx(s_band.elevation_deg)
    assert markers[0].get_ydata()[0] == pytest.approx(11.53, abs=0.1)


def test_margin_vs_elevation_spans_horizon_to_zenith(s_band, captured_figure, tmp_path):
    plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                   tmp_path / "m.png")

    assert only_axes(captured_figure).get_xlim() == pytest.approx((0.0, 90.0))


def test_single_series_figure_has_no_legend(s_band, captured_figure, tmp_path):
    """One series needs no key; the title names it. A legend box would be noise."""
    plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                   tmp_path / "m.png")

    assert only_axes(captured_figure).get_legend() is None


# ---------------------------------------------------------------------------
# What actually gets drawn: margin vs bit rate
# ---------------------------------------------------------------------------
def test_margin_vs_bit_rate_draws_the_sweep_arrays(s_band, captured_figure, tmp_path):
    sweep = sweeps.sweep_bit_rate(s_band)
    plots.plot_margin_vs_bit_rate(sweep, s_band, tmp_path / "r.png")

    line = series_line(only_axes(captured_figure))
    assert line.get_xdata() == pytest.approx(sweep["bit_rate_bps"])
    assert line.get_ydata() == pytest.approx(sweep["margin_db"])


def test_margin_vs_bit_rate_uses_a_log_rate_axis(s_band, captured_figure, tmp_path):
    """Eb/N0 is linear in log rate, so a log axis makes margin a straight line."""
    plots.plot_margin_vs_bit_rate(sweeps.sweep_bit_rate(s_band), s_band,
                                  tmp_path / "r.png")

    assert only_axes(captured_figure).get_xscale() == "log"


def test_margin_vs_bit_rate_labels_the_closing_rate(s_band, captured_figure, tmp_path):
    """Where margin crosses zero, the rate at which the link stops closing is named."""
    plots.plot_margin_vs_bit_rate(sweeps.sweep_bit_rate(s_band), s_band,
                                  tmp_path / "r.png")
    texts = [text.get_text() for text in only_axes(captured_figure).texts]

    assert any("closes at" in text for text in texts)


def test_margin_vs_bit_rate_omits_the_label_when_there_is_no_crossing(s_band,
                                                                     captured_figure,
                                                                     tmp_path):
    """A grid that never crosses zero must not claim a crossing rate."""
    rates = np.array([1.0e3, 1.0e4, 1.0e5])               # all comfortably closing
    plots.plot_margin_vs_bit_rate(sweeps.sweep_bit_rate(s_band, rates), s_band,
                                  tmp_path / "r.png")
    texts = [text.get_text() for text in only_axes(captured_figure).texts]

    assert not any("closes at" in text for text in texts)


# ---------------------------------------------------------------------------
# What actually gets drawn: max rate vs elevation
# ---------------------------------------------------------------------------
def test_max_rate_vs_elevation_draws_megabits(s_band, captured_figure, tmp_path):
    """The axis is in Mbit/s, so the plotted values are the sweep's bit/s over 1e6."""
    sweep = sweeps.sweep_max_rate_vs_elevation(s_band)
    plots.plot_max_rate_vs_elevation(sweep, s_band, tmp_path / "x.png")

    line = series_line(only_axes(captured_figure))
    assert line.get_xdata() == pytest.approx(sweep["elevation_deg"])
    assert line.get_ydata() == pytest.approx(sweep["max_bit_rate_bps"] / 1e6)


def test_max_rate_vs_elevation_uses_a_log_rate_axis(s_band, captured_figure, tmp_path):
    plots.plot_max_rate_vs_elevation(sweeps.sweep_max_rate_vs_elevation(s_band),
                                     s_band, tmp_path / "x.png")

    assert only_axes(captured_figure).get_yscale() == "log"


def test_max_rate_vs_elevation_names_the_target_margin(s_band, captured_figure, tmp_path):
    """The rate is conditional on a margin, so the title must say which."""
    plots.plot_max_rate_vs_elevation(sweeps.sweep_max_rate_vs_elevation(s_band),
                                     s_band, tmp_path / "x.png")

    assert "3 dB margin" in only_axes(captured_figure).get_title("left")


# ---------------------------------------------------------------------------
# The files on disk
# ---------------------------------------------------------------------------
def test_plot_writes_a_real_png(s_band, tmp_path):
    """The bytes on disk must be a PNG, not an empty or truncated file."""
    path = plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                          tmp_path / "m.png")

    assert path.exists()
    assert path.read_bytes()[:8] == PNG_MAGIC
    assert path.stat().st_size > 10_000                   # a blank canvas is far smaller


def test_plot_returns_the_path_written(s_band, tmp_path):
    target = tmp_path / "m.png"
    assert plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                          target) == target


def test_plot_creates_a_missing_output_directory(s_band, tmp_path):
    """--out may name a directory that does not exist yet."""
    target = tmp_path / "new" / "nested" / "m.png"
    plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band, target)

    assert target.exists()


def test_plot_closes_its_figure(s_band, tmp_path):
    """A leaked figure is how a batch of renders quietly exhausts memory."""
    plt.close("all")
    plots.plot_margin_vs_elevation(sweeps.sweep_elevation(s_band), s_band,
                                   tmp_path / "m.png")

    assert plt.get_fignums() == []


# ---------------------------------------------------------------------------
# render_all()
# ---------------------------------------------------------------------------
def test_render_all_writes_every_figure(s_band, tmp_path):
    written = plots.render_all(s_band, tmp_path)

    assert [path.name for path in written] == [
        "margin_vs_elevation.png",
        "margin_vs_bit_rate.png",
        "max_rate_vs_elevation.png",
    ]
    for path in written:
        assert path.read_bytes()[:8] == PNG_MAGIC


def test_render_all_leaves_no_figures_open(s_band, tmp_path):
    plt.close("all")
    plots.render_all(s_band, tmp_path)

    assert plt.get_fignums() == []


def test_render_all_works_on_the_published_g_over_t_branch(s_band, tmp_path):
    """A scenario with a published G/T must plot as readily as a computed one."""
    from dataclasses import replace

    written = plots.render_all(replace(s_band, g_over_t_db_per_k=15.0), tmp_path)

    assert len(written) == 3
    for path in written:
        assert path.stat().st_size > 10_000


# ---------------------------------------------------------------------------
# The module's ground rule
# ---------------------------------------------------------------------------
def test_plots_uses_a_headless_backend():
    """Rendering must never try to open a window, on CI or anywhere else."""
    import matplotlib

    assert matplotlib.get_backend().lower() == "agg"


def test_plots_module_contains_no_physics():
    """Formulas live in link_budget.py; this module only draws what it is given."""
    source = (REPO_ROOT / "plots.py").read_text(encoding="utf-8")

    assert "log10" not in source
    assert "import link_budget" not in source
