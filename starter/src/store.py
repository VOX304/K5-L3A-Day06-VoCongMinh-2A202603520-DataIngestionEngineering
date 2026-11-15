"""Persistent embedded Qdrant backend; no PostgreSQL server or API keys needed.

Each strategy owns a collection. Upsert replaces its complete chunk snapshot,
validating all records before writes, then removing stale IDs after new writes.
This is not a transaction: an interrupted write must be retried with the snapshot.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .models import Chunk


class QdrantVectorStore:
    def __init__(self, path: str | Path, dimensions: int) -> None:
        if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions < 1:
            raise ValueError("dimensions must be a positive integer")
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:
            raise RuntimeError("Install starter/requirements.txt to use local Qdrant") from exc
        self.dimensions = dimensions
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._models = models
        self._client = QdrantClient(path=str(self.path))

    def create_schema(self) -> None:
        """Collections are created lazily by upsert, one per strategy."""

    @staticmethod
    def _collection(strategy: str) -> str:
        if not isinstance(strategy, str) or not strategy.strip():
            raise ValueError("strategy must be a nonempty string")
        return "lab06_" + hashlib.sha256(strategy.encode("utf-8")).hexdigest()

    def _ensure_collection(self, collection: str, create: bool = False) -> bool:
        if not self._client.collection_exists(collection):
            if not create:
                return False
            self._client.create_collection(
                collection, vectors_config=self._models.VectorParams(
                    size=self.dimensions, distance=self._models.Distance.COSINE))
        config = self._client.get_collection(collection).config.params.vectors
        if not isinstance(config, self._models.VectorParams) or config.size != self.dimensions:
            raise ValueError("Stored collection dimensions do not match embedder dimensions")
        if config.distance != self._models.Distance.COSINE:
            raise ValueError("Stored collection must use cosine distance")
        return True

    def _vector(self, vector: list[float]) -> list[float]:
        if len(vector) != self.dimensions:
            raise ValueError("Vector dimensions do not match store dimensions")
        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError) as exc:
            raise ValueError("Vector values must be finite numbers") from exc
        if any(isinstance(value, (bool, str)) for value in vector):
            raise ValueError("Vector values must be numbers")
        if not all(math.isfinite(value) for value in values) or not any(values):
            raise ValueError("Vector must be finite and nonzero for cosine search")
        return values

    @staticmethod
    def _key(key: str) -> None:
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise ValueError("Metadata keys must be simple names without nested paths")

    @staticmethod
    def _scalar(value: Any) -> None:
        if not isinstance(value, (str, bool, int, float)):
            raise ValueError("Metadata/filter values must be string, boolean, integer or float scalars")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Metadata/filter numbers must be finite")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace all chunks for strategy, preserving other strategies."""
        collection = self._collection(strategy)
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and vector counts must match")
        points = []
        seen = set()
        for chunk, vector in zip(chunks, vectors):
            if not isinstance(chunk.chunk_id, str) or not chunk.chunk_id.strip():
                raise ValueError("chunk_id must be a nonempty string")
            if chunk.chunk_id in seen:
                raise ValueError("Duplicate chunk_id in snapshot")
            seen.add(chunk.chunk_id)
            if not isinstance(chunk.document_id, str) or not chunk.document_id.strip():
                raise ValueError("document_id must be a nonempty string")
            if not isinstance(chunk.source, str) or not chunk.source.strip():
                raise ValueError("source must be a nonempty string")
            if isinstance(chunk.page, bool) or not isinstance(chunk.page, int) or chunk.page < 1:
                raise ValueError("page must be a positive integer")
            if not isinstance(chunk.text, str) or not chunk.text.strip():
                raise ValueError("Chunk text must be a nonempty string")
            metadata = dict(chunk.metadata)
            for key, value in metadata.items():
                self._key(key)
                self._scalar(value)
            metadata.update(document_id=chunk.document_id, source=chunk.source, page=chunk.page)
            points.append(self._models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, strategy + "\0" + chunk.chunk_id)),
                vector=self._vector(vector),
                payload={"chunk_id": chunk.chunk_id, "text": chunk.text, "metadata": metadata}))
        # No changes occur until every record above has passed validation.
        self._ensure_collection(collection, create=True)
        if points:
            self._client.upsert(collection, points=points, wait=True)
            stale_filter = self._models.Filter(must_not=[
                self._models.HasIdCondition(has_id=[point.id for point in points])])
        else:
            stale_filter = self._models.Filter()
        self._client.delete(collection, points_selector=self._models.FilterSelector(
            filter=stale_filter), wait=True)

    def _filter(self, filters: dict[str, Any] | None) -> Any:
        conditions: list[Any] = []
        if filters is not None and not isinstance(filters, dict):
            raise ValueError("filters must be a dictionary")
        for key, value in (filters or {}).items():
            self._key(key)
            self._scalar(value)
            if isinstance(value, float):
                conditions.append(self._models.FieldCondition(
                    key="metadata." + key, range=self._models.Range(gte=value, lte=value)))
            else:
                conditions.append(self._models.FieldCondition(
                    key="metadata." + key, match=self._models.MatchValue(value=value)))
        return self._models.Filter(must=conditions) if conditions else None

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        collection = self._collection(strategy)
        vector = self._vector(query_vector)
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        query_filter = self._filter(filters)
        if not self._ensure_collection(collection):
            return []
        result = self._client.query_points(collection_name=collection, query=vector,
                                           query_filter=query_filter, limit=top_k,
                                           with_payload=True, with_vectors=False)
        hits = []
        for point in result.points:
            payload = point.payload or {}
            hits.append({"chunk_id": payload["chunk_id"], "text": payload["text"],
                         "score": float(point.score), "metadata": dict(payload["metadata"])})
        return hits

    def count(self, strategy: str) -> int:
        collection = self._collection(strategy)
        if not self._ensure_collection(collection):
            return 0
        return int(self._client.count(collection_name=collection, exact=True).count)

    def close(self) -> None:
        self._client.close()

    def snapshot_digest(self, strategy: str) -> str:
        """Fingerprint the disk snapshot, also making subsequent search use it.

        Qdrant local 1.20 returns normalized float32 vectors immediately after
        upsert but loads original persisted vectors on restart. Reopen before
        hashing so dev and test compare exactly the same persisted representation,
        without rounding away vector mutations or weakening the freeze check.
        """
        from qdrant_client import QdrantClient
        self._client.close()
        self._client = QdrantClient(path=str(self.path))
        collection = self._collection(strategy)
        if not self._ensure_collection(collection):
            raise ValueError('Snapshot collection does not exist')
        records: list[dict[str, Any]] = []
        offset = None
        while True:
            points, offset = self._client.scroll(collection_name=collection, limit=256,
                                                offset=offset, with_payload=True, with_vectors=True)
            records.extend({'id': str(p.id), 'payload': p.payload, 'vector': p.vector} for p in points)
            if offset is None:
                break
        records.sort(key=lambda p: p['id'])
        return hashlib.sha256(json.dumps(records, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def __enter__(self) -> QdrantVectorStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
