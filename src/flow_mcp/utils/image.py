"""Utility helpers for converting Matplotlib figures to PNG bytes."""

from __future__ import annotations

import io

import matplotlib.figure


def figure_to_png(fig: matplotlib.figure.Figure, dpi: int = 150) -> bytes:
    """Render a Matplotlib figure to a PNG byte string.

    The figure is closed after rendering to free memory.

    Args:
        fig: The Matplotlib figure to render.
        dpi: Resolution in dots per inch.

    Returns:
        Raw PNG bytes suitable for embedding in an MCP ``Image`` response.
    """
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        return buf.getvalue()
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)
