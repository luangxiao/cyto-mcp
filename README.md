# flow-mcp

> A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that brings
> flow cytometry analysis to any MCP-capable AI assistant — locally, privately, and for free.

---

## Why flow-mcp?

Flow cytometry analysis (FCS files, gating, compensation, clustering) is tedious, error-prone,
and hard to script. **flow-mcp** lets an AI assistant like Claude or GitHub Copilot drive the
entire analysis pipeline through natural language — while keeping every byte of your data on
your own machine.

```
Cloud LLM  ──HTTPS──►  MCP Client (Claude Desktop / VS Code / Cursor)
                               │  stdio / local HTTP
                               ▼
                        flow-mcp server  ──►  FCS files on your disk
```

**No data leaves your machine.** The LLM only sees compact summaries, statistics, and images
that the server sends back.

---

## Features

| Category | Tools |
|---|---|
| **File I/O** | List, load, validate FCS files; read FCS keywords |
| **Preprocessing** | Apply compensation matrix; Logicle / asinh / biexp transform |
| **Quality control** | Time-drift detection, saturated-event flagging |
| **Subsampling** | Reproducible down-sampling for fast exploration |
| **Statistics** | Per-channel percentile stats; cross-sample comparison |
| **Gating** | Rectangle, polygon, ellipse, quadrant, threshold gates |
| **Visualization** | Scatter plots, histograms, density overlays — returned as PNG + structured JSON |
| **Reporting** | Markdown / HTML summary reports |

*Advanced clustering (FlowSOM, UMAP) is planned for v0.2.*

---

## Quickstart

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) **or** pip
- An MCP-capable client: [Claude Desktop](https://claude.ai/download),
  [VS Code + GitHub Copilot](https://code.visualstudio.com/), or [Cursor](https://cursor.sh/)

### Install from source

```bash
git clone https://github.com/YOUR_USERNAME/flow-mcp.git
cd flow-mcp
uv sync                       # creates .venv and installs all deps
uv run flow-mcp --help        # verify it works
```

Or with pip:

```bash
pip install -e .
flow-mcp --help
```

### Configure your MCP client

**Claude Desktop** — edit `claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "flow": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/flow-mcp", "flow-mcp", "serve",
               "--data-dir", "/path/to/your/fcs/files"],
      "env": {}
    }
  }
}
```

**VS Code** — create `.vscode/mcp.json` in your workspace:

```jsonc
{
  "servers": {
    "flow": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "${workspaceFolder}", "flow-mcp", "serve",
               "--data-dir", "${workspaceFolder}/data"]
    }
  }
}
```

### Try it

In your AI assistant, ask:

> *"List FCS files in my data directory and load the first one. Show me the panel channels and a
> scatter plot of FSC-A vs SSC-A."*

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed description of the codebase layout,
design decisions, and extension guide.

```
src/flow_mcp/
├── server.py          # FastMCP app wiring and startup
├── cli.py             # click CLI entry point  (`flow-mcp serve`)
├── config.py          # Pydantic settings (data-dir, output-dir, cache size)
├── errors.py          # Typed error hierarchy
├── cache.py           # LRU in-memory sample cache
├── tools/
│   ├── io.py          # load_fcs, list_fcs, fcs_keywords, validate_fcs
│   ├── preprocess.py  # apply_compensation, transform
│   ├── qc.py          # quality_check
│   ├── stats.py       # channel_stats, compare_samples
│   ├── gating.py      # gate_*, population_stats
│   └── plots.py       # scatter_plot, histogram, density_plot
└── utils/
    ├── image.py       # fig → PNG bytes helper
    └── paths.py       # safe path resolution within data-dir sandbox
```

---

## Design principles

1. **Data never leaves the machine.** The server only reads files from the configured `--data-dir`
   and writes outputs to `--output-dir`. No network calls.
2. **Return references, not raw data.** Large artefacts (PNG plots, reports) are written to disk
   and referenced by URI. Tool responses stay small enough to fit in any context window.
3. **Dual return for plots.** Every plot tool returns both a PNG image (for the human) *and* a
   structured JSON summary (for the LLM to reason about numerically).
4. **Sandboxed file access.** All path arguments are resolved relative to `--data-dir` and
   validated to prevent path traversal attacks.
5. **Stateless tools, stateful cache.** Each tool call is self-contained; the LRU sample cache is
   an optimisation, not a requirement for correctness.

---

## Contributing

Contributions, bug reports, and feature requests are welcome!
Please open an issue before submitting large PRs.

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Install dev dependencies: `uv sync --extra dev`
4. Run tests: `uv run pytest`
5. Lint: `uv run ruff check src tests`
6. Open a pull request

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
