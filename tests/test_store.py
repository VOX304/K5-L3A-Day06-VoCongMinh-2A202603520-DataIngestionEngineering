"""Public-interface tests; small hand vectors are fixtures, never benchmark data."""
import pytest

from starter.src.models import Chunk
from starter.src.store import QdrantVectorStore


def test_reject_invalid_dimensions_before_opening_database(tmp_path):
    with pytest.raises(ValueError, match="dimensions"):
        QdrantVectorStore(tmp_path / "vectors", dimensions=0)


@pytest.fixture
def store(tmp_path):
    pytest.importorskip("qdrant_client", reason="Install starter/requirements.txt for local Qdrant integration tests")
    with QdrantVectorStore(tmp_path / "vectors", dimensions=3) as instance:
        yield instance


def chunk(identifier, source="a.pdf", page=1, **metadata):
    return Chunk(identifier, source, source, page, "Text " + identifier, metadata)


def test_snapshot_ranking_filters_and_replacement(store):
    chunks = [chunk("a", topic="alpha"), chunk("b", "b.pdf", 2, topic="beta")]
    store.upsert("fixed", chunks, [[1, 0, 0], [0, 1, 0]])
    original_digest = store.snapshot_digest('fixed')
    store.upsert("fixed", chunks, [[1, 0, 0], [0, 1, 0]])
    assert store.snapshot_digest('fixed') == original_digest
    assert store.count("fixed") == 2
    hits = store.search("fixed", [1, 0, 0])
    assert hits[0]["chunk_id"] == "a"
    assert hits[0]["score"] == pytest.approx(1)
    assert hits[0]["metadata"]["source"] == "a.pdf"
    assert store.search("fixed", [1, 0, 0], filters={"source": "b.pdf"})[0]["chunk_id"] == "b"
    assert store.search("fixed", [1, 0, 0], filters={"page": 2, "topic": "beta"})[0]["chunk_id"] == "b"
    assert store.search("fixed", [1, 0, 0], filters={"topic": "missing"}) == []
    store.upsert("semantic", [chunk("c")], [[0, 0, 1]])
    store.upsert("fixed", [chunk("new")], [[1, 0, 0]])
    assert store.snapshot_digest('fixed') != original_digest
    assert store.count("fixed") == 1
    assert store.search("fixed", [1, 0, 0])[0]["chunk_id"] == "new"
    assert store.count("semantic") == 1
    store.upsert("fixed", [], [])
    assert store.count("fixed") == 0


def test_validation_leaves_snapshot_untouched(store):
    store.upsert("fixed", [chunk("a")], [[1, 0, 0]])
    for vectors in ([], [[1, 2]], [[float("nan"), 0, 1]], [[0, 0, 0]]):
        with pytest.raises(ValueError):
            store.upsert("fixed", [chunk("bad")], vectors)
    with pytest.raises(ValueError, match="Duplicate"):
        store.upsert("fixed", [chunk("a"), chunk("a")], [[1, 0, 0], [0, 1, 0]])
    with pytest.raises(ValueError):
        store.search("fixed", [1, 0, 0], filters={"page": [1]})
    with pytest.raises(ValueError):
        store.search("fixed", [1, 0, 0], filters={"metadata.topic": "x"})
    assert store.count("fixed") == 1
    assert store.search("fixed", [1, 0, 0])[0]["chunk_id"] == "a"


def test_persistence_and_dimension_compatibility(tmp_path):
    pytest.importorskip("qdrant_client", reason="Install starter/requirements.txt for local Qdrant integration tests")
    path = tmp_path / "vectors"
    with QdrantVectorStore(path, dimensions=3) as store:
        store.upsert("fixed", [chunk("a")], [[1, 0, 0]])
    with QdrantVectorStore(path, dimensions=3) as reopened:
        assert reopened.count("fixed") == 1
        assert reopened.search("fixed", [1, 0, 0])[0]["chunk_id"] == "a"
    with QdrantVectorStore(path, dimensions=4) as mismatch:
        with pytest.raises(ValueError, match="dimensions"):
            mismatch.search("fixed", [1, 0, 0, 0])


def test_frozen_digest_survives_reload_for_non_axis_vectors(tmp_path):
    pytest.importorskip('qdrant_client')
    path = tmp_path / 'vectors'
    with QdrantVectorStore(path, dimensions=3) as store:
        store.upsert('A', [chunk('fixture')], [[0.2, 0.3, 0.4]])
        before = store.snapshot_digest('A')
    with QdrantVectorStore(path, dimensions=3) as reopened:
        assert reopened.snapshot_digest('A') == before, 'Unchanged frozen index must survive reload'
        reopened.upsert('A', [chunk('fixture')], [[0.4, 0.3, 0.2]])
        assert reopened.count('A') == 1
        assert reopened.snapshot_digest('A') != before, 'Same-count vector mutation must invalidate freeze'
