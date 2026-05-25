# Architecture

This document explains the internal structure of **cyto-mcp**, the design decisions behind it,
and how to extend it with new tools.

---

## Repository layout

```
cyto-mcp/
├── src/
│   └── cyto_mcp/           # Main Python package
│       ├── __init__.py
│       ├── server.py       # FastMCP app; registers all tools and starts the server
│       ├── cli.py          # CLI entry point (`cyto-mcp serve [OPTIONS]`)
│       ├── config.py       # Pydantic-based server configuration
│       ├── errors.py       # Domain error hierarchy
│       ├── cache.py        # Thread-safe LRU cache for loaded FlowKit Samples
│       ├── tools/          # One module per functional area
│       │   ├── __init__.py
│       │   ├── io.py       # File discovery & loading
│       │   ├── preprocess.py
│       │   ├── stats.py
│       │   ├── gating.py
│       │   └── plots.py
│       └── utils/
│           ├── __init__.py
│           ├── image.py    # Matplotlib figure → PNG bytes
│           └── paths.py    # Safe path resolution (sandboxed to data-dir)
├── tests/
│   ├── conftest.py         # Shared fixtures (tiny synthetic FCS, temp dirs)
│   ├── test_io.py
│   ├── test_preprocess.py
│   ├── test_stats.py
│   ├── test_gating.py
│   └── test_plots.py
├── examples/
│   ├── claude_desktop_config.json  # Copy-paste client configs
│   └── vscode_mcp.json
├── pyproject.toml
├── README.md
└── ARCHITECTURE.md
```

---

## Data flow

```
User prompt
    │
    ▼
MCP Client (Claude Desktop / VS Code / Cursor)
    │  calls tool via JSON-RPC over stdio
    ▼
cyto_mcp.server  ──dispatches──►  tools/io.py
                                  tools/preprocess.py
                                  tools/gating.py
                                  tools/stats.py
                                  tools/plots.py
                                        │
                         reads ◄────────┤────────► writes
                      FCS files        │         PNG / reports
                    (--data-dir)       │        (--output-dir)
                                 cache.py
                              (LRU of loaded
                               fk.Sample objects)
```

### Key invariants

- **Tools are pure functions** from the perspective of the MCP protocol. They receive arguments,
  access the cache (an implementation detail), and return a JSON-serialisable value or an image.
- **The cache is an optimisation.** If a sample is evicted, the next tool call reloads it from
  disk. Correctness is never compromised by cache state.
- **All path arguments are sandboxed.** `utils/paths.py` resolves every caller-supplied path
  relative to `--data-dir` and raises `PathTraversalError` for any path that escapes it.

---

## Configuration (`config.py`)

`ServerConfig` is a Pydantic `BaseSettings` model. Values are loaded (in order of priority) from:

1. CLI flags (`--data-dir`, `--output-dir`, `--cache-size`)
2. Environment variables (`CYTO_MCP_DATA_DIR`, etc.)
3. Hard-coded defaults

This makes the server easy to configure in any deployment scenario without code changes.

---

## Sample cache (`cache.py`)

Loading a large FCS file (potentially hundreds of MB) on every tool call would be unacceptable.
`SampleCache` wraps `collections.OrderedDict` to provide an LRU eviction policy:

- Maximum capacity is configurable (default: 5 samples).
- Cache keys are `sample_id` strings (the stem of the FCS filename).
- The cache is **not** shared across OS processes; it lives in the server process.

---

## Tool registration pattern

Each tool module exposes a `register(mcp: FastMCP, config: ServerConfig, cache: SampleCache)`
function. `server.py` calls each one at startup. This keeps tool files self-contained and makes
it easy to add or remove feature groups.

```python
# tools/io.py
def register(mcp: FastMCP, config: ServerConfig, cache: SampleCache) -> None:

    @mcp.tool()
    def load_fcs(path: str) -> dict:
        ...

    @mcp.tool()
    def list_fcs() -> list[str]:
        ...
```

---

## Plot design: dual return

Every plot tool returns a `dict` containing:

```python
{
    "image": Image(data=<png_bytes>, format="png"),   # rendered for the human
    "summary": { ... },                                # structured data for the LLM
    "output_path": "outputs/sample_001/fsc_ssc.png",  # persistent reference URI
}
```

The `summary` field lets the LLM reason numerically (gate suggestions, peak positions, % events)
without relying solely on visual interpretation, which is unreliable for dense cytometry plots.

---

## Error handling

`errors.py` defines a typed hierarchy:

```
CytoMcpError (base)
├── SampleNotFoundError     # requested sample_id not in cache and not on disk
├── ChannelNotFoundError    # requested channel name absent from the FCS file
├── PathTraversalError      # caller tried to escape --data-dir
├── UnsupportedFormatError  # file is not a valid FCS 2.0/3.0/3.1 file
└── GatingError             # malformed gate specification
```

Tools catch these and return structured error dicts instead of crashing, so the LLM can
report a useful message to the user.

---

## Adding a new tool

1. Add a function to the appropriate module under `tools/` (or create a new module).
2. Decorate it with `@mcp.tool()` inside the module's `register()` function.
3. Write a docstring — the MCP SDK exposes this to the LLM as the tool description.
4. Add at least one test in `tests/`.
5. Update the feature table in `README.md`.

---

## Security considerations

- `--data-dir` acts as a **chroot-like sandbox**. The server refuses to read or write outside it.
- The server does not execute arbitrary code from FCS files or gate specifications.
- No outbound network connections are made (all analysis is local).
- The server should be run with the minimum OS privileges needed (read access to `data-dir`,
  write access to `output-dir`).
