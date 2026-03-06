"""Cobalt — Unit testing for AI Agents.

Python port of https://github.com/basalt-ai/cobalt
"""

from cobalt.config import define_config, load_config
from cobalt.dataset import Dataset
from cobalt.evaluator import Evaluator
from cobalt.experiment import experiment
from cobalt.storage.db import HistoryDB
from cobalt.storage.results import list_results, load_result, save_result
from cobalt.types import (
    CIResult,
    CobaltConfig,
    EvalContext,
    EvalResult,
    ExperimentItem,
    ExperimentReport,
    ExperimentResult,
    ExperimentSummary,
    ItemEvaluation,
    ItemResult,
    JudgeConfig,
    ResultSummary,
    RunnerContext,
    ScoreStats,
    ThresholdConfig,
    ThresholdMetric,
    ThresholdViolation,
)

__all__ = [
    # Core
    "experiment",
    "Dataset",
    "Evaluator",
    # Config
    "load_config",
    "define_config",
    # Storage
    "HistoryDB",
    "save_result",
    "load_result",
    "list_results",
    # Types
    "ExperimentItem",
    "EvalContext",
    "EvalResult",
    "ExperimentResult",
    "ExperimentReport",
    "ExperimentSummary",
    "ItemResult",
    "ItemEvaluation",
    "ScoreStats",
    "CobaltConfig",
    "JudgeConfig",
    "ThresholdConfig",
    "ThresholdMetric",
    "ThresholdViolation",
    "CIResult",
    "ResultSummary",
    "RunnerContext",
]

__version__ = "0.1.0"
