"""Tests for Dataset."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cobalt import Dataset


def _tmp_file(suffix: str, content: str) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# from_items
# ---------------------------------------------------------------------------


def test_from_items_basic():
    ds = Dataset.from_items([{"a": 1}, {"a": 2}])
    assert len(ds) == 2
    assert list(ds)[0] == {"a": 1}


def test_items_returns_copy():
    ds = Dataset.from_items([{"a": 1}])
    items = ds.items()
    items.append({"a": 99})
    assert len(ds) == 1  # original unchanged


# ---------------------------------------------------------------------------
# from_file (json / jsonl / csv)
# ---------------------------------------------------------------------------


def test_from_json_array():
    path = _tmp_file(".json", json.dumps([{"x": 1}, {"x": 2}]))
    ds = Dataset.from_file(str(path))
    assert len(ds) == 2


def test_from_json_object_with_items_key():
    path = _tmp_file(".json", json.dumps({"items": [{"x": 1}]}))
    ds = Dataset.from_file(str(path))
    assert len(ds) == 1


def test_from_jsonl():
    content = '{"a": 1}\n{"a": 2}\n'
    path = _tmp_file(".jsonl", content)
    ds = Dataset.from_file(str(path))
    assert len(ds) == 2
    assert ds.items()[1]["a"] == 2


def test_from_csv():
    content = "input,expected\nhello,world\nfoo,bar\n"
    path = _tmp_file(".csv", content)
    ds = Dataset.from_file(str(path))
    assert len(ds) == 2
    assert ds.items()[0]["input"] == "hello"


# ---------------------------------------------------------------------------
# Transformations
# ---------------------------------------------------------------------------


def test_filter():
    ds = Dataset.from_items([{"v": 1}, {"v": 2}, {"v": 3}])
    filtered = ds.filter(lambda item, _: item["v"] % 2 == 1)
    assert len(filtered) == 2


def test_map():
    ds = Dataset.from_items([{"v": 1}, {"v": 2}])
    mapped = ds.map(lambda item, _: {"v": item["v"] * 10})
    assert mapped.items()[0]["v"] == 10


def test_sample():
    ds = Dataset.from_items(list(range(20)))
    sampled = ds.sample(5)
    assert len(sampled) == 5


def test_sample_clamps_at_length():
    ds = Dataset.from_items([1, 2, 3])
    sampled = ds.sample(100)
    assert len(sampled) == 3


def test_slice():
    ds = Dataset.from_items(list(range(10)))
    sliced = ds.slice(2, 5)
    assert sliced.items() == [2, 3, 4]


def test_chaining():
    ds = Dataset.from_items([{"v": i} for i in range(10)])
    result = ds.filter(lambda item, _: item["v"] >= 5).slice(0, 3)
    assert len(result) == 3
    assert result.items()[0]["v"] == 5
