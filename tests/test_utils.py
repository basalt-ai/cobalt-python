"""Tests for stats and template utilities."""

from __future__ import annotations

import pytest

from cobalt.utils.stats import calculate
from cobalt.utils.template import render


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def test_calculate_basic():
    scores = [0.0, 0.5, 1.0]
    s = calculate(scores)
    assert abs(s.avg - 0.5) < 0.01
    assert s.min == 0.0
    assert s.max == 1.0


def test_calculate_single():
    s = calculate([0.7])
    assert s.avg == 0.7
    assert s.p50 == 0.7
    assert s.p95 == 0.7
    assert s.p99 == 0.7


def test_calculate_empty():
    s = calculate([])
    assert s.avg == 0.0
    assert s.p95 == 0.0


def test_calculate_percentiles():
    # 100 values 0.01, 0.02, …, 1.00
    scores = [i / 100 for i in range(1, 101)]
    s = calculate(scores)
    assert abs(s.p50 - 0.50) < 0.02
    assert abs(s.p95 - 0.95) < 0.02
    assert abs(s.p99 - 0.99) < 0.02


# ---------------------------------------------------------------------------
# template
# ---------------------------------------------------------------------------


def test_render_simple():
    assert render("Hello {{name}}!", {"name": "World"}) == "Hello World!"


def test_render_multiple():
    t = "{{a}} + {{b}} = {{c}}"
    assert render(t, {"a": "1", "b": "2", "c": "3"}) == "1 + 2 = 3"


def test_render_missing_key_leaves_placeholder():
    result = render("Hello {{missing}}!", {"name": "x"})
    assert "{{missing}}" in result


def test_render_nested():
    result = render("{{item.input}}", {"item": {"input": "deep value"}})
    assert result == "deep value"


def test_render_no_placeholders():
    assert render("plain text", {}) == "plain text"
