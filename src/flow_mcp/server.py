"""MCP server assembly.

This module creates the :class:`~mcp.server.fastmcp.FastMCP` instance,
applies configuration, instantiates the sample cache, and registers every
tool module. It is imported by the CLI entry point (``cli.py``) and can
also be imported directly for testing.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from flow_mcp import __version__
from flow_mcp.cache import SampleCache
from flow_mcp.config import ServerConfig
from flow_mcp.tools import gating, io, plots, preprocess, stats


def create_server(config: ServerConfig) -> FastMCP:
    """Instantiate and configure the MCP server.

    Args:
        config: Runtime configuration (paths, cache size, render settings).

    Returns:
        A fully wired :class:`~mcp.server.fastmcp.FastMCP` instance ready to
        be run via :meth:`~mcp.server.fastmcp.FastMCP.run`.
    """
    # Ensure the output directory exists
    config.output_dir.mkdir(parents=True, exist_ok=True)

    mcp = FastMCP(
        name="cyto-mcp",
        instructions=(
            "You are connected to cyto-mcp, an MCP server for flow cytometry analysis. "
            "All FCS files are stored on the user's local machine — data never leaves their device. "
            "\n\n"
            "Typical workflow:\n"
            "1. Call `list_fcs` to discover available files.\n"
            "2. Call `load_fcs` to load a file into the cache (returns sample_id).\n"
            "3. Optionally call `apply_compensation` and `transform` to pre-process.\n"
            "4. Call `channel_stats` or `scatter_plot` / `histogram` to explore the data.\n"
            "5. Call `gate_rectangle` or `gate_threshold` to define populations.\n"
            "6. Call `population_stats` to get frequency and MFI for each gate.\n"
            "\n"
            "Important notes:\n"
            "- When a plot tool returns a `summary` dict alongside the image, prefer the "
            "structured numbers for quantitative reasoning rather than estimating from pixels.\n"
            "- Large files take a few seconds to load; call `subsample` for fast exploration.\n"
            "- Use `unload_fcs` to free memory when you are done with a sample.\n"
        ),
    )

    cache = SampleCache(max_size=config.cache_size)

    # Register each tool module
    io.register(mcp, config, cache)
    preprocess.register(mcp, config, cache)
    stats.register(mcp, config, cache)
    gating.register(mcp, config, cache)
    plots.register(mcp, config, cache)

    return mcp
