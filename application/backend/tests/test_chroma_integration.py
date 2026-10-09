"""Exercise the installed Chroma engine with supplied vectors and no network/model downloads."""
import secrets
import pytest
from sqlalchemy import select
from app.models import Source
from app.rag import retrieve
from app.errors import DomainError


@pytest.mark.parametrize("stale", [False, True])
def test_real_chroma_scope_and_source_freshness(system, monkeypatch, stale):
    chromadb = pytest.importorskip("chromadb")
    from chromadb.config import Settings as ChromaSettings
    client = chromadb.EphemeralClient(settings=ChromaSettings(anonymized_telemetry=False))
    name = "ff_test_" + secrets.token_hex(8)
    collection = client.create_collection(name, embedding_function=None, metadata={"hnsw:space": "cosine"})
    factory, settings, _ = system
    try:
        with factory() as db:
            sources = list(db.scalars(select(Source)))
            collection.add(ids=[s.id for s in sources], embeddings=[[1.0, 0.0] for _ in sources],
                metadatas=[{"source_id": s.id, "machine_id": s.machine_id,
                            "checksum": "stale" if stale else s.checksum} for s in sources])
            monkeypatch.setattr("app.rag.chroma_collection", lambda *args: collection)
            monkeypatch.setattr("app.rag.embed", lambda *args: [[1.0, 0.0]])
            config = settings.model_copy(update={"rag_backend": "chroma"})
            if stale:
                with pytest.raises(DomainError):
                    retrieve(db, config, "cnc-v1", ["cnc-v1.case.v1", "cnc-v1.manual.v1"], "tooling")
            else:
                result = retrieve(db, config, "cnc-v1", ["cnc-v1.case.v1", "cnc-v1.manual.v1"], "tooling")
                assert {s["id"] for s in result.sources} == {"cnc-v1.case.v1", "cnc-v1.manual.v1"}
                assert all(s["machine_id"] == "cnc-v1" for s in result.sources)
    finally:
        client.delete_collection(name)
