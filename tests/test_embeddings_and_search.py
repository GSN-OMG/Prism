import pytest

from prism.embeddings import FakeEmbedder, compose_lesson_embedding_text, embed_text
from prism.phase3.embeddings_and_search import vector_literal


def test_compose_lesson_embedding_text_trims_and_joins() -> None:
    text = compose_lesson_embedding_text(title="  T  ", content="C", rationale="  R  ")
    assert text == "T\n\nC\n\nR"


def test_fake_embedder_is_deterministic_and_bounded() -> None:
    embedder = FakeEmbedder(embedding_dim=6)
    v1 = embedder.embed("hello")
    v2 = embedder.embed("hello")

    assert v1 == v2
    assert len(v1) == 6
    assert all(0.0 <= x <= 1.0 for x in v1)


def test_embed_text_includes_model_and_dim() -> None:
    embedder = FakeEmbedder(embedding_dim=3, embedding_model="fake/model@v1")
    res = embed_text(embedder=embedder, text="query")

    assert res.embedding_model == "fake/model@v1"
    assert res.embedding_dim == 3
    assert len(res.vector) == 3


def test_vector_literal_formats_pgvector_compatible_string() -> None:
    assert vector_literal([0.1, 1.0, -2.5]) == "[0.1,1.0,-2.5]"


def test_vector_literal_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError):
        vector_literal([float("nan")])
