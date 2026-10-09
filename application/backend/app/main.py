"""FastAPI transport layer. Domain services own generation, retrieval, simulation and grading."""
import logging
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .config import get_settings
from .contracts import LoginInput, GenerateInput, PublishInput, ActionInput, SubmitInput, ReviewInput, validate_email
from .curriculum import CurriculumPack, import_pack
from .db import get_db
from .errors import DomainError
from .models import (User, Scenario, ScenarioValidation, Source, Machine, Component, GenerationJob, Attempt, AuditEvent,
                     GradeReview)
from .security import current_user, instructor, verify_password, create_session, limit, password_hash
from .scenarios import enqueue, publish, retire
from .simulation import start_attempt, owned_attempt, public_snapshot, advance, replay
from .assessment import submit, review_reasoning
from .reports import assessment_pdf

log = logging.getLogger("faultforge.api")
_DUMMY_HASH = password_hash(secrets.token_urlsafe(32))


@asynccontextmanager
async def lifespan(_app):
    """Validate environment at startup; schema migrations and data ingestion remain explicit operations."""
    get_settings()
    yield


app = FastAPI(title="Fault Forge", version="0.1.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().allowed_origins,
    allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"], expose_headers=["X-Request-ID"])


def error_response(request: Request, code: str, message: str, status: int) -> JSONResponse:
    """Return the single public error shape; private exception strings are never accepted here."""
    return JSONResponse({"error": {"code": code, "message": message,
                                  "request_id": getattr(request.state, "request_id", "unknown")}}, status_code=status)


@app.middleware("http")
async def request_boundary(request: Request, call_next):
    """Assign server request IDs, bound JSON bodies and redact unexpected failures; return secure response headers."""
    request.state.request_id = secrets.token_hex(12)
    if request.method == "POST":
        raw_length = request.headers.get("content-length", "")
        if not raw_length.isdigit():
            return error_response(request, "length_required", "A bounded Content-Length is required.", 411)
        if int(raw_length) > 1_000_000:
            return error_response(request, "request_too_large", "Request exceeds the size limit.", 413)
    try:
        response = await call_next(request)
    except Exception:
        log.error("unhandled_request request_id=%s", request.state.request_id)
        response = error_response(request, "internal_error", "The request could not be completed.", 500)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    """Convert a safe domain failure to the uniform API envelope; never return provider output."""
    return error_response(request, exc.code, exc.message, exc.status)


@app.exception_handler(RequestValidationError)
async def input_error(request: Request, _exc: RequestValidationError):
    """Redact validation details which may contain passwords/answers; return a handled 422."""
    return error_response(request, "invalid_input", "Check the required fields, lengths and allowed values.", 422)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    """Normalize framework errors without returning raw route exception details."""
    return error_response(request, "http_error", "The requested operation is unavailable.", exc.status_code)


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, _exc: IntegrityError):
    """Report a safe concurrent-write conflict without leaking SQL or schema details."""
    return error_response(request, "write_conflict", "A conflicting update was recorded. Refresh and retry.", 409)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, _exc: SQLAlchemyError):
    """Report infrastructure unavailability with no credentials or raw query contents."""
    return error_response(request, "database_unavailable", "The data service is temporarily unavailable.", 503)


@app.get("/api/health")
def health():
    """Return process liveness and explicit fixture mode; no inputs or dependency checks."""
    return {"status": "ok", "demo_mode": get_settings().demo_mode, "version": "0.1.0"}


@app.get("/api/ready")
def ready(db=Depends(get_db)):
    """Check database/schema readiness; fail safely when migrations or the data service are unavailable."""
    db.execute(text("SELECT 1"))
    db.scalar(select(func.count()).select_from(Machine))
    return {"status": "ready"}


@app.post("/api/auth/login")
def login(data: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    """Validate credentials/origin, rate-limit failures and set an opaque cookie; return profile and CSRF token."""
    if request.headers.get("origin") not in get_settings().allowed_origins:
        raise DomainError("origin_denied", "This origin is not permitted.", 403)
    limit(db, "login", request.client.host if request.client else "unknown", 20)
    try:
        email = validate_email(data.email)
    except ValueError:
        raise DomainError("invalid_credentials", "Email or password is incorrect.", 401) from None
    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not valid:
        raise DomainError("invalid_credentials", "Email or password is incorrect.", 401)
    token, csrf = create_session(db, user)
    response.set_cookie("ff_session", token, httponly=True, secure=get_settings().secure_cookies,
                        samesite="lax", max_age=get_settings().session_hours * 3600, path="/")
    return {"id": user.id, "name": user.name, "role": user.role, "csrf": csrf, "demo_mode": get_settings().demo_mode}


@app.get("/api/auth/me")
def me(request: Request, user=Depends(current_user)):
    """Return the authenticated profile and CSRF token; reject missing/expired sessions."""
    return {"id": user.id, "name": user.name, "role": user.role, "csrf": request.state.auth_session.csrf,
            "demo_mode": get_settings().demo_mode}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, _user=Depends(current_user), db=Depends(get_db)):
    """Revoke the current session without deleting history; require CSRF and return success."""
    request.state.auth_session.revoked = True
    db.commit()
    response.delete_cookie("ff_session", path="/")
    return {"ok": True}


