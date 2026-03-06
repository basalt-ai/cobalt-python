"""Core types for the Cobalt AI testing framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Primitive aliases
# ---------------------------------------------------------------------------

ExperimentItem = dict[str, Any]


# ---------------------------------------------------------------------------
# Evaluation types
# ---------------------------------------------------------------------------


@dataclass
class EvalContext:
    item: ExperimentItem
    output: str | dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    score: float  # 0.0 – 1.0
    reason: str | None = None
    chain_of_thought: str | None = None


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------


@dataclass
class ScoreStats:
    avg: float
    min: float
    max: float
    p50: float
    p95: float
    p99: float


@dataclass
class ItemEvaluation:
    score: float
    reason: str | None = None
    chain_of_thought: str | None = None


@dataclass
class ExperimentResult:
    output: str | dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ItemResult:
    index: int
    input: ExperimentItem
    output: ExperimentResult
    latency_ms: float
    evaluations: dict[str, ItemEvaluation]
    error: str | None = None


@dataclass
class ExperimentSummary:
    total_items: int
    total_duration_ms: float
    avg_latency_ms: float
    total_tokens: int | None = None
    estimated_cost: float | None = None
    scores: dict[str, ScoreStats] = field(default_factory=dict)


@dataclass
class ExperimentReport:
    id: str
    name: str
    timestamp: str
    tags: list[str]
    config: dict[str, Any]
    summary: ExperimentSummary
    items: list[ItemResult]


# ---------------------------------------------------------------------------
# Config types
# ---------------------------------------------------------------------------


@dataclass
class JudgeConfig:
    model: str = "gpt-4o-mini"
    provider: Literal["openai", "anthropic"] = "openai"
    api_key: str | None = None


@dataclass
class CobaltConfig:
    test_dir: str = "./experiments"
    test_match: list[str] = field(default_factory=lambda: ["**/*.cobalt.py"])
    judge: JudgeConfig = field(default_factory=JudgeConfig)
    concurrency: int = 5
    timeout: float = 30.0
    reporters: list[str] = field(default_factory=lambda: ["cli"])
    langfuse: dict[str, str] = field(default_factory=dict)
    langsmith: dict[str, str] = field(default_factory=dict)
    braintrust: dict[str, str] = field(default_factory=dict)
    basalt: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CI / threshold types
# ---------------------------------------------------------------------------


@dataclass
class ThresholdMetric:
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None
    pass_rate: float | None = None  # fraction 0–1 of items that must pass
    min_score: float | None = None  # minimum score for pass_rate counting


@dataclass
class ThresholdConfig:
    score: ThresholdMetric | None = None
    latency: ThresholdMetric | None = None
    evaluators: dict[str, ThresholdMetric] = field(default_factory=dict)


@dataclass
class ThresholdViolation:
    category: str
    metric: str
    expected: float
    actual: float
    message: str


@dataclass
class CIResult:
    passed: bool
    violations: list[ThresholdViolation]
    summary: str


# ---------------------------------------------------------------------------
# Storage types
# ---------------------------------------------------------------------------


@dataclass
class ResultSummary:
    id: str
    name: str
    timestamp: str
    tags: list[str]
    avg_scores: dict[str, float]
    total_items: int
    duration_ms: float


# ---------------------------------------------------------------------------
# Runner types
# ---------------------------------------------------------------------------


@dataclass
class RunnerContext:
    item: ExperimentItem
    index: int
    run_index: int = 0
