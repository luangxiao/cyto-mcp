"""Statistics tools: per-channel summaries and cross-sample comparisons.

Registered tools
----------------
- ``channel_stats``     — Percentile statistics for one or more channels.
- ``compare_samples``   — Compare MFI / frequency across multiple samples.
"""

from __future__ import annotations

import numpy as np
import flowkit as fk
from mcp.server.fastmcp import FastMCP

from cyto_mcp.cache import SampleCache
from cyto_mcp.config import ServerConfig
from cyto_mcp.errors import ChannelNotFoundError, CytoMcpError, SampleNotFoundError


def _require_sample(cache: SampleCache, sample_id: str) -> fk.Sample:
    sample = cache.get(sample_id)
    if sample is None:
        raise SampleNotFoundError(sample_id)
    return sample


def _channel_array(sample: fk.Sample, channel: str, source: str = "xform") -> np.ndarray:
    """Return the event array for *channel*, falling back to 'raw' if xform unavailable."""
    all_channels = list(sample.pnn_labels)
    if channel not in all_channels:
        raise ChannelNotFoundError(channel, all_channels)
    idx = sample.get_channel_index(channel)
    try:
        df = sample.as_dataframe(source=source)
    except Exception:
        df = sample.as_dataframe(source="raw")
    return df.iloc[:, idx].to_numpy(dtype=float)


def register(mcp: FastMCP, config: ServerConfig, cache: SampleCache) -> None:
    """Register all statistics tools onto *mcp*."""

    @mcp.tool()
    def channel_stats(
        sample_id: str,
        channels: list[str] | None = None,
        source: str = "xform",
        percentiles: list[float] | None = None,
    ) -> dict:
        """Return descriptive statistics for one or more channels.

        Args:
            sample_id:   Sample to analyse (must be loaded).
            channels:    Channel names (PnN) to summarise. Defaults to all channels.
            source:      Which event data to use: ``"xform"`` (transformed, default),
                         ``"comp"`` (compensated only), or ``"raw"``.
            percentiles: Percentile values to compute (0–100). Defaults to
                         ``[1, 5, 25, 50, 75, 95, 99]``.

        Returns:
            A dict with a ``stats`` key mapping each channel name to its
            statistics (mean, std, min, max, and the requested percentiles).
        """
        try:
            sample = _require_sample(cache, sample_id)
        except CytoMcpError as exc:
            return exc.to_dict()

        target = channels if channels is not None else list(sample.pnn_labels)
        pcts = percentiles if percentiles is not None else [1, 5, 25, 50, 75, 95, 99]

        stats: dict[str, dict] = {}
        for ch in target:
            try:
                arr = _channel_array(sample, ch, source)
            except CytoMcpError as exc:
                stats[ch] = exc.to_dict()
                continue

            pct_values = np.percentile(arr, pcts).tolist()
            stats[ch] = {
                "n": int(arr.size),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(arr.min()),
                "max": float(arr.max()),
                "percentiles": {str(int(p)): float(v) for p, v in zip(pcts, pct_values)},
            }

        return {"sample_id": sample_id, "source": source, "stats": stats}

    # ------------------------------------------------------------------

    @mcp.tool()
    def compare_samples(
        sample_ids: list[str],
        channels: list[str],
        metric: str = "median",
        source: str = "xform",
    ) -> dict:
        """Compare a statistic across multiple samples for a set of channels.

        Useful for spotting batch effects or treatment differences before
        formal statistical analysis.

        Args:
            sample_ids: List of sample IDs to compare (all must be loaded).
            channels:   Channel names (PnN) to include in the comparison.
            metric:     Summary statistic to compare. One of:
                        ``"median"`` (default), ``"mean"``, ``"cv"``
                        (coefficient of variation), ``"p95"``.
            source:     Event data source: ``"xform"``, ``"comp"``, or ``"raw"``.

        Returns:
            A dict with a ``table`` key — a list of rows, each row being a
            dict of ``{sample_id, channel, value}``. Also includes a
            ``pivot`` dict keyed by channel → {sample_id → value} for easy
            reading.
        """
        rows: list[dict] = []
        errors: list[str] = []
        pivot: dict[str, dict[str, float]] = {ch: {} for ch in channels}

        for sid in sample_ids:
            sample = cache.get(sid)
            if sample is None:
                errors.append(f"Sample '{sid}' is not loaded.")
                continue

            for ch in channels:
                try:
                    arr = _channel_array(sample, ch, source)
                except CytoMcpError as exc:
                    errors.append(str(exc))
                    continue

                if metric == "median":
                    value = float(np.median(arr))
                elif metric == "mean":
                    value = float(np.mean(arr))
                elif metric == "cv":
                    mean = np.mean(arr)
                    value = float(np.std(arr) / mean * 100) if mean != 0 else float("nan")
                elif metric == "p95":
                    value = float(np.percentile(arr, 95))
                else:
                    return {
                        "error": "UnsupportedMetric",
                        "message": f"Unknown metric '{metric}'. "
                                   "Choose from: median, mean, cv, p95.",
                    }

                rows.append({"sample_id": sid, "channel": ch, "value": value})
                pivot[ch][sid] = value

        result: dict = {"metric": metric, "source": source, "table": rows, "pivot": pivot}
        if errors:
            result["warnings"] = errors
        return result