@app.get("/api/machines")
def machines(_user=Depends(current_user), db=Depends(get_db)):
    """List configured machine metadata only; authentication is required."""
    rows = list(db.scalars(select(Machine).order_by(Machine.name).limit(100)))
    components = list(db.scalars(select(Component).where(Component.machine_id.in_([m.id for m in rows]))))
    return [{"id": m.id, "name": m.name, **m.config, "components": [
        {"id": c.id, "name": c.config["name"], "geometry": c.config["geometry"]}
        for c in components if c.machine_id == m.id]} for m in rows]


@app.get("/api/scenarios")
def catalog(machine_id: str | None = None, difficulty: str | None = None, offset: int = 0,
            _user=Depends(current_user), db=Depends(get_db)):
    """Return at most 60 published public briefs filtered via parameterized queries; never include answer keys."""
    query = select(Scenario).where(Scenario.status == "published")
    if machine_id:
        query = query.where(Scenario.machine_id == machine_id[:100])
    if difficulty:
        query = query.where(Scenario.difficulty == difficulty[:20])
    return [{"id": s.id, "title": s.payload["title"], "briefing": s.payload["briefing"],
             "machine_id": s.machine_id, "difficulty": s.difficulty, "synthetic": s.payload["synthetic"],
             "version": s.version} for s in db.scalars(query.order_by(Scenario.created_at.desc()).offset(max(0, min(offset, 10000))).limit(60))]


@app.get("/api/instructor/sources")
def sources(_user=Depends(instructor), db=Depends(get_db)):
    """Return bounded private source inventory for instructors; includes keys and therefore denies trainee access."""
    return [{"id": s.id, "machine_id": s.machine_id, "kind": s.kind, "title": s.title, "locator": s.locator,
             "approved": s.approved, "synthetic": s.synthetic, "checksum": s.checksum,
             "external_inference_allowed": s.external_inference_allowed, "content": s.content}
            for s in db.scalars(select(Source).order_by(Source.id).limit(300))]


@app.post("/api/instructor/curriculum")
def ingest(data: CurriculumPack, user=Depends(instructor), db=Depends(get_db)):
    """Import validated immutable config/manual/case JSON as unapproved sources; reject overwrites and unsafe content."""
    ids = import_pack(db, data, user.id, get_settings().demo_mode)
    db.commit()
    return {"source_ids": ids, "status": "requires_review"}


@app.post("/api/instructor/sources/{source_id}/approve")
def approve_source(source_id: str, data: PublishInput, user=Depends(instructor), db=Depends(get_db)):
    """Approve an exact source checksum after instructor review; reject stale review and record provenance."""
    source = db.get(Source, source_id)
    if not source:
        raise DomainError("not_found", "Source not found.", 404)
    if source.checksum != data.content_hash:
        raise DomainError("review_conflict", "Review the current source version.", 409)
    source.approved = True
    db.add(AuditEvent(actor_id=user.id, action="source_approved", target_id=source.id, details={"checksum": source.checksum}))
    db.commit()
    return {"approved": True}


@app.post("/api/scenarios/generate", status_code=202)
def generate(data: GenerateInput, user=Depends(instructor), db=Depends(get_db)):
    """Queue grounded generation and return a durable job reference; empty/unapproved evidence fails admission."""
    limit(db, "generation", user.id, 10)
    job = enqueue(db, user.id, data, get_settings())
    return {"id": job.id, "status": job.status, "status_url": f"/api/jobs/{job.id}"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, user=Depends(instructor), db=Depends(get_db)):
    """Return the caller's generation status and safe error code; other owners receive 404."""
    job = db.get(GenerationJob, job_id)
    if not job or job.owner_id != user.id:
        raise DomainError("not_found", "Generation job not found.", 404)
    return {"id": job.id, "status": job.status, "error_code": job.error_code, "scenario_id": job.scenario_id}


@app.get("/api/instructor/scenarios")
def drafts(_user=Depends(instructor), db=Depends(get_db)):
    """List the latest 100 private scenario versions and validation evidence for instructor review."""
    rows = list(db.scalars(select(Scenario).order_by(Scenario.created_at.desc()).limit(100)))
    validations = list(db.scalars(select(ScenarioValidation).where(ScenarioValidation.scenario_id.in_([s.id for s in rows]))))
    return [{"id": s.id, "machine_id": s.machine_id, "difficulty": s.difficulty, "status": s.status,
        "payload": s.payload, "content_hash": s.content_hash, "generator_version": s.generator_version,
        "source_case_ids": s.source_case_ids, "sources": s.source_manifest,
        "validations": [{"stage": v.stage, "passed": v.passed, "checks": v.checks} for v in validations if v.scenario_id == s.id]}
        for s in rows]


