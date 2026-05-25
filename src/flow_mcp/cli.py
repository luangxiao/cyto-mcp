"""Command-line interface for cyto-mcp.

Usage
-----
Start the server (stdio transport, for use with Claude Desktop / VS Code):

    cyto-mcp serve --data-dir /path/to/fcs [--output-dir ./outputs] [--cache-size 5]

Validate configuration without starting the server:

    cyto-mcp check --data-dir /path/to/fcs

Update to the latest published version (requires uv or pip):

    cyto-mcp update
"""

from __future__ import annotations

from pathlib import Path

import click

from flow_mcp import __version__
from flow_mcp.config import ServerConfig


@click.group()
@click.version_option(__version__, prog_name="cyto-mcp")
def main() -> None:
    """flow-mcp — MCP server for flow cytometry analysis."""


@main.command()
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Root directory containing FCS files (env: FLOW_MCP_DATA_DIR).",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for generated plots and reports (env: FLOW_MCP_OUTPUT_DIR).",
)
@click.option(
    "--cache-size",
    type=int,
    default=None,
    help="Max number of FCS samples held in memory (env: FLOW_MCP_CACHE_SIZE).",
)
@click.option(
    "--plot-dpi",
    type=int,
    default=None,
    help="DPI for rendered PNG plots (env: FLOW_MCP_PLOT_DPI).",
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    show_default=True,
    help="MCP transport protocol.",
)
def serve(
    data_dir: Path | None,
    output_dir: Path | None,
    cache_size: int | None,
    plot_dpi: int | None,
    transport: str,
) -> None:
    """Start the flow-mcp MCP server."""
    # Build config, merging CLI flags over env / defaults
    overrides: dict = {}
    if data_dir is not None:
        overrides["data_dir"] = data_dir
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if cache_size is not None:
        overrides["cache_size"] = cache_size
    if plot_dpi is not None:
        overrides["plot_dpi"] = plot_dpi

    config = ServerConfig(**overrides)

    # Late import avoids pulling in heavy deps before config validation
    from flow_mcp.server import create_server

    click.echo(f"cyto-mcp v{__version__}", err=True)
    click.echo(f"  data-dir   : {config.data_dir}", err=True)
    click.echo(f"  output-dir : {config.output_dir}", err=True)
    click.echo(f"  cache-size : {config.cache_size}", err=True)
    click.echo(f"  transport  : {transport}", err=True)
    click.echo("Starting server…", err=True)

    mcp = create_server(config)
    mcp.run(transport=transport)


@main.command()
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Root directory to validate.",
)
def check(data_dir: Path | None) -> None:
    """Validate configuration and print diagnostics without starting the server."""
    overrides: dict = {}
    if data_dir is not None:
        overrides["data_dir"] = data_dir

    config = ServerConfig(**overrides)

    click.echo(f"cyto-mcp v{__version__} — configuration check")
    click.echo(f"  data-dir   : {config.data_dir}")
    click.echo(f"  output-dir : {config.output_dir}")
    click.echo(f"  cache-size : {config.cache_size}")

    if not config.data_dir.exists():
        click.secho(f"  WARNING: data-dir does not exist: {config.data_dir}", fg="yellow")
    else:
        fcs_files = list(config.data_dir.rglob("*.fcs"))
        click.secho(f"  FCS files found: {len(fcs_files)}", fg="green" if fcs_files else "yellow")

    click.secho("Configuration OK.", fg="green")


@main.command()
@click.option(
    "--pre",
    is_flag=True,
    default=False,
    help="Allow pre-release versions.",
)
def update(pre: bool) -> None:
    """Update flow-mcp to the latest version from PyPI.

    Detects whether the package was installed with ``uv`` or ``pip`` and
    runs the appropriate upgrade command.

    Examples
    --------
    Upgrade to the latest stable release::

        flow-mcp update

    Upgrade to the latest pre-release::

        flow-mcp update --pre
    """
    import shutil
    import subprocess
    import sys

    package = "cyto-mcp"
    if pre:
        package += " --pre"

    click.echo(f"Current version: {__version__}")

    # Prefer uv if available (faster and handles virtual envs cleanly)
    if shutil.which("uv"):
        cmd = ["uv", "pip", "install", "--upgrade", "cyto-mcp"]
        if pre:
            cmd.append("--pre")
        runner = "uv"
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "cyto-mcp"]
        if pre:
            cmd.append("--pre")
        runner = "pip"

    click.echo(f"Upgrading via {runner}: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        click.secho("Update successful. Restart the MCP server to apply changes.", fg="green")
    else:
        click.secho("Update failed. Check the output above for details.", fg="red")
        raise SystemExit(result.returncode)
