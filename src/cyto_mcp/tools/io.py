"""Tools for FCS file discovery, loading, and validation.

Registered tools
----------------
- ``list_fcs``      — Enumerate FCS files in the data directory.
- ``load_fcs``      — Load a single FCS file into the sample cache.
- ``fcs_keywords``  — Retrieve raw FCS keyword/value pairs from a file.
- ``validate_fcs``  — Check whether a file is a valid FCS 2.0/3.0/3.1 file.
- ``unload_fcs``    — Evict a sample from the cache to free memory.
- ``cached_samples``— List all currently cached sample IDs.
"""

from __future__ import annotations

from pathlib import Path

import flowkit as fk
from mcp.server.fastmcp import FastMCP

from cyto_mcp.cache import SampleCache
from cyto_mcp.config import ServerConfig
from cyto_mcp.errors import CytoMcpError, UnsupportedFormatError
from cyto_mcp.utils.paths import resolve_data_path


def register(mcp: FastMCP, config: ServerConfig, cache: SampleCache) -> None:
    """Register all I/O tools onto *mcp*."""

    @mcp.tool()
    def list_fcs(subdirectory: str = "") -> dict:
        """List FCS files available in the data directory.

        Args:
            subdirectory: Optional sub-path within the data directory to scan.
                          Defaults to the data directory root.

        Returns:
            A dict with:
            - ``files``: list of relative file paths (str) found.
            - ``count``: total number of files found.
        """
        try:
            scan_root = resolve_data_path(subdirectory, config.data_dir) if subdirectory else config.data_dir
        except CytoMcpError as exc:
            return exc.to_dict()

        if not scan_root.is_dir():
            return {"error": "DirectoryNotFound", "message": f"'{subdirectory}' is not a directory."}

        fcs_files = sorted(scan_root.rglob("*.fcs"))
        relative = [str(f.relative_to(config.data_dir)) for f in fcs_files]
        return {"files": relative, "count": len(relative)}

    # ------------------------------------------------------------------

    @mcp.tool()
    def load_fcs(path: str) -> dict:
        """Load an FCS file and cache it for subsequent analysis.

        The file is identified by a path **relative to the server's data
        directory** (e.g. ``"experiment1/sample_001.fcs"``).

        Args:
            path: Relative path to the FCS file within the data directory.

        Returns:
            A dict with:
            - ``sample_id``: identifier to use in subsequent tool calls.
            - ``event_count``: number of recorded events (cells).
            - ``channels``: list of detector names (PnN keywords).
            - ``fluorophores``: list of fluorophore/marker names (PnS keywords).
            - ``acquisition_date``: value of the ``$DATE`` keyword if present.
            - ``cytometer``: value of the ``$CYT`` keyword if present.
        """
        try:
            abs_path = resolve_data_path(path, config.data_dir)
        except CytoMcpError as exc:
            return exc.to_dict()

        if not abs_path.is_file():
            return UnsupportedFormatError(path, "File not found.").to_dict()

        try:
            sample = fk.Sample(abs_path)
        except Exception as exc:
            return UnsupportedFormatError(path, str(exc)).to_dict()

        # Build a unique sample_id from the relative path so that files with the
        # same stem in different subdirectories don't silently collide in the cache.
        # e.g. "dir1/a.fcs" → "dir1__a", "a.fcs" → "a".
        rel = Path(path).with_suffix("")
        sample_id = "__".join(rel.parts) if rel.parts else rel.stem
        cache.put(sample_id, sample)

        channels = [sample.pnn_labels[i] for i in range(len(sample.pnn_labels))]
        fluorophores = [sample.pns_labels[i] for i in range(len(sample.pns_labels))]

        metadata = sample.metadata
        return {
            "sample_id": sample_id,
            "event_count": sample.event_count,
            "channels": channels,
            "fluorophores": fluorophores,
            "acquisition_date": metadata.get("$DATE", ""),
            "cytometer": metadata.get("$CYT", ""),
            "tube_name": metadata.get("TUBE NAME", metadata.get("$SMNO", "")),
        }

    # ------------------------------------------------------------------

    @mcp.tool()
    def fcs_keywords(path: str, keywords: list[str] | None = None) -> dict:
        """Return FCS keyword/value pairs from a file without fully loading it.

        Useful for quickly inspecting metadata (panel, dates, cytometer settings)
        without occupying cache space.

        Args:
            path: Relative path to the FCS file within the data directory.
            keywords: Optional list of specific keywords to retrieve.
                      If omitted, all keywords are returned.

        Returns:
            A dict mapping keyword names to their values, plus an ``error``
            key if the file cannot be read.
        """
        try:
            abs_path = resolve_data_path(path, config.data_dir)
        except CytoMcpError as exc:
            return exc.to_dict()

        if not abs_path.is_file():
            return UnsupportedFormatError(path, "File not found.").to_dict()

        try:
            sample = fk.Sample(abs_path)
        except Exception as exc:
            return UnsupportedFormatError(path, str(exc)).to_dict()

        all_kw: dict[str, str] = sample.metadata
        if keywords:
            result = {k: all_kw.get(k, "") for k in keywords}
        else:
            result = dict(all_kw)
        return result

    # ------------------------------------------------------------------

    @mcp.tool()
    def validate_fcs(path: str) -> dict:
        """Check whether a file is a readable FCS file.

        Args:
            path: Relative path to the FCS file within the data directory.

        Returns:
            A dict with:
            - ``valid`` (bool): whether the file passed validation.
            - ``version``: FCS version string (e.g. ``"FCS3.1"``).
            - ``event_count``: number of events if valid.
            - ``issues``: list of problem descriptions (empty if valid).
        """
        try:
            abs_path = resolve_data_path(path, config.data_dir)
        except CytoMcpError as exc:
            return {"valid": False, "issues": [str(exc)]}

        if not abs_path.is_file():
            return {"valid": False, "issues": [f"File not found: {path}"]}

        issues: list[str] = []
        try:
            sample = fk.Sample(abs_path)
            version = sample.metadata.get("$FCSversion", "unknown")
            return {
                "valid": True,
                "version": version,
                "event_count": sample.event_count,
                "issues": issues,
            }
        except Exception as exc:
            return {"valid": False, "issues": [str(exc)]}

    # ------------------------------------------------------------------

    @mcp.tool()
    def unload_fcs(sample_id: str) -> dict:
        """Evict a sample from the in-memory cache to free RAM.

        The FCS file is not deleted from disk. You can reload the sample
        at any time with ``load_fcs``.

        Args:
            sample_id: The sample identifier returned by ``load_fcs``.

        Returns:
            A dict with ``evicted`` (bool) indicating whether the sample
            was found in the cache.
        """
        evicted = cache.evict(sample_id)
        return {"evicted": evicted, "sample_id": sample_id}

    # ------------------------------------------------------------------

    @mcp.tool()
    def cached_samples() -> dict:
        """List all sample IDs currently held in memory.

        Returns:
            A dict with:
            - ``samples``: list of cached sample IDs.
            - ``count``: number of samples in cache.
            - ``capacity``: maximum cache size.
        """
        return {
            "samples": cache.sample_ids,
            "count": len(cache),
            "capacity": config.cache_size,
        }
