"""Shared test fixtures.

Provides:
- A minimal synthetic FCS file written to a temp directory.
- A pre-loaded ``SampleCache`` and ``ServerConfig`` scoped to that directory.
"""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest

from flow_mcp.cache import SampleCache
from flow_mcp.config import ServerConfig


def _write_minimal_fcs(path: Path, n_events: int = 500, n_channels: int = 6) -> None:
    """Write a bare-minimum FCS 3.1 file for testing.

    Channels: FSC-A, SSC-A, FITC-A, PE-A, APC-A, Time
    """
    channel_names = ["FSC-A", "SSC-A", "FITC-A", "PE-A", "APC-A", "Time"][:n_channels]
    fluoro_names  = ["",      "",      "FITC",   "PE",   "APC",   ""][:n_channels]

    rng = np.random.default_rng(0)
    data = rng.uniform(0, 262144, size=(n_events, n_channels)).astype(np.float32)

    # --- TEXT segment ---
    kv: dict[str, str] = {
        "$BEGINANALYSIS": "0",
        "$ENDANALYSIS": "0",
        "$BYTEORD": "1,2,3,4",
        "$DATATYPE": "F",
        "$MODE": "L",
        "$NEXTDATA": "0",
        "$PAR": str(n_channels),
        "$TOT": str(n_events),
        "$FCSversion": "FCS3.1",
        "$DATE": "20-May-2026",
        "$CYT": "TestCytometer",
        "TUBE NAME": "Test_Tube_001",
    }
    for i, (pnn, pns) in enumerate(zip(channel_names, fluoro_names), start=1):
        kv[f"$P{i}N"] = pnn
        kv[f"$P{i}S"] = pns
        kv[f"$P{i}B"] = "32"
        kv[f"$P{i}R"] = "262144"
        kv[f"$P{i}E"] = "0,0"

    separator = "/"
    text_body = separator.join(f"{k}{separator}{v}" for k, v in kv.items()) + separator
    text_bytes = text_body.encode("ascii")

    # --- DATA segment (raw float32, little-endian) ---
    data_bytes = data.tobytes()

    # --- HEADER (256 bytes) ---
    text_start = 256
    text_end   = text_start + len(text_bytes) - 1
    data_start = text_end + 1
    data_end   = data_start + len(data_bytes) - 1

    header = (
        f"FCS3.1  "
        f"{text_start:>8}{text_end:>8}"
        f"{data_start:>8}{data_end:>8}"
        f"{'0':>8}{'0':>8}"
    ).encode("ascii")
    header = header.ljust(256, b" ")

    with path.open("wb") as f:
        f.write(header)
        f.write(text_bytes)
        f.write(data_bytes)


@pytest.fixture(scope="session")
def fcs_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A temp directory containing two minimal FCS files."""
    d = tmp_path_factory.mktemp("fcs_data")
    _write_minimal_fcs(d / "sample_001.fcs")
    _write_minimal_fcs(d / "sample_002.fcs")
    return d


@pytest.fixture()
def server_config(fcs_dir: Path, tmp_path: Path) -> ServerConfig:
    """A ``ServerConfig`` pointing at the test FCS directory."""
    return ServerConfig(
        data_dir=fcs_dir,
        output_dir=tmp_path / "outputs",
        cache_size=3,
    )


@pytest.fixture()
def cache() -> SampleCache:
    """A fresh empty ``SampleCache``."""
    return SampleCache(max_size=3)
