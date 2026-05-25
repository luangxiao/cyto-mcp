"""Tests for cyto_mcp.cache."""

from __future__ import annotations

import flowkit as fk
import pytest

from cyto_mcp.cache import SampleCache


def _dummy_sample(path: str) -> fk.Sample:
    return fk.Sample(path)


def test_put_and_get(fcs_dir):
    cache = SampleCache(max_size=2)
    sample = fk.Sample(fcs_dir / "sample_001.fcs")
    cache.put("s1", sample)
    assert cache.get("s1") is sample


def test_lru_eviction(fcs_dir):
    cache = SampleCache(max_size=2)
    s1 = fk.Sample(fcs_dir / "sample_001.fcs")
    s2 = fk.Sample(fcs_dir / "sample_002.fcs")
    s3 = fk.Sample(fcs_dir / "sample_001.fcs")  # third distinct logical entry

    cache.put("s1", s1)
    cache.put("s2", s2)
    # Access s1 to make it MRU
    cache.get("s1")
    # Adding s3 should evict s2 (LRU), not s1
    cache.put("s3", s3)

    assert cache.get("s1") is not None
    assert cache.get("s2") is None  # evicted
    assert cache.get("s3") is not None


def test_evict(fcs_dir):
    cache = SampleCache(max_size=3)
    sample = fk.Sample(fcs_dir / "sample_001.fcs")
    cache.put("s1", sample)
    assert cache.evict("s1") is True
    assert cache.evict("s1") is False
    assert "s1" not in cache


def test_clear(fcs_dir):
    cache = SampleCache(max_size=3)
    cache.put("s1", fk.Sample(fcs_dir / "sample_001.fcs"))
    cache.put("s2", fk.Sample(fcs_dir / "sample_002.fcs"))
    cache.clear()
    assert len(cache) == 0
