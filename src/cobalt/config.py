"""Configuration loading for Cobalt."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from cobalt.types import CobaltConfig, JudgeConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


_DEFAULT_CONFIG = CobaltConfig()


def load_config(cwd: str | Path | None = None) -> CobaltConfig:
    """Load ``cobalt.toml`` from *cwd* (or current directory).

    Missing keys fall back to :class:`CobaltConfig` defaults.
    """
    search_dir = Path(cwd) if cwd else Path.cwd()
    config_file = search_dir / "cobalt.toml"

    if not config_file.exists():
        return CobaltConfig()

    with config_file.open("rb") as fh:
        raw: dict[str, Any] = tomllib.load(fh)

    judge_raw = raw.get("judge", {})
    judge = JudgeConfig(
        model=judge_raw.get("model", _DEFAULT_CONFIG.judge.model),
        provider=judge_raw.get("provider", _DEFAULT_CONFIG.judge.provider),
        api_key=judge_raw.get("api_key") or os.environ.get("COBALT_API_KEY"),
    )

    exp_raw = raw.get("experiment", {})

    return CobaltConfig(
        test_dir=exp_raw.get("test_dir", _DEFAULT_CONFIG.test_dir),
        test_match=exp_raw.get("test_match", _DEFAULT_CONFIG.test_match),
        judge=judge,
        concurrency=exp_raw.get("concurrency", _DEFAULT_CONFIG.concurrency),
        timeout=float(exp_raw.get("timeout", _DEFAULT_CONFIG.timeout)),
        reporters=raw.get("reporters", _DEFAULT_CONFIG.reporters),
        langfuse=raw.get("langfuse", {}),
        langsmith=raw.get("langsmith", {}),
        braintrust=raw.get("braintrust", {}),
        basalt=raw.get("basalt", {}),
    )


def define_config(config: CobaltConfig) -> CobaltConfig:
    """Identity helper — mirrors TS ``defineConfig`` for IDE completion."""
    return config


def get_api_key(config: CobaltConfig) -> str | None:
    """Return the best available API key for LLM calls."""
    if config.judge.api_key:
        return config.judge.api_key
    if config.judge.provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    return os.environ.get("OPENAI_API_KEY")
