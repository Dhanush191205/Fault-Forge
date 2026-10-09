"""Scenario service: durable admission, fenced generation, review and explicit publication."""
import logging
from datetime import timedelta
from sqlalchemy import select, update, func, or_, and_
from sqlalchemy.exc import IntegrityError
from .contracts import GenerateInput, Candidate
from .errors import DomainError
from .models import (GenerationJob, Scenario, ScenarioValidation, QuizItem, AuditEvent, Source, RateBucket, new_id, utcnow)
from .provider import generate_candidate, FixtureProvider, NvidiaProvider
from .rag import retrieve, content_hash, EvidenceBundle, source_snapshot
from .validation import validate_candidate

log = logging.getLogger("faultforge.generation")


def enqueue(db, user_id: str, request: GenerateInput, settings) -> GenerationJob:
    """Pin source hashes and queue an idempotent request; reject missing context before admitting a job."""
    values = request.model_dump()
    digest = content_hash(values)
    existing = db.scalar(select(GenerationJob).where(GenerationJob.owner_id == user_id,
                                                    GenerationJob.request_key == request.request_key))
    if existing:
        if existing.request_hash != digest:
            raise DomainError("idempotency_conflict", "This request key belongs to different inputs.", 409)
        return existing
    # Fail fast on approval and context checks. Vector work occurs only in the worker.
    sources = list(db.scalars(select(Source).where(Source.id.in_(request.source_ids),
                                                 Source.machine_id == request.machine_id, Source.approved.is_(True))))
    if len(sources) != len(set(request.source_ids)):
        raise DomainError("source_unavailable", "Select approved sources for the chosen machine.")
    bundle = EvidenceBundle(request.machine_id, tuple(source_snapshot(s) for s in sources))
    bundle.require_grounding()
    values["source_manifest"] = bundle.manifest()
    # Serialize capacity admission across replicas. This row is a mutex, not a per-process counter.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(RateBucket).values(key="generation-queue-admission", count=0).on_conflict_do_nothing())
    db.execute(update(RateBucket).where(RateBucket.key == "generation-queue-admission").values(count=0))
    queued = db.scalar(select(func.count()).select_from(GenerationJob).where(GenerationJob.status.in_(["queued", "running"])))
    if queued >= 100:
        raise DomainError("queue_full", "Generation is busy. Please try again later.", 429)
    job = GenerationJob(owner_id=user_id, request_key=request.request_key, request_hash=digest, request=values)
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(GenerationJob).where(GenerationJob.owner_id == user_id,
                                                        GenerationJob.request_key == request.request_key))
        if existing and existing.request_hash == digest:
            return existing
        raise DomainError("idempotency_conflict", "A conflicting generation request already exists.", 409) from None
    return job


def claim_job(db) -> tuple[str, str] | None:
    """Claim one queued/expired job under a row lock and CAS; return ID/token or None if idle."""
    now = utcnow()
    eligible = or_(GenerationJob.status == "queued", and_(GenerationJob.status == "running", GenerationJob.lease_until < now))
    job = db.scalar(select(GenerationJob).where(eligible).order_by(GenerationJob.created_at)
                    .with_for_update(skip_locked=True).limit(1))
    if not job:
        db.rollback()
        return None
    if job.tries >= 3:
        job.status, job.error_code = "failed", "worker_retry_exhausted"
        db.commit()
        return None
    token = new_id()
    changed = db.execute(update(GenerationJob).where(GenerationJob.id == job.id, eligible)
        .values(status="running", token=token, lease_until=now + timedelta(minutes=5), tries=GenerationJob.tries + 1)).rowcount
    db.commit()
    return (job.id, token) if changed else None


def persist_validated(db, owner_id: str, candidate: Candidate, bundle: EvidenceBundle, request: dict,
                      generator_version: str, job_id: str | None = None) -> Scenario:
    """Validate before writing, then atomically stage scenario/validation/quiz rows; caller commits."""
    payload = validate_candidate(db, candidate, bundle, request)
    scenario = Scenario(machine_id=candidate.machine_id, author_id=owner_id, difficulty=candidate.difficulty,
        generator_version=generator_version, source_case_ids=[candidate.case_id], source_manifest=bundle.manifest(),
        payload=payload, content_hash=content_hash(payload), status="draft")
    db.add(scenario)
    db.flush()
    db.add(ScenarioValidation(scenario_id=scenario.id, job_id=job_id, stage="automatic", passed=True,
        content_hash=scenario.content_hash, checks={"components": True, "sensors": True, "joint_state": True,
        "citations": True, "difficulty": True, "approved_prose": True, "safety": True}))
    for q in payload["quiz"]:
        db.add(QuizItem(scenario_id=scenario.id, payload=q))
    db.add(AuditEvent(actor_id=owner_id, action="scenario_validated", target_id=scenario.id,
                      details={"hash": scenario.content_hash, "generator_version": generator_version}))
    return scenario


