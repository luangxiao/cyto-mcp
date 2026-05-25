# cyto-mcp

> A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that brings
> flow cytometry analysis to any MCP-capable AI assistant — locally, privately, and for free.

---

## Why cyto-mcp?

Flow cytometry analysis (FCS files, gating, compensation, clustering) is tedious, error-prone,
and hard to script. **cyto-mcp** lets an AI assistant like Claude or GitHub Copilot drive the
entire analysis pipeline through natural language — while keeping every byte of your data on
your own machine.

```
Cloud LLM  ──HTTPS──►  MCP Client (Claude Desktop / VS Code / Cursor)
                               │  stdio / local HTTP
                               ▼
                        cyto-mcp server  ──►  FCS files on your disk
```

**No data leaves your machine.** The LLM only sees compact summaries, statistics, and images
that the server sends back.

---

## Features

| Category | Tools |
|---|---|
| **File I/O** | List, load, validate FCS files; read FCS keywords |
| **Preprocessing** | Apply compensation matrix; Logicle / asinh / biexp transform |
| **Subsampling** | Reproducible down-sampling for fast exploration |
| **Statistics** | Per-channel percentile stats; cross-sample comparison |
| **Gating** | Rectangle and threshold gates; population frequency & MFI |
| **Visualization** | Scatter plots and histograms — returned as PNG + structured JSON |

*Quality control (time-drift, saturation flagging), polygon/ellipse gates, reporting, and clustering (FlowSOM, UMAP) are planned for v0.2.*

---

## Quickstart

### Prerequisites

- Python 3.11+
- An MCP-capable client: [Claude Desktop](https://claude.ai/download),
  [VS Code + GitHub Copilot](https://code.visualstudio.com/), or [Cursor](https://cursor.sh/)

### Install from PyPI *(recommended)*

```bash
pip install cyto-mcp
cyto-mcp --help               # verify it works
```

Or with [uv](https://docs.astral.sh/uv/) (faster, isolated):

```bash
uv tool install cyto-mcp
cyto-mcp --help
```

### Install from source *(for contributors / development)*

```bash
git clone https://github.com/luangxiao/cyto-mcp.git
cd cyto-mcp
uv sync                       # creates .venv and installs all deps
uv run cyto-mcp --help        # verify it works
```

### Configure your MCP client

**Claude Desktop** — edit `claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "flow": {
      "command": "cyto-mcp",
      "args": ["serve", "--data-dir", "/path/to/your/fcs/files"]
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
      "command": "cyto-mcp",
      "args": ["serve", "--data-dir", "/path/to/your/fcs/files"]
    }
  }
}
```

> **Note for VS Code:** if `cyto-mcp` is not on VS Code's PATH, use the full path to the
> executable (e.g. `C:/Users/you/AppData/Roaming/Python/Scripts/cyto-mcp.exe` on Windows, or
> run `which cyto-mcp` on macOS/Linux to find it).

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
├── cli.py             # click CLI entry point  (`cyto-mcp serve`)
├── config.py          # Pydantic settings (data-dir, output-dir, cache size)
├── errors.py          # Typed error hierarchy
├── cache.py           # LRU in-memory sample cache
├── tools/
│   ├── io.py          # load_fcs, list_fcs, fcs_keywords, validate_fcs
│   ├── preprocess.py  # apply_compensation, transform, subsample
│   ├── stats.py       # channel_stats, compare_samples
│   ├── gating.py      # gate_rectangle, gate_threshold, population_stats
│   └── plots.py       # scatter_plot, histogram
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

## Community & Discussion

I'm a solo developer building this in my spare time — I'd genuinely love to hear from you, whether you're a researcher, clinician, bioinformatician, or just curious.

- **Questions / ideas?** → open a [Discussion](https://github.com/luangxiao/cyto-mcp/discussions) — no question is too basic.
- **Found a bug?** → open an [Issue](https://github.com/luangxiao/cyto-mcp/issues) with steps to reproduce.
- **Want to share a use-case or analysis workflow?** → post it in [Show and Tell](https://github.com/luangxiao/cyto-mcp/discussions/categories/show-and-tell), I genuinely enjoy seeing real-world applications.

---

## Contributing

All contributions are welcome — from typo fixes to new tools. Here's how to get started:

1. **Fork** the repository and clone it locally
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Install dev dependencies: `uv sync --extra dev`
4. Run tests: `uv run pytest`
5. Lint: `uv run ruff check src tests`
6. Open a **pull request** with a clear description of what and why

For anything non-trivial, please open an issue or discussion first so we can align on approach before you invest time coding. I'll do my best to review PRs promptly and give constructive feedback.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
