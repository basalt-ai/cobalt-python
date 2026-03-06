"""Simple {{variable}} template rendering."""

from __future__ import annotations

import re
from typing import Any


def render(template: str, context: dict[str, Any]) -> str:
    """Replace ``{{key}}`` and ``{{nested.key}}`` placeholders.

    Supports dotted paths (e.g. ``{{item.input}}``).  Missing keys are left
    as-is so callers can distinguish intentional gaps from typos.
    """

    def replace(match: re.Match) -> str:  # type: ignore[type-arg]
        key = match.group(1).strip()
        parts = key.split(".")
        value: Any = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None)
            if value is None:
                return match.group(0)  # leave placeholder intact
        return str(value)

    return re.sub(r"\{\{(.+?)\}\}", replace, template)
