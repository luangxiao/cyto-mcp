"""Typed error hierarchy for flow-mcp.

All domain errors inherit from ``FlowMcpError`` so callers can catch them
with a single ``except FlowMcpError`` clause and still distinguish sub-types
when needed.
"""

from __future__ import annotations


class FlowMcpError(Exception):
    """Base class for all flow-mcp errors."""

    def to_dict(self) -> dict[str, str]:
        """Serialize to a JSON-safe dict suitable for returning from a tool."""
        return {"error": type(self).__name__, "message": str(self)}


class SampleNotFoundError(FlowMcpError):
    """Raised when a requested sample_id is not cached and cannot be found on disk."""

    def __init__(self, sample_id: str) -> None:
        super().__init__(
            f"Sample '{sample_id}' is not loaded. "
            "Call load_fcs() first, or verify the sample_id is correct."
        )
        self.sample_id = sample_id


class ChannelNotFoundError(FlowMcpError):
    """Raised when a requested channel name is absent from the FCS file."""

    def __init__(self, channel: str, available: list[str]) -> None:
        super().__init__(
            f"Channel '{channel}' not found. "
            f"Available channels: {available}"
        )
        self.channel = channel
        self.available = available


class PathTraversalError(FlowMcpError):
    """Raised when a caller-supplied path escapes the configured data directory."""

    def __init__(self, attempted_path: str) -> None:
        super().__init__(
            f"Path '{attempted_path}' is outside the allowed data directory. "
            "Only paths within --data-dir are accessible."
        )
        self.attempted_path = attempted_path


class UnsupportedFormatError(FlowMcpError):
    """Raised when a file is not a valid / supported FCS file."""

    def __init__(self, path: str, reason: str = "") -> None:
        msg = f"'{path}' is not a supported FCS file."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)
        self.path = path


class GatingError(FlowMcpError):
    """Raised when a gate specification is malformed or incompatible with the sample."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class CompensationError(FlowMcpError):
    """Raised when compensation cannot be applied (e.g., matrix dimension mismatch)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
