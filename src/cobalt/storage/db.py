"""SQLite history database for experiment runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from cobalt.types import ExperimentReport, ResultSummary

_DB_PATH = Path.home() / ".cobalt" / "history.db"


class HistoryDB:
    """Lightweight SQLite store for run summaries."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else _DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                tags            TEXT NOT NULL DEFAULT '[]',
                total_items     INTEGER NOT NULL DEFAULT 0,
                duration_ms     REAL NOT NULL DEFAULT 0,
                avg_latency_ms  REAL NOT NULL DEFAULT 0,
                scores          TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        self._conn.commit()

    def insert_run(self, report: ExperimentReport) -> None:
        avg_scores = {
            name: stats.avg for name, stats in report.summary.scores.items()
        }
        self._conn.execute(
            """
            INSERT OR REPLACE INTO runs
                (id, name, timestamp, tags, total_items, duration_ms, avg_latency_ms, scores)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.id,
                report.name,
                report.timestamp,
                json.dumps(report.tags),
                report.summary.total_items,
                report.summary.total_duration_ms,
                report.summary.avg_latency_ms,
                json.dumps(avg_scores),
            ),
        )
        self._conn.commit()

    def list_runs(
        self,
        experiment: str | None = None,
        limit: int = 50,
    ) -> list[ResultSummary]:
        query = "SELECT id, name, timestamp, tags, total_items, duration_ms, avg_latency_ms, scores FROM runs"
        params: list[Any] = []
        if experiment:
            query += " WHERE name = ?"
            params.append(experiment)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [
            ResultSummary(
                id=row[0],
                name=row[1],
                timestamp=row[2],
                tags=json.loads(row[3]),
                total_items=row[4],
                duration_ms=row[5],
                avg_scores=json.loads(row[7]),
            )
            for row in rows
        ]

    def get_run(self, run_id: str) -> ResultSummary | None:
        row = self._conn.execute(
            "SELECT id, name, timestamp, tags, total_items, duration_ms, avg_latency_ms, scores FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return ResultSummary(
            id=row[0],
            name=row[1],
            timestamp=row[2],
            tags=json.loads(row[3]),
            total_items=row[4],
            duration_ms=row[5],
            avg_scores=json.loads(row[7]),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "HistoryDB":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
