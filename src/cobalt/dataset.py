"""Dataset — immutable, chainable test-data container."""

from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path
from typing import Any, Callable, Generic, Iterator, TypeVar

import httpx

from cobalt.types import ExperimentItem

T = TypeVar("T")


class Dataset(Generic[T]):
    """Immutable, chainable container for experiment data.

    Examples::

        ds = Dataset.from_items([{"input": "hello", "expected": "world"}])
        ds = Dataset.from_file("data.csv")
        ds = await Dataset.from_remote("https://example.com/data.jsonl")
    """

    def __init__(self, items: list[T]) -> None:
        self._items: list[T] = list(items)

    # ------------------------------------------------------------------
    # Class-method loaders
    # ------------------------------------------------------------------

    @classmethod
    def from_items(cls, items: list[T]) -> "Dataset[T]":
        return cls(items)

    @classmethod
    def from_file(cls, path: str) -> "Dataset[ExperimentItem]":
        """Auto-detect format from extension (json / jsonl / csv)."""
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix == ".jsonl":
            return cls.from_jsonl(path)
        if suffix == ".csv":
            return cls.from_csv(path)
        return cls.from_json(path)

    @classmethod
    def from_json(cls, path: str) -> "Dataset[ExperimentItem]":
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
        items: list[ExperimentItem] = data if isinstance(data, list) else data.get("items", [])
        return cls(items)

    @classmethod
    def from_jsonl(cls, path: str) -> "Dataset[ExperimentItem]":
        items: list[ExperimentItem] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
        return cls(items)

    @classmethod
    def from_csv(cls, path: str) -> "Dataset[ExperimentItem]":
        text = Path(path).read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(text))
        return cls(list(reader))  # type: ignore[arg-type]

    @classmethod
    async def from_remote(cls, url: str) -> "Dataset[ExperimentItem]":
        """Fetch JSON or JSONL from an HTTP/HTTPS URL."""
        async with httpx.AsyncClient() as client:
            resp = client.get(url, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            text = resp.text

        # Detect JSONL
        if "\n" in text.strip() and not text.strip().startswith("["):
            items: list[ExperimentItem] = [
                json.loads(line) for line in text.splitlines() if line.strip()
            ]
        else:
            data = json.loads(text)
            items = data if isinstance(data, list) else data.get("items", [])
        return cls(items)

    # ------------------------------------------------------------------
    # Remote platform loaders (thin HTTP wrappers)
    # ------------------------------------------------------------------

    @classmethod
    async def from_langfuse(
        cls,
        name: str,
        *,
        secret_key: str | None = None,
        public_key: str | None = None,
        base_url: str = "https://cloud.langfuse.com",
    ) -> "Dataset[ExperimentItem]":
        import os

        sk = secret_key or os.environ.get("LANGFUSE_SECRET_KEY", "")
        pk = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        async with httpx.AsyncClient(auth=(pk, sk)) as client:
            r = await client.get(f"{base_url}/api/public/datasets/{name}", timeout=30)
            r.raise_for_status()
            data = r.json()
        items = [
            {"input": row.get("input"), "expected_output": row.get("expectedOutput"), **row}
            for row in data.get("items", [])
        ]
        return cls(items)

    @classmethod
    async def from_langsmith(
        cls,
        name: str,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.smith.langchain.com",
    ) -> "Dataset[ExperimentItem]":
        import os

        key = api_key or os.environ.get("LANGSMITH_API_KEY", "")
        headers = {"x-api-key": key}
        async with httpx.AsyncClient(headers=headers) as client:
            r = await client.get(f"{base_url}/api/v1/datasets?name={name}", timeout=30)
            r.raise_for_status()
            dataset_id = r.json()[0]["id"]
            r2 = await client.get(f"{base_url}/api/v1/examples?dataset={dataset_id}", timeout=30)
            r2.raise_for_status()
        items = [
            {"input": row.get("inputs"), "expected_output": row.get("outputs"), **row}
            for row in r2.json()
        ]
        return cls(items)

    @classmethod
    async def from_braintrust(
        cls,
        project: str,
        dataset: str,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.braintrustdata.com",
    ) -> "Dataset[ExperimentItem]":
        import os

        key = api_key or os.environ.get("BRAINTRUST_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"}
        async with httpx.AsyncClient(headers=headers) as client:
            r = await client.get(
                f"{base_url}/v1/dataset",
                params={"project_name": project, "dataset_name": dataset},
                timeout=30,
            )
            r.raise_for_status()
        return cls(r.json().get("objects", []))

    @classmethod
    async def from_basalt(
        cls,
        dataset_id: str,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.getbasalt.ai",
    ) -> "Dataset[ExperimentItem]":
        import os

        key = api_key or os.environ.get("BASALT_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"}
        async with httpx.AsyncClient(headers=headers) as client:
            r = await client.get(f"{base_url}/v1/datasets/{dataset_id}/items", timeout=30)
            r.raise_for_status()
        return cls(r.json().get("items", []))

    # ------------------------------------------------------------------
    # Chainable transformations
    # ------------------------------------------------------------------

    def map(self, fn: Callable[[T, int], Any]) -> "Dataset[Any]":
        return Dataset([fn(item, i) for i, item in enumerate(self._items)])

    def filter(self, predicate: Callable[[T, int], bool]) -> "Dataset[T]":
        return Dataset([item for i, item in enumerate(self._items) if predicate(item, i)])

    def sample(self, n: int) -> "Dataset[T]":
        shuffled = random.sample(self._items, min(n, len(self._items)))
        return Dataset(shuffled)

    def slice(self, start: int, end: int | None = None) -> "Dataset[T]":
        return Dataset(self._items[start:end])

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __repr__(self) -> str:
        return f"Dataset({len(self._items)} items)"

    def items(self) -> list[T]:
        """Return a copy of the underlying item list."""
        return list(self._items)
