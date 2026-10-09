"""Concurrency fencing, production configuration and transport failure regression tests."""
from datetime import timedelta
from unittest.mock import Mock
import pytest
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from app.config import Settings
from app.contracts import GenerateInput
from app.models import GenerationJob, Source, Scenario, Attempt, utcnow
from app.rag import vector_matches
from app.scenarios import enqueue, claim_job, process_job
from test_grounding import context
from test_workflow import publish_one, investigate, answers


@pytest.mark.parametrize("values", [
    {"environment": "production"}, {"demo_mode": False}, {"allowed_origins": ["*"]},
    {"llm_timeout": 600}, {"rag_backend": "silent_fallback"},
])
def test_unsafe_configuration_refuses_startup(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_stale_worker_cannot_complete_claim(system):
    factory, settings, users = system
    with factory() as db:
        request, _, _ = context(db, settings)
        job = enqueue(db, users["instructor"], GenerateInput(**request, request_key="leased-job"), settings)
        first = claim_job(db)
        db.execute(update(GenerationJob).where(GenerationJob.id == job.id).values(lease_until=utcnow() - timedelta(seconds=1)))
        db.commit()
        second = claim_job(db)
        assert first[1] != second[1]
    provider = Mock()
    process_job(factory, settings, *first, provider=provider)
    provider.complete.assert_not_called()
    process_job(factory, settings, *second)
    with factory() as db:
        assert db.get(GenerationJob, job.id).status == "succeeded"


def test_revoked_source_stops_queued_generation(system):
    factory, settings, users = system
    with factory() as db:
        request, _, _ = context(db, settings)
        job = enqueue(db, users["instructor"], GenerateInput(**request, request_key="revoked-source"), settings)
        claim = claim_job(db)
        db.get(Source, "cnc-v1.manual.v1").approved = False
        db.commit()
    provider = Mock()
    process_job(factory, settings, *claim, provider=provider)
    provider.complete.assert_not_called()
    with factory() as db:
        assert db.get(GenerationJob, job.id).status == "failed"


def test_source_versions_are_immutable(system):
    factory, _, _ = system
    with factory() as db, pytest.raises(DBAPIError):
        db.execute(update(Source).where(Source.id == "cnc-v1.manual.v1").values(content={"text": "Replacement"}))


def test_completed_assessment_cannot_be_overwritten(clients):
    teacher, trainee, factory, _, _ = clients
    draft = publish_one(teacher)
    snapshot = investigate(trainee, draft)
    with factory() as db:
        body = answers(db, snapshot)
    assert trainee.post(f"/api/attempts/{snapshot['id']}/submit", json=body).status_code == 200
    with factory() as db, pytest.raises(DBAPIError):
        db.execute(update(Attempt).where(Attempt.id == snapshot["id"]).values(result={"score": 0}))


def test_rate_limit_and_size_limit_are_consistent_errors(clients):
    teacher, _, _, _, _ = clients
    for _ in range(20):
        response = teacher.post("/api/auth/login", json={"email": "unknown@example.test", "password": "invalid-input-value"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    response = teacher.post("/api/scenarios/generate", content="x" * 1_000_001)
    assert response.status_code == 413 and response.json()["error"]["code"] == "request_too_large"


def test_chroma_query_has_machine_and_id_filters(monkeypatch):
    collection = Mock()
    collection.query.return_value = {"metadatas": [[{"source_id": "wanted", "checksum": "fresh"},
        {"source_id": "irrelevant", "checksum": "fresh"}]], "distances": [[0.2, 0.99]]}
    monkeypatch.setattr("app.rag.embed", lambda *args: [[1.0, 0.0]])
    monkeypatch.setattr("app.rag.chroma_collection", lambda *args: collection)
    assert vector_matches(Settings(), "cnc-v1", ["wanted", "irrelevant"], "vibration") == {"wanted": "fresh"}
    assert collection.query.call_args.kwargs["where"] == {"$and": [{"machine_id": "cnc-v1"},
        {"source_id": {"$in": ["wanted", "irrelevant"]}}]}


def test_nonempty_provenance_is_required_in_database(system):
    factory, _, users = system
    with factory() as db:
        source = db.scalar(select(Scenario))
        invalid = Scenario(machine_id=source.machine_id, author_id=users["instructor"], difficulty="Beginner",
            generator_version="test/1", source_case_ids=[], source_manifest=[], payload=source.payload,
            content_hash=source.content_hash)
        db.add(invalid)
        with pytest.raises(DBAPIError):
            db.flush()
