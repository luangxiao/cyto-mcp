"""Tests for tools/stats.py."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from flow_mcp.tools import io, stats


def _setup(server_config, cache):
    mcp = FastMCP("test")
    io.register(mcp, server_config, cache)
    stats.register(mcp, server_config, cache)
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    tools["load_fcs"](path="sample_001.fcs")
    tools["load_fcs"](path="sample_002.fcs")
    return tools


def test_channel_stats_defaults(server_config, cache):
    tools = _setup(server_config, cache)
    result = tools["channel_stats"](sample_id="sample_001", source="raw")
    assert "error" not in result
    assert "FSC-A" in result["stats"]
    s = result["stats"]["FSC-A"]
    assert "mean" in s
    assert s["n"] == 500


def test_channel_stats_specific_channels(server_config, cache):
    tools = _setup(server_config, cache)
    result = tools["channel_stats"](
        sample_id="sample_001", channels=["FSC-A", "SSC-A"], source="raw"
    )
    assert set(result["stats"].keys()) == {"FSC-A", "SSC-A"}


def test_compare_samples(server_config, cache):
    tools = _setup(server_config, cache)
    result = tools["compare_samples"](
        sample_ids=["sample_001", "sample_002"],
        channels=["FSC-A"],
        metric="median",
        source="raw",
    )
    assert "error" not in result
    assert len(result["table"]) == 2
    assert "FSC-A" in result["pivot"]
    assert "sample_001" in result["pivot"]["FSC-A"]
