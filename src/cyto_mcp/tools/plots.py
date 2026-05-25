"""Visualisation tools: scatter plots, histograms, and density plots.

Design — dual return
--------------------
Every plot tool returns **both**:

1. A rendered PNG image (for the human to inspect visually).
2. A structured JSON ``summary`` (for the LLM to reason about numerically —
   peak positions, suggested gates, percentages, etc.).

The PNG is also written to ``--output-dir/<sample_id>/`` so it can be
re-referenced later without re-rendering.

Registered tools
----------------
- ``scatter_plot``   — 2-D dot / density scatter of two channels.
- ``histogram``      — 1-D histogram of a single channel.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; must be set before importing pyplot
import matplotlib.pyplot as plt
import numpy as np
import flowkit as fk
from mcp.server.fastmcp import FastMCP, Image

from cyto_mcp.cache import SampleCache
from cyto_mcp.config import ServerConfig
from cyto_mcp.errors import ChannelNotFoundError, CytoMcpError, SampleNotFoundError
from cyto_mcp.utils.image import figure_to_png
from cyto_mcp.utils.paths import make_output_path

# Characters that are illegal in filenames on Windows (also covers POSIX safely).
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _safe_filename(name: str) -> str:
    """Return *name* with characters illegal in filenames replaced by ``_``."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", name).strip(". ")
    return cleaned or "plot"


def _require_sample(cache: SampleCache, sample_id: str) -> fk.Sample:
    sample = cache.get(sample_id)
    if sample is None:
        raise SampleNotFoundError(sample_id)
    return sample


