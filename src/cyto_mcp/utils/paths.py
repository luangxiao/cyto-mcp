"""Safe path resolution within the server's data-directory sandbox.

All path arguments supplied by callers (via the LLM) are resolved through
:func:`resolve_data_path` before use. This prevents path-traversal attacks
where a malicious prompt might pass ``../../etc/passwd`` as a file path.
"""

from __future__ import annotations

from pathlib import Path

from cyto_mcp.errors import PathTraversalError


def resolve_data_path(user_path: str, data_dir: Path) -> Path:
    """Resolve *user_path* relative to *data_dir* and ensure it stays inside.

    Args:
        user_path: A relative or absolute path string supplied by the caller.
        data_dir:  The root directory the server is allowed to access.

    Returns:
        An absolute :class:`~pathlib.Path` that is guaranteed to be inside
        *data_dir*.

    Raises:
        PathTraversalError: If the resolved path escapes *data_dir*.
    """
    candidate = (data_dir / user_path).resolve()
    try:
        candidate.relative_to(data_dir)
    except ValueError:
        raise PathTraversalError(user_path) from None
    return candidate


def make_output_path(output_dir: Path, sample_id: str, filename: str) -> Path:
    """Return the path for a generated output file and create parent dirs.

    Args:
        output_dir: Root output directory from server config.
        sample_id:  Sample identifier (used as a sub-directory name).
        filename:   Output file name (e.g. ``fsc_ssc.png``).

    Returns:
        Full absolute path where the output should be written.
    """
    dest = output_dir / sample_id / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest
