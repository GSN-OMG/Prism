from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    embedding_model: str
    embedding_dim: int


class Embedder(Protocol):
    embedding_model: str
    embedding_dim: int

    def embed(self, text: str) -> list[float]: ...


def _coerce_embedding(vector: Sequence[float]) -> list[float]:
    coerced: list[float] = []
    for value in vector:
        float_value = float(value)
        if not math.isfinite(float_value):
            raise ValueError("Embedding vector contains non-finite float.")
        coerced.append(float_value)
    return coerced


def compose_lesson_embedding_text(*, title: str, content: str, rationale: str) -> str:
    parts = [title.strip(), content.strip(), rationale.strip()]
    return "\n\n".join([p for p in parts if p])


class FakeEmbedder:
    def __init__(
        self, *, embedding_dim: int = 8, embedding_model: str = "fake/sha256@v1"
    ) -> None:
        if embedding_dim <= 0:
            raise ValueError("embedding_dim must be positive.")
        self.embedding_dim = embedding_dim
        self.embedding_model = embedding_model

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector: list[float] = []
        for i in range(self.embedding_dim):
            start = (i * 4) % len(digest)
            chunk = digest[start : start + 4]
            if len(chunk) < 4:
                chunk = (chunk + digest)[:4]
            value = int.from_bytes(chunk, "big", signed=False)
            vector.append(value / 2**32)
        return vector


class Model2VecEmbedder:
    def __init__(
        self,
        *,
        model: str,
        normalize: bool = True,
        force_download: bool = False,
    ) -> None:
        self._model_id = model
        self._normalize = normalize
        self._force_download = force_download

        self._model = None
        self.embedding_model = model
        self.embedding_dim = 0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Model2VecEmbedder:
        if env is None:
            env = os.environ

        model = env.get("PRISM_EMBEDDING_MODEL")
        if not model:
            raise RuntimeError(
                "Missing `PRISM_EMBEDDING_MODEL` env var (model2vec HF path)."
            )

        normalize = env.get("PRISM_EMBEDDING_NORMALIZE", "true").lower() in {
            "1",
            "true",
            "yes",
            "y",
        }
        force_download = env.get("PRISM_EMBEDDING_FORCE_DOWNLOAD", "false").lower() in {
            "1",
            "true",
            "yes",
            "y",
        }
        return cls(model=model, normalize=normalize, force_download=force_download)

    def _load(self) -> None:
        if self._model is not None:
            return

        from model2vec import StaticModel

        self._model = StaticModel.from_pretrained(
            self._model_id,
            normalize=self._normalize,
            force_download=self._force_download,
        )
        self.embedding_dim = int(self._model.dim)

    def embed(self, text: str) -> list[float]:
        self._load()
        assert self._model is not None
        result = self._model.encode(
            [text], show_progress_bar=False, use_multiprocessing=False
        )
        vector = result[0].tolist()
        return _coerce_embedding(vector)


def embed_text(*, embedder: Embedder, text: str) -> EmbeddingResult:
    vector = _coerce_embedding(embedder.embed(text))
    return EmbeddingResult(
        vector=vector,
        embedding_model=embedder.embedding_model,
        embedding_dim=embedder.embedding_dim or len(vector),
    )
