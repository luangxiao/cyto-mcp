"""Preprocessing tools: compensation and transformation.

Registered tools
----------------
- ``apply_compensation`` — Apply a spillover/compensation matrix.
- ``transform``          — Apply a channel transformation (Logicle, asinh, biexp, linear).
- ``subsample``          — Down-sample events for fast exploratory analysis.
"""

from __future__ import annotations

import numpy as np
import flowkit as fk
from mcp.server.fastmcp import FastMCP

from cyto_mcp.cache import SampleCache
from cyto_mcp.config import ServerConfig
from cyto_mcp.errors import (
    ChannelNotFoundError,
    CompensationError,
    CytoMcpError,
    SampleNotFoundError,
)
from cyto_mcp.utils.paths import resolve_data_path


def _require_sample(cache: SampleCache, sample_id: str) -> fk.Sample:
    """Return the cached sample or raise :class:`SampleNotFoundError`."""
    sample = cache.get(sample_id)
    if sample is None:
        raise SampleNotFoundError(sample_id)
    return sample


def register(mcp: FastMCP, config: ServerConfig, cache: SampleCache) -> None:
    """Register all preprocessing tools onto *mcp*."""

    @mcp.tool()
    def apply_compensation(
        sample_id: str,
        matrix: list[list[float]] | None = None,
        matrix_name: str = "$SPILL",
    ) -> dict:
        """Apply a compensation (spillover) matrix to a loaded sample.

        If *matrix* is omitted, the matrix stored under *matrix_name* in the
        FCS file's own metadata is used (most instruments write ``$SPILL`` or
        ``SPILL``).

        Args:
            sample_id:   Sample to compensate.
            matrix:      Optional 2-D spillover matrix (rows = detectors,
                         cols = fluorophores). Must be square and match the
                         number of fluorescent channels.
            matrix_name: Which built-in matrix key to fall back to when
                         *matrix* is not provided. Common values:
                         ``"$SPILL"``, ``"SPILL"``, ``"$COMP"``.

        Returns:
            A dict with:
            - ``sample_id``: echoed back.
            - ``compensated``: ``True`` on success.
            - ``matrix_source``: ``"provided"`` or the keyword used.
            - ``channels``: list of compensated channel names.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except CytoMcpError as exc:
            return exc.to_dict()

        try:
            if matrix is not None:
                np_matrix = np.array(matrix, dtype=float)
                fluoro_channels = [
                    sample.pnn_labels[i]
                    for i in range(len(sample.pnn_labels))
                    if sample.pns_labels[i]  # channels that have a fluorophore label
                ]
                comp = fk.Matrix(
                    matrix_id="user_provided",
                    spill_data_or_file=np_matrix,
                    detectors=fluoro_channels,
                    fluorochromes=fluoro_channels,
                )
                source = "provided"
            else:
                comp = sample.get_compensation_matrix(matrix_name)
                source = matrix_name
                if comp is None:
                    return CompensationError(
                        f"No compensation matrix found under key '{matrix_name}'. "
                        "Try providing a matrix explicitly."
                    ).to_dict()

            sample.apply_compensation(comp)
            cache.put(sample_id, sample)  # refresh cache entry
            return {
                "sample_id": sample_id,
                "compensated": True,
                "matrix_source": source,
                "channels": comp.detectors,
            }
        except Exception as exc:
            return CompensationError(str(exc)).to_dict()

    # ------------------------------------------------------------------

    @mcp.tool()
    def transform(
        sample_id: str,
        method: str = "logicle",
        channels: list[str] | None = None,
        # asinh params
        asinh_cofactor: float = 150.0,
        # logicle params
        logicle_t: float = 262144.0,
        logicle_w: float = 0.5,
        logicle_m: float = 4.5,
        logicle_a: float = 0.0,
    ) -> dict:
        """Apply a channel transformation to a loaded sample.

        Transformations are a prerequisite for meaningful gating and
        visualisation of fluorescence data.

        Args:
            sample_id:       Sample to transform.
            method:          One of ``"logicle"`` (default), ``"asinh"``,
                             ``"biexponential"``, ``"linear"``, ``"log"``.
            channels:        Channel names (PnN) to transform. Defaults to
                             all fluorescent channels (those with a PnS label).
            asinh_cofactor:  Cofactor for the asinh transform: ``asinh(x / cofactor)``.
            logicle_t:       Logicle *T* parameter (top of scale).
            logicle_w:       Logicle *W* parameter (width of linearisation).
            logicle_m:       Logicle *M* parameter (decades).
            logicle_a:       Logicle *A* parameter (additional negative decades).

        Returns:
            A dict with:
            - ``sample_id``: echoed back.
            - ``method``: transformation method applied.
            - ``transformed_channels``: list of channel names that were transformed.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except CytoMcpError as exc:
            return exc.to_dict()

        # Determine target channels
        all_channels = list(sample.pnn_labels)
        fluoro_channels = [
            sample.pnn_labels[i]
            for i in range(len(sample.pnn_labels))
            if sample.pns_labels[i]
        ]
        target = channels if channels is not None else fluoro_channels

        # Validate channel names
        invalid = [c for c in target if c not in all_channels]
        if invalid:
            return ChannelNotFoundError(invalid[0], all_channels).to_dict()

        channel_indices = [sample.get_channel_index(c) for c in target]

        try:
            method_lower = method.lower()
            if method_lower == "logicle":
                xform = fk.transforms.LogicleTransform(
                    transform_id="logicle",
                    param_t=logicle_t,
                    param_w=logicle_w,
                    param_m=logicle_m,
                    param_a=logicle_a,
                )
            elif method_lower == "asinh":
                xform = fk.transforms.AsinhTransform(
                    transform_id="asinh",
                    param_t=logicle_t,
                    param_m=logicle_m,
                    param_a=asinh_cofactor,
                )
            elif method_lower in ("log", "logarithmic"):
                xform = fk.transforms.LogTransform(
                    transform_id="log",
                    param_t=logicle_t,
                    param_m=logicle_m,
                )
            elif method_lower == "linear":
                xform = fk.transforms.LinearTransform(
                    transform_id="linear",
                    param_t=logicle_t,
                    param_a=0.0,
                )
            elif method_lower in ("biexponential", "biexp"):
                xform = fk.transforms.WSPBiexTransform(
                    transform_id="biexp",
                )
            else:
                return {
                    "error": "UnsupportedTransform",
                    "message": f"Unknown method '{method}'. "
                               "Choose from: logicle, asinh, log, linear, biexponential.",
                }

            sample.apply_transform({c: xform for c in target})
            cache.put(sample_id, sample)

            return {
                "sample_id": sample_id,
                "method": method,
                "transformed_channels": target,
            }
        except Exception as exc:
            return {"error": "TransformError", "message": str(exc)}

    # ------------------------------------------------------------------

    @mcp.tool()
    def subsample(
        sample_id: str,
        n: int = 50_000,
        seed: int = 42,
        new_sample_id: str | None = None,
    ) -> dict:
        """Down-sample a loaded FCS file to at most *n* events.

        The result is stored in the cache under *new_sample_id* (or
        ``{sample_id}_sub{n}`` if not specified). The original sample is
        not modified.

        This is useful for fast exploratory analysis with the LLM before
        committing to full-data processing.

        Args:
            sample_id:     Source sample to down-sample.
            n:             Target number of events (default 50 000).
            seed:          Random seed for reproducibility.
            new_sample_id: Cache key for the sub-sampled result.

        Returns:
            A dict with:
            - ``source_sample_id``: original sample.
            - ``new_sample_id``:    cache key for the sub-sampled copy.
            - ``original_events``:  event count before sub-sampling.
            - ``sampled_events``:   event count after sub-sampling.
            - ``downsampled``:      ``False`` if the sample already had ≤ *n* events.
        """
        try:
            sample = _require_sample(cache, sample_id)
        except CytoMcpError as exc:
            return exc.to_dict()

        original_count = sample.event_count
        sid_out = new_sample_id or f"{sample_id}_sub{n}"

        if original_count <= n:
            cache.put(sid_out, sample)
            return {
                "source_sample_id": sample_id,
                "new_sample_id": sid_out,
                "original_events": original_count,
                "sampled_events": original_count,
                "downsampled": False,
            }

        rng = np.random.default_rng(seed)
        indices = rng.choice(original_count, size=n, replace=False)
        sub = sample.as_dataframe(source="raw").iloc[sorted(indices)]

        # Build a new FlowKit sample from the sub-sampled data.
        # FlowKit accepts a DataFrame constructor for in-memory samples.
        new_sample = fk.Sample(
            fcs_path_or_data=sub,
            channel_labels=list(sample.pnn_labels),
        )
        cache.put(sid_out, new_sample)

        return {
            "source_sample_id": sample_id,
            "new_sample_id": sid_out,
            "original_events": original_count,
            "sampled_events": n,
            "downsampled": True,
        }
