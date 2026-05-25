"""Tests for tools/io.py."""

from __future__ import annotations

import pytest
from mcp.server.fastmcp import FastMCP

from cyto_mcp.tools import io


def _make_mcp_with_io(server_config, cache):
    mcp = FastMCP("test")
    io.register(mcp, server_config, cache)
    return mcp


def test_list_fcs(server_config, cache):
    mcp = _make_mcp_with_io(server_config, cache)
    # Call the tool function directly by looking it up on the MCP instance
    tool_fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}["list_fcs"]
    result = tool_fn()
    assert result["count"] == 2
    assert any("sample_001" in f for f in result["files"])


def test_load_fcs(server_config, cache):
    mcp = _make_mcp_with_io(server_config, cache)
    tool_fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}["load_fcs"]
    result = tool_fn(path="sample_001.fcs")
    assert "error" not in result
    assert result["sample_id"] == "sample_001"
    assert result["event_count"] == 500
    assert "FSC-A" in result["channels"]


def test_load_fcs_missing_file(server_config, cache):
    mcp = _make_mcp_with_io(server_config, cache)
    tool_fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}["load_fcs"]
    result = tool_fn(path="nonexistent.fcs")
    assert "error" in result


def test_load_fcs_path_traversal(server_config, cache):
    mcp = _make_mcp_with_io(server_config, cache)
    tool_fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}["load_fcs"]
    result = tool_fn(path="../../etc/passwd")
    assert "error" in result


def test_validate_fcs(server_config, cache):
    mcp = _make_mcp_with_io(server_config, cache)
    tool_fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}["validate_fcs"]
    result = tool_fn(path="sample_001.fcs")
    assert result["valid"] is True
    assert result["event_count"] == 500


def test_cached_samples_and_unload(server_config, cache):
    mcp = _make_mcp_with_io(server_config, cache)
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    tools["load_fcs"](path="sample_001.fcs")
    assert tools["cached_samples"]()["count"] == 1
    tools["unload_fcs"](sample_id="sample_001")
    assert tools["cached_samples"]()["count"] == 0