def _get_channel_data(
    sample: fk.Sample,
    channel: str,
    source: str,
    max_events: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return event data for *channel*, optionally down-sampled to *max_events*."""
    all_channels = list(sample.pnn_labels)
    if channel not in all_channels:
        raise ChannelNotFoundError(channel, all_channels)
    idx = sample.get_channel_index(channel)
    try:
        df = sample.as_dataframe(source=source)
    except Exception:
        df = sample.as_dataframe(source="raw")

    arr = df.iloc[:, idx].to_numpy(dtype=float)
    if arr.size > max_events:
        indices = rng.choice(arr.size, size=max_events, replace=False)
        arr = arr[np.sort(indices)]
    return arr


def register(mcp: FastMCP, config: ServerConfig, cache: SampleCache) -> None:
    """Register all visualisation tools onto *mcp*."""

    @mcp.tool()
    def scatter_plot(
        sample_id: str,
        x_channel: str,
        y_channel: str,
        source: str = "xform",
        color_channel: str | None = None,
        alpha: float = 0.3,
        point_size: float = 1.0,
        title: str | None = None,
    ) -> Any:
        """Render a 2-D scatter plot of two channels.

        The PNG is returned inline (for immediate display in the AI client)
        and also saved to the output directory for later reference.

        Along with the image, a structured ``summary`` is returned so the
        LLM can reason numerically without relying on pixel-level image
        understanding.

        Args:
            sample_id:     Sample to plot (must be loaded).
            x_channel:     PnN label of the X-axis channel.
            y_channel:     PnN label of the Y-axis channel.
            source:        Event data to use: ``"xform"`` (default), ``"comp"``, ``"raw"``.
            color_channel: Optional third channel used to colour-code events by intensity.
            alpha:         Point transparency (0 = invisible, 1 = opaque). Default 0.3.
            point_size:    Marker size in points. Default 1.0.
            title:         Custom plot title. Defaults to ``"<x> vs <y>"``

        Returns:
            A dict with:
            - ``image``: PNG rendered inline.
            - ``output_path``: relative path of the saved PNG.
            - ``summary``: structured dict with event count, axis ranges, and
              estimated density peak positions.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except CytoMcpError as exc:
            return exc.to_dict()

        rng = np.random.default_rng(42)
        try:
            x_arr = _get_channel_data(sample, x_channel, source, config.plot_max_events, rng)
            y_arr = _get_channel_data(sample, y_channel, source, config.plot_max_events, rng)
        except CytoMcpError as exc:
            return exc.to_dict()

        # Align lengths in case channels have different missing-value counts
        n = min(len(x_arr), len(y_arr))
        x_arr, y_arr = x_arr[:n], y_arr[:n]

        # ---- Build figure ----
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.set_xlabel(x_channel)
        ax.set_ylabel(y_channel)
        ax.set_title(title or f"{x_channel} vs {y_channel} — {sample_id}")

        if color_channel:
            try:
                c_arr = _get_channel_data(sample, color_channel, source, config.plot_max_events, rng)[:n]
                sc = ax.scatter(x_arr, y_arr, c=c_arr, s=point_size, alpha=alpha,
                                cmap="viridis", rasterized=True)
                fig.colorbar(sc, ax=ax, label=color_channel)
            except CytoMcpError:
                ax.scatter(x_arr, y_arr, s=point_size, alpha=alpha, color="steelblue",
                           rasterized=True)
        else:
            ax.scatter(x_arr, y_arr, s=point_size, alpha=alpha, color="steelblue",
                       rasterized=True)

        fig.tight_layout()

        # ---- Persist PNG ----
        filename = _safe_filename(f"scatter_{x_channel}_{y_channel}") + ".png"
        out_path = make_output_path(config.output_dir, sample_id, filename)
        png_bytes = figure_to_png(fig, dpi=config.plot_dpi)
        out_path.write_bytes(png_bytes)

        # ---- Build LLM-readable summary ----
        summary = {
            "plotted_events": n,
            "x_channel": x_channel,
            "y_channel": y_channel,
            "x_range": [round(float(x_arr.min()), 4), round(float(x_arr.max()), 4)],
            "y_range": [round(float(y_arr.min()), 4), round(float(y_arr.max()), 4)],
            "x_median": round(float(np.median(x_arr)), 4),
            "y_median": round(float(np.median(y_arr)), 4),
            "x_p5": round(float(np.percentile(x_arr, 5)), 4),
            "x_p95": round(float(np.percentile(x_arr, 95)), 4),
            "y_p5": round(float(np.percentile(y_arr, 5)), 4),
            "y_p95": round(float(np.percentile(y_arr, 95)), 4),
        }

        # FastMCP converts a list into a multi-part response:
        # the Image becomes an image content block (displayed to the user),
        # the JSON string becomes a text content block (readable by the LLM).
        summary["output_path"] = str(out_path.relative_to(config.output_dir))
        return [Image(data=png_bytes, format="png"), json.dumps(summary, indent=2)]

    # ------------------------------------------------------------------

    @mcp.tool()
    def histogram(
        sample_id: str,
        channel: str,
        source: str = "xform",
        bins: int = 256,
        overlay_sample_ids: list[str] | None = None,
        title: str | None = None,
    ) -> Any:
        """Render a 1-D histogram of a single channel.

        Optionally overlays histograms from multiple samples on the same axes,
        useful for comparing distributions across conditions or time points.

        Args:
            sample_id:          Primary sample to plot.
            channel:            PnN label of the channel to histogram.
            source:             Event data source: ``"xform"``, ``"comp"``, or ``"raw"``.
            bins:               Number of histogram bins (default 256).
            overlay_sample_ids: Additional sample IDs to overlay. All must be loaded.
            title:              Custom plot title.

        Returns:
            Same structure as ``scatter_plot`` (image + output_path + summary).
            ``summary`` includes peak positions and bin statistics per sample.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except CytoMcpError as exc:
            return exc.to_dict()

        rng = np.random.default_rng(42)

        samples_to_plot: list[tuple[str, fk.Sample]] = [(sample_id, sample)]
        if overlay_sample_ids:
            for sid in overlay_sample_ids:
                s = cache.get(sid)
                if s is not None:
                    samples_to_plot.append((sid, s))

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.set_xlabel(channel)
        ax.set_ylabel("Count")
        ax.set_title(title or f"{channel} — {sample_id}")

        summaries: dict[str, dict] = {}
        for sid, s in samples_to_plot:
            try:
                arr = _get_channel_data(s, channel, source, config.plot_max_events, rng)
            except CytoMcpError:
                continue

            counts, edges = np.histogram(arr, bins=bins)
            ax.stairs(counts, edges, label=sid, alpha=0.75)

            peak_bin = int(np.argmax(counts))
            peak_x = float((edges[peak_bin] + edges[peak_bin + 1]) / 2)
            summaries[sid] = {
                "n": int(arr.size),
                "median": round(float(np.median(arr)), 4),
                "mean": round(float(np.mean(arr)), 4),
                "peak_x": round(peak_x, 4),
                "peak_count": int(counts[peak_bin]),
            }

        if len(samples_to_plot) > 1:
            ax.legend(fontsize=8)
        fig.tight_layout()

        filename = _safe_filename(f"histogram_{channel}") + ".png"
        out_path = make_output_path(config.output_dir, sample_id, filename)
        png_bytes = figure_to_png(fig, dpi=config.plot_dpi)
        out_path.write_bytes(png_bytes)

        summary = {
            "channel": channel,
            "bins": bins,
            "output_path": str(out_path.relative_to(config.output_dir)),
            "per_sample": summaries,
        }
        return [Image(data=png_bytes, format="png"), json.dumps(summary, indent=2)]