def process_job(factory, settings, job_id: str, token: str, provider=None) -> None:
    """Run retrieval/generation outside long transactions; fence stale completion and log safe rejections."""
    try:
        with factory() as db:
            job = db.get(GenerationJob, job_id)
            if not job or job.token != token or job.status != "running":
                return
            request, owner_id = job.request, job.owner_id
            bundle = retrieve(db, settings, request["machine_id"], request["source_ids"], request["brief"])
            pinned = {x["id"]: x["checksum"] for x in request["source_manifest"]}
            if any(pinned.get(x["id"]) != x["checksum"] for x in bundle.sources):
                raise DomainError("source_changed", "A source changed after this request was admitted.")
        adapter = provider or (FixtureProvider() if settings.llm_provider == "fixture" else NvidiaProvider(settings))
        candidate = generate_candidate(adapter, bundle, request)
        with factory() as db:
            job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id,
                GenerationJob.token == token, GenerationJob.status == "running",
                GenerationJob.lease_until > utcnow()).with_for_update())
            if not job:
                return
            check_sources(db, bundle.manifest())
            scenario = persist_validated(db, owner_id, candidate, bundle, request,
                settings.generator_version + ("/fixture" if settings.llm_provider == "fixture" else "/" + settings.llm_model), job.id)
            job.status, job.scenario_id = "succeeded", scenario.id
            db.commit()
    except Exception as exc:
        code = exc.code if isinstance(exc, DomainError) else "generation_failed"
        log.warning("generation_rejected job=%s code=%s", job_id, code)
        with factory() as db:
            job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id, GenerationJob.token == token,
                GenerationJob.status == "running", GenerationJob.lease_until > utcnow()).with_for_update())
            if job:
                job.status, job.error_code = "failed", code
                db.add(ScenarioValidation(job_id=job.id, stage="automatic", passed=False, checks={"error_code": code}))
                db.add(AuditEvent(actor_id=job.owner_id, action="generation_rejected", target_id=job.id, details={"code": code}))
                db.commit()


def check_sources(db, manifest: list[dict]) -> None:
    """Recheck all pinned source approvals and hashes; raise before commit or publication on drift."""
    for item in manifest:
        source = db.scalar(select(Source).where(Source.id == item["id"]).with_for_update())
        if not source or not source.approved or source.checksum != item["checksum"] or content_hash(source.content) != item["checksum"]:
            raise DomainError("source_changed", "A pinned source has changed or its approval was revoked.", 409)


def publish(db, scenario_id: str, reviewer_id: str, reviewed_hash: str) -> Scenario:
    """Publish only the reviewed immutable hash after automatic validation; repeated approval is idempotent."""
    row = db.scalar(select(Scenario).where(Scenario.id == scenario_id).with_for_update())
    if not row:
        raise DomainError("not_found", "Scenario not found.", 404)
    if row.content_hash != reviewed_hash or content_hash(row.payload) != reviewed_hash:
        raise DomainError("review_conflict", "The scenario changed. Review the current version.", 409)
    if row.status == "published":
        return row
    if row.status != "draft":
        raise DomainError("retired", "Retired scenarios cannot be republished.", 409)
    validation = db.scalar(select(ScenarioValidation).where(ScenarioValidation.scenario_id == row.id,
        ScenarioValidation.stage == "automatic", ScenarioValidation.passed.is_(True), ScenarioValidation.content_hash == reviewed_hash))
    if not validation:
        raise DomainError("validation_required", "Automatic validation is required before publication.", 409)
    check_sources(db, row.source_manifest)
    from .validation import validate_readings
    validate_readings(db, row.machine_id, row.payload["readings"])
    row.status = "published"
    db.add(ScenarioValidation(scenario_id=row.id, reviewer_id=reviewer_id, stage="instructor", passed=True,
        content_hash=reviewed_hash, checks={"safety_reviewed": True, "grounding_reviewed": True}))
    db.add(AuditEvent(actor_id=reviewer_id, action="scenario_published", target_id=row.id, details={"hash": reviewed_hash}))
    db.commit()
    return row


def retire(db, scenario_id: str, actor_id: str) -> None:
    """Soft-retire a scenario; retain its quiz, validations and historical attempts without mutation."""
    row = db.get(Scenario, scenario_id)
    if not row:
        raise DomainError("not_found", "Scenario not found.", 404)
    row.status, row.deleted_at = "retired", utcnow()
    db.add(AuditEvent(actor_id=actor_id, action="scenario_retired", target_id=row.id, details={"hash": row.content_hash}))
    db.commit()
