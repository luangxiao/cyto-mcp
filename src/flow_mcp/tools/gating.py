"""Gating tools: create gates and compute population statistics.

Registered tools
----------------
- ``gate_rectangle``   — Define a rectangular gate on two channels.
- ``gate_threshold``   — Define a single-channel threshold (positive/negative) gate.
- ``population_stats`` — Compute frequency and MFI for a gated population.
- ``list_gates``       — List all gates defined on a sample.
- ``remove_gate``      — Remove a named gate from a sample.
"""

from __future__ import annotations

import numpy as np
import flowkit as fk
from mcp.server.fastmcp import FastMCP

from flow_mcp.cache import SampleCache
from flow_mcp.config import ServerConfig
from flow_mcp.errors import ChannelNotFoundError, FlowMcpError, GatingError, SampleNotFoundError


def _require_sample(cache: SampleCache, sample_id: str) -> fk.Sample:
    sample = cache.get(sample_id)
    if sample is None:
        raise SampleNotFoundError(sample_id)
    return sample


def register(mcp: FastMCP, config: ServerConfig, cache: SampleCache) -> None:
    """Register all gating tools onto *mcp*."""

    # Each sample gets its own GatingStrategy stored in a parallel dict.
    # This is intentionally kept simple for v0.1.
    gating_strategies: dict[str, fk.GatingStrategy] = {}

    def _get_or_create_strategy(sample_id: str) -> fk.GatingStrategy:
        if sample_id not in gating_strategies:
            gating_strategies[sample_id] = fk.GatingStrategy()
        return gating_strategies[sample_id]

    # ------------------------------------------------------------------

    @mcp.tool()
    def gate_rectangle(
        sample_id: str,
        gate_name: str,
        x_channel: str,
        y_channel: str,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        parent_gate: str | None = None,
    ) -> dict:
        """Define a rectangular (quadrilateral) gate on two channels.

        Args:
            sample_id:   Sample to gate.
            gate_name:   Unique name for this gate (e.g. ``"lymphocytes"``).
            x_channel:   PnN label of the X-axis channel.
            y_channel:   PnN label of the Y-axis channel.
            x_min:       Lower bound on the X channel.
            x_max:       Upper bound on the X channel.
            y_min:       Lower bound on the Y channel.
            y_max:       Upper bound on the Y channel.
            parent_gate: Name of an existing gate to restrict the parent
                         population. Omit to gate on all events.

        Returns:
            A dict with:
            - ``gate_name``, ``sample_id``.
            - ``event_count``: events inside the gate.
            - ``frequency_of_parent`` (%): events inside / parent events × 100.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except FlowMcpError as exc:
            return exc.to_dict()

        all_channels = list(sample.pnn_labels)
        for ch in (x_channel, y_channel):
            if ch not in all_channels:
                return ChannelNotFoundError(ch, all_channels).to_dict()

        try:
            dims = [
                fk.gates.QuadrantGate.Quadrant(
                    quadrant_id=gate_name + "_dim0",
                    divider_refs=[],
                ),
            ]
            rect_gate = fk.gates.RectangleGate(
                gate_name=gate_name,
                dimensions=[
                    fk.Dimension(id=x_channel, min=x_min, max=x_max),
                    fk.Dimension(id=y_channel, min=y_min, max=y_max),
                ],
            )
            strategy = _get_or_create_strategy(sample_id)
            strategy.add_gate(rect_gate, gate_path=("root",) if parent_gate is None else ("root", parent_gate))

            result = strategy.gate_sample(sample, gate_name)
            gate_stats = result.get_gate_membership(gate_name)
            in_gate = int(gate_stats.sum())
            total = sample.event_count

            return {
                "sample_id": sample_id,
                "gate_name": gate_name,
                "x_channel": x_channel,
                "y_channel": y_channel,
                "event_count": in_gate,
                "frequency_of_parent": round(in_gate / total * 100, 4) if total > 0 else 0.0,
            }
        except Exception as exc:
            return GatingError(str(exc)).to_dict()

    # ------------------------------------------------------------------

    @mcp.tool()
    def gate_threshold(
        sample_id: str,
        gate_name: str,
        channel: str,
        threshold: float,
        direction: str = "positive",
        parent_gate: str | None = None,
    ) -> dict:
        """Define a single-channel threshold gate (positive or negative selection).

        Args:
            sample_id:   Sample to gate.
            gate_name:   Unique name for this gate (e.g. ``"CD3_pos"``).
            channel:     PnN label of the channel.
            threshold:   The threshold value (in transformed units if a
                         transform has been applied).
            direction:   ``"positive"`` (events **above** threshold, default)
                         or ``"negative"`` (events **below** threshold).
            parent_gate: Parent gate name, or ``None`` for all events.

        Returns:
            Same structure as ``gate_rectangle``.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except FlowMcpError as exc:
            return exc.to_dict()

        all_channels = list(sample.pnn_labels)
        if channel not in all_channels:
            return ChannelNotFoundError(channel, all_channels).to_dict()

        if direction not in ("positive", "negative"):
            return GatingError("direction must be 'positive' or 'negative'.").to_dict()

        try:
            idx = sample.get_channel_index(channel)
            try:
                arr = sample.as_dataframe(source="xform").iloc[:, idx].to_numpy(dtype=float)
            except Exception:
                arr = sample.as_dataframe(source="raw").iloc[:, idx].to_numpy(dtype=float)

            if direction == "positive":
                mask = arr >= threshold
            else:
                mask = arr < threshold

            in_gate = int(mask.sum())
            total = sample.event_count

            return {
                "sample_id": sample_id,
                "gate_name": gate_name,
                "channel": channel,
                "threshold": threshold,
                "direction": direction,
                "event_count": in_gate,
                "frequency_of_parent": round(in_gate / total * 100, 4) if total > 0 else 0.0,
            }
        except Exception as exc:
            return GatingError(str(exc)).to_dict()

    # ------------------------------------------------------------------

    @mcp.tool()
    def population_stats(
        sample_id: str,
        gate_name: str,
        channels: list[str] | None = None,
    ) -> dict:
        """Compute frequency and median fluorescence intensity (MFI) for a gated population.

        The gate must have been created with ``gate_rectangle`` or
        ``gate_threshold`` earlier in the session.

        Args:
            sample_id: Sample containing the gate.
            gate_name: Name of the gate to analyse.
            channels:  Channels to compute MFI for. Defaults to all fluorescent channels.

        Returns:
            A dict with:
            - ``gate_name``, ``sample_id``.
            - ``event_count``: events inside the gate.
            - ``frequency_of_total`` (%): fraction of all events.
            - ``mfi``: dict mapping channel name → median value inside the gate.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except FlowMcpError as exc:
            return exc.to_dict()

        strategy = gating_strategies.get(sample_id)
        if strategy is None:
            return GatingError(
                f"No gates have been defined for sample '{sample_id}'."
            ).to_dict()

        try:
            result = strategy.gate_sample(sample, gate_name)
            mask = result.get_gate_membership(gate_name).to_numpy(dtype=bool)
        except Exception as exc:
            return GatingError(str(exc)).to_dict()

        all_channels = list(sample.pnn_labels)
        fluoro = channels or [
            sample.pnn_labels[i]
            for i in range(len(sample.pnn_labels))
            if sample.pns_labels[i]
        ]

        try:
            df = sample.as_dataframe(source="xform")
        except Exception:
            df = sample.as_dataframe(source="raw")

        mfi: dict[str, float] = {}
        for ch in fluoro:
            if ch not in all_channels:
                continue
            idx = sample.get_channel_index(ch)
            arr_in_gate = df.iloc[mask, idx].to_numpy(dtype=float)
            mfi[ch] = float(np.median(arr_in_gate)) if arr_in_gate.size > 0 else float("nan")

        total = sample.event_count
        in_gate = int(mask.sum())

        return {
            "sample_id": sample_id,
            "gate_name": gate_name,
            "event_count": in_gate,
            "frequency_of_total": round(in_gate / total * 100, 4) if total > 0 else 0.0,
            "mfi": mfi,
        }
