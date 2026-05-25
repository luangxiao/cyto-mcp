"""Server configuration via Pydantic Settings.

Values are resolved in priority order:
1. CLI flags (passed explicitly at startup)
2. Environment variables (prefixed ``CYTO_MCP_``)
3. Hard-coded defaults below
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Runtime configuration for the cyto-mcp server."""

    model_config = SettingsConfigDict(
        env_prefix="CYTO_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    data_dir: Path = Field(
        default=Path.home() / "flow_data",
        description=(
            "Root directory that the server is allowed to read FCS files from. "
            "All path arguments in tool calls are resolved relative to this directory."
        ),
    )
    output_dir: Path = Field(
        default=Path.cwd() / "outputs",
        description=(
            "Directory where the server writes generated plots and reports. "
            "Created automatically if it does not exist."
        ),
    )

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    cache_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of FlowKit Sample objects held in memory simultaneously.",
    )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    plot_dpi: int = Field(
        default=150,
        ge=72,
        le=300,
        description="DPI used when rendering plot PNGs.",
    )
    plot_max_events: int = Field(
        default=50_000,
        ge=1_000,
        description=(
            "Maximum number of events rendered in scatter/density plots. "
            "Larger samples are automatically down-sampled before rendering."
        ),
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("data_dir", "output_dir", mode="before")
    @classmethod
    def _expand(cls, v: object) -> Path:
        return Path(str(v)).expanduser().resolve()
