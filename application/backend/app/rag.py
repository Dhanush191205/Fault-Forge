"""Scoped RAG interface: empty or irrelevant evidence never falls through to generation."""
import hashlib
import json
from dataclasses import dataclass
import httpx
from sqlalchemy import select
from .errors import DomainError
from .models import Source


def content_hash(value) -> str:
    """Return a canonical JSON SHA-256; unsupported/nonfinite values raise ValueError/TypeError."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class EvidenceBundle:
    """Validated source snapshot that must contain a failure case and its manual evidence."""
    machine_id: str
    sources: tuple[dict, ...]

    def require_grounding(self) -> None:
        """Check source scope, kinds and nonempty content; raise before every model invocation."""
        kinds = {x["kind"] for x in self.sources if x.get("content")}
        if not {"case", "manual"}.issubset(kinds) or any(x["machine_id"] != self.machine_id for x in self.sources):
            raise DomainError("insufficient_evidence", "Select a matching failure case and manual with usable evidence.")

    def manifest(self) -> list[dict]:
        """Return immutable source IDs and checksums for provenance; no external work is performed."""
        return [{"id": x["id"], "checksum": x["checksum"], "title": x["title"], "locator": x["locator"]} for x in self.sources]


def source_snapshot(source: Source) -> dict:
    """Project an authorized source record for internal RAG; caller owns access checks."""
    return {"id": source.id, "kind": source.kind, "machine_id": source.machine_id,
            "title": source.title, "locator": source.locator, "content": source.content,
            "checksum": source.checksum}


def retrieve(db, settings, machine_id: str, source_ids: list[str], query: str) -> EvidenceBundle:
    """Retrieve pinned approved sources using configured backend; reject misses, scope drift and outages."""
    rows = list(db.scalars(select(Source).where(Source.id.in_(source_ids), Source.machine_id == machine_id,
                                               Source.approved.is_(True))))
    if len(rows) != len(set(source_ids)) or any(content_hash(s.content) != s.checksum for s in rows):
        raise DomainError("source_unavailable", "Selected sources are missing, changed, or unapproved.")
    if not settings.demo_mode and any(s.synthetic for s in rows):
        raise DomainError("synthetic_source", "Production generation requires approved equipment-specific sources.")
    if settings.llm_provider == "nvidia" and any(not s.external_inference_allowed for s in rows):
        raise DomainError("source_permission", "Selected sources are not approved for this inference provider.")
    if settings.rag_backend == "chroma":
        matches = vector_matches(settings, machine_id, source_ids, query)
        rows = [s for s in rows if s.id in matches and matches[s.id] == s.checksum]
    elif not settings.demo_mode:
        raise DomainError("fixture_disabled", "Fixture retrieval is disabled.", 503)
    bundle = EvidenceBundle(machine_id, tuple(source_snapshot(s) for s in rows))
    bundle.require_grounding()
    case_sources = [s for s in rows if s.kind == "case"]
    if not case_sources or not any(set(s.content["manual_ids"]).issubset({r.id for r in rows}) for s in case_sources):
        raise DomainError("insufficient_evidence", "Retrieval did not find the case's required manual evidence.")
    return bundle


def embed(settings, texts: list[str], input_type: str) -> list[list[float]]:
    """Request NVIDIA-compatible embeddings; provider/shape failures become handled retrieval errors."""
    if not settings.embedding_model:
        raise DomainError("embedding_not_configured", "Configure an embedding model before indexing.", 503)
    try:
        with httpx.Client(timeout=30) as client:
            result = client.post(settings.embedding_base_url.rstrip("/") + "/embeddings",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={"model": settings.embedding_model, "input": texts, "input_type": input_type})
            result.raise_for_status()
            rows = sorted(result.json()["data"], key=lambda x: x["index"])
            vectors = [r["embedding"] for r in rows]
            if len(vectors) != len(texts) or any(not v for v in vectors):
                raise ValueError("Invalid embedding count")
            return vectors
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise DomainError("embedding_unavailable", "The embedding service is unavailable.", 503) from exc


def chroma_collection(settings, create: bool = False):
    """Open the configured remote Chroma collection without implicit downloads or fallback stores."""
    try:
        import chromadb
        headers = {"Authorization": f"Bearer {settings.chroma_token}"} if settings.chroma_token else None
        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                                    ssl=settings.chroma_ssl, headers=headers)
        if create:
            return client.get_or_create_collection(settings.chroma_collection, embedding_function=None,
                                                   metadata={"hnsw:space": "cosine"})
        return client.get_collection(settings.chroma_collection, embedding_function=None)
    except Exception as exc:
        raise DomainError("retrieval_unavailable", "The vector store is unavailable.", 503) from exc


def vector_matches(settings, machine_id: str, source_ids: list[str], query: str) -> dict[str, str]:
    """Query bounded cosine neighbors with mandatory machine and selected-ID filters; return fresh matches."""
    vector = embed(settings, [query], "query")
    try:
        result = chroma_collection(settings).query(query_embeddings=vector, n_results=min(12, len(source_ids)),
            where={"$and": [{"machine_id": machine_id}, {"source_id": {"$in": source_ids}}]},
            include=["metadatas", "distances"])
        return {metadata["source_id"]: metadata["checksum"]
                for metadata, distance in zip(result["metadatas"][0], result["distances"][0], strict=True)
                if distance <= settings.retrieval_max_distance}
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError("retrieval_unavailable", "The vector store could not retrieve evidence.", 503) from exc


def index_sources(db, settings) -> int:
    """Index approved permissioned sources with explicit embeddings; return count or fail without fallback."""
    sources = list(db.scalars(select(Source).where(Source.approved.is_(True), Source.external_inference_allowed.is_(True))))
    if not settings.demo_mode:
        sources = [s for s in sources if not s.synthetic]
    collection = chroma_collection(settings, create=True)
    for start in range(0, len(sources), 16):
        batch = sources[start:start + 16]
        documents = [json.dumps(s.content, ensure_ascii=True) for s in batch]
        vectors = embed(settings, documents, "passage")
        collection.upsert(ids=[s.id for s in batch], documents=documents, embeddings=vectors,
            metadatas=[{"machine_id": s.machine_id, "source_id": s.id, "kind": s.kind,
                        "checksum": s.checksum} for s in batch])
    return len(sources)
