import pytest

from starter.src.embeddings import MyEmbedder


def test_embedder_contract_without_loading_model(tmp_path):
    embedder = MyEmbedder(cache_dir=tmp_path)
    assert embedder.model_name == "BAAI/bge-small-en-v1.5"
    assert embedder.dimensions == 384
    assert embedder.embed_documents([]) == []


def test_invalid_inputs_fail_before_model_download(tmp_path):
    embedder = MyEmbedder(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="nonempty"):
        embedder.embed_query(" ")
    with pytest.raises(ValueError, match="nonempty"):
        embedder.embed_documents([""])
    with pytest.raises(ValueError, match="supported"):
        MyEmbedder("unknown/model", cache_dir=tmp_path)

@pytest.mark.parametrize("raw, message", [
    ([[1.0] * 383], "dimensions"),
    ([[float("nan")] * 384], "nonfinite"),
    ([[0.0] * 384], "zero"),
    ([], "count"),
])
def test_rejects_invalid_provider_output(tmp_path, monkeypatch, raw, message):
    # Controlled adapter fixture exercises public validation without model download.
    # These vectors never enter a production embedder or a benchmark.
    class ProviderFixture:
        def embed(self, texts, batch_size):
            return iter(raw)

    embedder = MyEmbedder(cache_dir=tmp_path)
    monkeypatch.setattr(embedder, "_model", ProviderFixture())
    with pytest.raises(ValueError, match=message):
        embedder.embed_documents(["A document"])


def test_document_batch_order_and_query_adapter(tmp_path, monkeypatch):
    first = [1.0] + [0.0] * 383
    second = [0.0, 1.0] + [0.0] * 382

    class ProviderFixture:
        def embed(self, texts, batch_size):
            assert texts == ["first", "second"]
            assert batch_size == 4
            return iter([first, second])

        def query_embed(self, question):
            assert question == "A question?"
            return iter([second])

    embedder = MyEmbedder(cache_dir=tmp_path, batch_size=4)
    monkeypatch.setattr(embedder, "_model", ProviderFixture())
    assert embedder.embed_documents(["first", "second"]) == [first, second]
    assert embedder.embed_query("A question?") == second
