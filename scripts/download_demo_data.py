"""Download public FCS demo files from the FlowKit test dataset.

These files are used for local development and manual testing.
They are NOT committed to git (excluded by fcs_demo/.gitignore).

Usage
-----
    uv run python scripts/download_demo_data.py

Source
------
FlowKit by Scott White — https://github.com/whitews/FlowKit (BSD 3-Clause)
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/whitews/FlowKit/master/data"

# (remote path relative to BASE_URL, local path relative to fcs_demo/)
FILES: list[tuple[str, str]] = [
    # Simple / small — good for unit tests and quick demos
    ("simple_line_example/data_set_simple_line_100.fcs",  "simple_line_example/data_set_simple_line_100.fcs"),
    ("test_data_2d_01.fcs",                               "test_data_2d_01.fcs"),
    ("gate_ref/data1.fcs",                                "gate_ref/data1.fcs"),
    # Medium — single tube with compensation matrix
    ("100715.fcs",                                        "100715.fcs"),
    # Multi-sample 8-colour panel — good for cross-sample comparison tools
    ("8_color_data_set/fcs_files/101_DEN084Y5_15_E01_008_clean.fcs",
     "8_color_data_set/101_DEN084Y5_15_E01_008_clean.fcs"),
    ("8_color_data_set/fcs_files/101_DEN084Y5_15_E03_009_clean.fcs",
     "8_color_data_set/101_DEN084Y5_15_E03_009_clean.fcs"),
    ("8_color_data_set/fcs_files/101_DEN084Y5_15_E05_010_clean.fcs",
     "8_color_data_set/101_DEN084Y5_15_E05_010_clean.fcs"),
]

DEMO_DIR = Path(__file__).parent.parent / "src" / "cyto_mcp" / "fcs_demo"


def download(remote: str, local: Path) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    if local.exists():
        print(f"  skip  {local.name}  (already exists)")
        return
    url = f"{BASE_URL}/{remote}"
    print(f"  fetch {local.relative_to(DEMO_DIR)} ...", end=" ", flush=True)
    urllib.request.urlretrieve(url, local)
    size_kb = local.stat().st_size // 1024
    print(f"{size_kb} KB")


def main() -> None:
    print(f"Downloading {len(FILES)} FCS demo files into:\n  {DEMO_DIR}\n")
    errors: list[str] = []
    for remote, local_rel in FILES:
        try:
            download(remote, DEMO_DIR / local_rel)
        except Exception as exc:
            errors.append(f"{local_rel}: {exc}")
            print(f"  ERROR: {exc}")

    print()
    if errors:
        print(f"{len(errors)} file(s) failed. Check your internet connection.")
        sys.exit(1)
    else:
        print("All files downloaded successfully.")
        print("Point --data-dir at the fcs_demo folder to try them:")
        print(f"  uv run cyto-mcp serve --data-dir {DEMO_DIR}")


if __name__ == "__main__":
    main()