@app.post("/api/instructor/scenarios/{scenario_id}/publish")
def publish_scenario(scenario_id: str, data: PublishInput, user=Depends(instructor), db=Depends(get_db)):
    """Publish an explicitly reviewed hash after validation; never auto-publish generation results."""
    row = publish(db, scenario_id, user.id, data.content_hash)
    return {"id": row.id, "status": row.status}


@app.post("/api/instructor/scenarios/{scenario_id}/retire")
def retire_scenario(scenario_id: str, user=Depends(instructor), db=Depends(get_db)):
    """Soft-retire a published/draft scenario while preserving all learner and validation history."""
    retire(db, scenario_id, user.id)
    return {"status": "retired"}


@app.post("/api/scenarios/{scenario_id}/start")
def start(scenario_id: str, user=Depends(current_user), db=Depends(get_db)):
    """Start or resume an authenticated learner session; return the public snapshot or a handled error."""
    limit(db, "start", user.id, 30)
    return public_snapshot(db, start_attempt(db, scenario_id, user.id))


@app.get("/api/attempts/{attempt_id}")
def session(attempt_id: str, user=Depends(current_user), db=Depends(get_db)):
    """Return authorized resumable twin state; no private rubric keys appear before submission."""
    return public_snapshot(db, owned_attempt(db, attempt_id, user))


@app.post("/api/attempts/{attempt_id}/actions")
def action(attempt_id: str, data: ActionInput, user=Depends(current_user), db=Depends(get_db)):
    """Accept an ordered safety/investigation action using revision and idempotency controls."""
    return public_snapshot(db, advance(db, owned_attempt(db, attempt_id, user), data, user.id))


@app.post("/api/attempts/{attempt_id}/submit")
def assessment(attempt_id: str, data: SubmitInput, user=Depends(current_user), db=Depends(get_db)):
    """Score recorded evidence and quiz answers; require human review of Intern/Expert free text."""
    return public_snapshot(db, submit(db, owned_attempt(db, attempt_id, user), data, user.id))


@app.get("/api/attempts/{attempt_id}/report.pdf")
def report(attempt_id: str, user=Depends(current_user), db=Depends(get_db)):
    """Download an authorized assessment PDF from server results; reject unsubmitted sessions."""
    attempt = owned_attempt(db, attempt_id, user)
    learner = db.get(User, attempt.user_id)
    body = assessment_pdf(public_snapshot(db, attempt), learner.name)
    return Response(body, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="fault-forge-report.pdf"'})


@app.get("/api/instructor/attempts")
def instructor_attempts(_user=Depends(instructor), db=Depends(get_db)):
    """Return a bounded instructor review queue with replay and private source rubric, within this installation."""
    attempts = list(db.scalars(select(Attempt).where(Attempt.status == "pending_review").order_by(Attempt.finished_at).limit(100)))
    return [{"id": a.id, "learner": db.get(User, a.user_id).name, "submission": a.submission,
        "snapshot": public_snapshot(db, a), "replay": replay(db, a),
        "reference": {k: db.get(Scenario, a.scenario_id).payload[k] for k in
                      ("correct_diagnosis_id", "required_evidence_ids", "explanation", "rationale_rubric")}} for a in attempts]


@app.post("/api/instructor/attempts/{attempt_id}/review")
def review_attempt(attempt_id: str, data: ReviewInput, user=Depends(instructor), db=Depends(get_db)):
    """Append the instructor's two-criterion reasoning score; reject self-review and duplicate grading."""
    row = review_reasoning(db, owned_attempt(db, attempt_id, user), user.id, data)
    return {"points": row.points, "status": "completed"}


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user), db=Depends(get_db)):
    """Return the caller's recorded recent sessions and derived totals; provisional scores are clearly separated."""
    attempts = list(db.scalars(select(Attempt).where(Attempt.user_id == user.id).order_by(Attempt.started_at.desc()).limit(50)))
    reviews = {r.attempt_id: r for r in db.scalars(select(GradeReview).where(GradeReview.attempt_id.in_([a.id for a in attempts])))}
    rows = []
    for a in attempts:
        scenario = db.get(Scenario, a.scenario_id)
        score = a.result["score"] if a.result else None
        if a.id in reviews:
            score = a.result["automatic_score"] + reviews[a.id].points
        rows.append({"id": a.id, "title": scenario.payload["title"], "machine_id": scenario.machine_id,
                     "difficulty": scenario.difficulty, "status": a.status, "score": score, "step": a.step,
                     "started_at": a.started_at.isoformat()})
    scores = [r["score"] for r in rows if r["score"] is not None]
    return {"sessions": rows, "completed": sum(r["status"] == "completed" for r in rows),
            "average": round(sum(scores) / len(scores)) if scores else None,
            "review_pending": sum(r["status"] == "pending_review" for r in rows),
            "scope": "Your most recent 50 sessions"}


@app.get("/api/instructor/audit")
def audit(_user=Depends(instructor), db=Depends(get_db)):
    """List recent safe audit metadata; excludes raw prompts, model output and credentials."""
    return [{"action": e.action, "target_id": e.target_id, "details": e.details, "created_at": e.created_at.isoformat()}
            for e in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100))]
