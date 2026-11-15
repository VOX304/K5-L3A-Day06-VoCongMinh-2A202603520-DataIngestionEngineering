"""Local ONNX embeddings, with model files cached on disk by FastEmbed."""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    """Real BGE inference through FastEmbed; never substitutes synthetic vectors.

    Initialization is lazy: the first nonempty request loads/downloads the model.
    Set MODEL_CACHE_DIR or pass cache_dir to reuse model files across runs.
    """

    dimensions = 384
    DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 cache_dir: str | Path | None = None, batch_size: int = 32) -> None:
        if model_name != self.DEFAULT_MODEL:
            raise ValueError(f"Only supported model is {self.DEFAULT_MODEL}")
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        self.model_name = model_name
        self.batch_size = batch_size
        self.cache_dir = Path(cache_dir or os.environ.get("MODEL_CACHE_DIR")
                              or Path(__file__).resolve().parents[2] / ".cache" / "fastembed")
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError("Install starter/requirements.txt to use FastEmbed") from exc
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(model_name=self.model_name,
                                        cache_dir=str(self.cache_dir),
                                        providers=["CPUExecutionProvider"])
        return self._model

    @staticmethod
    def _validate_text(text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Embedding inputs must be nonempty strings")

    def _validate_vectors(self, raw_vectors: Any, expected: int) -> list[list[float]]:
        vectors = [[float(value) for value in vector] for vector in raw_vectors]
        if len(vectors) != expected:
            raise ValueError("Embedding provider returned an unexpected vector count")
        for vector in vectors:
            if len(vector) != self.dimensions or not all(math.isfinite(x) for x in vector):
                raise ValueError("Embedding provider returned invalid dimensions or nonfinite values")
            if not any(vector):
                raise ValueError("Embedding provider returned a zero vector")
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        for text in texts:
            self._validate_text(text)
        if not texts:
            return []
        return self._validate_vectors(
            self._load_model().embed(texts, batch_size=self.batch_size), len(texts))

    def embed_query(self, question: str) -> list[float]:
        self._validate_text(question)
        return self._validate_vectors(self._load_model().query_embed(question), 1)[0]
