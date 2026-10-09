"""Persistent, versioned domain records. Published payloads and grades are append-only."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def new_id() -> str:
    """Return a random record identifier; takes no input and has no domain failure mode."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Return the current aware UTC time for server-owned audit fields."""
    return datetime.now(timezone.utc)


class User(Base):
    """Local identity with an explicit instructor/trainee role."""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("role IN ('instructor','trainee')"),)


class AuthSession(Base):
    """Hashed opaque sessions; only the HttpOnly cookie contains the bearer secret."""
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class RateBucket(Base):
    """Shared, database-backed admission counters, including failed login attempts."""
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Machine(Base):
    """Versioned configuration and geometry; adding machines does not change engine logic."""
    __tablename__ = "machines"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSON)


class Component(Base):
    """Component Schema table, authoritative for IDs, ranges, units and twin geometry."""
    __tablename__ = "components"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    config: Mapped[dict] = mapped_column(JSON)


class Source(Base):
    """Immutable source chunk/case version with equipment and external-inference permissions."""
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    locator: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    external_inference_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class GenerationJob(Base):
    """Durable leased job; completion requires the same unexpired worker token."""
    __tablename__ = "generation_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tries: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    scenario_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("owner_id", "request_key"),)


class Scenario(Base):
    """Validated immutable scenario version; publication and retirement are explicit states."""
    __tablename__ = "scenario_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    difficulty: Mapped[str] = mapped_column(String(20))
    generator_version: Mapped[str] = mapped_column(String(120), nullable=False)
    source_case_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    source_manifest: Mapped[list] = mapped_column(JSON, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("scenario_templates.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("length(generator_version) > 0"),
                     CheckConstraint("status IN ('draft','published','retired')"),)


class ScenarioValidation(Base):
    """Append-only automatic and instructor validation records, pinned to content hashes."""
    __tablename__ = "scenario_validations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scenario_id: Mapped[str | None] = mapped_column(ForeignKey("scenario_templates.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("generation_jobs.id"))
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    stage: Mapped[str] = mapped_column(String(20))
    passed: Mapped[bool] = mapped_column(Boolean)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    checks: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuizItem(Base):
    """Private question keys frozen with a scenario; queryable by trainees only after publication."""
    __tablename__ = "quiz_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenario_templates.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Attempt(Base):
    """Server-owned learner state with compare-and-swap revision and submission idempotency."""
    __tablename__ = "attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenario_templates.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="active")
    submission: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    submit_key: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttemptEvent(Base):
    """Immutable accepted action and resulting revision for resume and instructor replay."""
    __tablename__ = "attempt_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("attempt_id", "key"), UniqueConstraint("attempt_id", "revision"))


class GradeReview(Base):
    """Append-only human rationale review; original automatic score remains unchanged."""
    __tablename__ = "grade_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    points: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("attempt_id"), CheckConstraint("points >= 0 AND points <= 20"))


class AuditEvent(Base):
    """Append-only safe metadata audit; raw LLM output and secrets are never included."""
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
