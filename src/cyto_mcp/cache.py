"""Thread-safe LRU cache for loaded FlowKit Sample objects.

Loading a large FCS file on every tool call would be prohibitively slow.
``SampleCache`` keeps the most recently used samples in memory and evicts
the least recently used one when the capacity limit is reached.

The cache is intentionally simple — it is an optimisation, not a source of
truth. If a sample is evicted, the next tool call simply reloads it from disk.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Callable

import flowkit as fk

if TYPE_CHECKING:
    pass


class SampleCache:
    """LRU cache mapping ``sample_id`` → :class:`flowkit.Sample`."""

    def __init__(self, max_size: int = 5) -> None:
        if max_size < 1:
            raise ValueError("max_size must be at least 1")
        self._max_size = max_size
        self._store: OrderedDict[str, fk.Sample] = OrderedDict()
        self._lock = threading.Lock()
        self._on_evict: list[Callable[[str], None]] = []

    # ------------------------------------------------------------------
    # Eviction hooks
    # ------------------------------------------------------------------

    def on_evict(self, callback: Callable[[str], None]) -> None:
        """Register a callback invoked with the sample_id whenever a sample
        is removed (explicit evict, LRU overflow, or clear).

        Callbacks are called outside the cache lock so they may safely
        acquire their own locks. Exceptions in callbacks are swallowed to
        avoid corrupting cache state.
        """
        self._on_evict.append(callback)

    def _notify_evict(self, sample_ids: list[str]) -> None:
        for sid in sample_ids:
            for cb in self._on_evict:
                try:
                    cb(sid)
                except Exception:  # noqa: BLE001 — isolation between hooks
                    pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, sample_id: str) -> fk.Sample | None:
        """Return the cached sample, or ``None`` if it is not present.

        Accessing a sample moves it to the *most recently used* position.
        """
        with self._lock:
            if sample_id not in self._store:
                return None
            self._store.move_to_end(sample_id)
            return self._store[sample_id]

    def put(self, sample_id: str, sample: fk.Sample) -> None:
        """Insert or update a sample in the cache.

        If the cache is full, the least recently used entry is evicted first.
        """
        evicted: list[str] = []
        with self._lock:
            if sample_id in self._store:
                self._store.move_to_end(sample_id)
            self._store[sample_id] = sample
            if len(self._store) > self._max_size:
                lru_id, _ = self._store.popitem(last=False)  # evict LRU (oldest) entry
                evicted.append(lru_id)
        self._notify_evict(evicted)

    def evict(self, sample_id: str) -> bool:
        """Explicitly remove a sample from the cache.

        Returns ``True`` if the sample was present and removed.
        """
        removed = False
        with self._lock:
            if sample_id in self._store:
                del self._store[sample_id]
                removed = True
        if removed:
            self._notify_evict([sample_id])
        return removed

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            ids = list(self._store.keys())
            self._store.clear()
        self._notify_evict(ids)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __contains__(self, sample_id: str) -> bool:
        with self._lock:
            return sample_id in self._store

    @property
    def sample_ids(self) -> list[str]:
        """Return a snapshot of cached sample IDs (most-recently-used last)."""
        with self._lock:
            return list(self._store.keys())
