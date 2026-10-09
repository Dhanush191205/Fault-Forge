"""Authoritative, machine-agnostic educational state transitions and public twin projections."""
import hashlib
from sqlalchemy import select, update
from .contracts import PROFILES
from .errors import DomainError
from .models import Scenario, Attempt, AttemptEvent, Component, GradeReview
from .rag import content_hash
from .validation import validate_readings

ACTION_IDS = ("safety", "inspect", "measure", "history", "verify")


def owned_attempt(db, attempt_id: str, user) -> Attempt:
    """Return an owned attempt (or instructor read access); otherwise return the same safe 404."""
    row = db.get(Attempt, attempt_id)
    if not row or (user.role != "instructor" and row.user_id != user.id):
        raise DomainError("not_found", "Training session not found.", 404)
    return row


def start_attempt(db, scenario_id: str, user_id: str) -> Attempt:
    """Start/resume an active session for a published scenario; reject hidden or retired content."""
    scenario = db.get(Scenario, scenario_id)
    if not scenario or scenario.status != "published":
        raise DomainError("not_found", "Published scenario not found.", 404)
    row = db.scalar(select(Attempt).where(Attempt.user_id == user_id, Attempt.scenario_id == scenario_id,
                                          Attempt.status == "active").order_by(Attempt.started_at.desc()))
    if row:
        return row
    row = Attempt(user_id=user_id, scenario_id=scenario_id)
    db.add(row)
    db.commit()
    return row


def advance(db, attempt: Attempt, action, user_id: str) -> Attempt:
    """Commit one ordered action under a revision CAS; identical retries do not advance twice."""
    if attempt.user_id != user_id:
        raise DomainError("forbidden", "Only the assigned trainee can advance this session.", 403)
    event = db.scalar(select(AttemptEvent).where(AttemptEvent.attempt_id == attempt.id, AttemptEvent.key == action.request_key))
    if event:
        if event.action != action.action or event.revision != action.expected_revision + 1:
            raise DomainError("idempotency_conflict", "This action key has different inputs.", 409)
        db.refresh(attempt)
        return attempt
    if attempt.status != "active" or attempt.step >= len(ACTION_IDS):
        raise DomainError("session_complete", "This session has no remaining investigation actions.", 409)
    if ACTION_IDS[attempt.step] != action.action:
        raise DomainError("safety_sequence", "Complete the investigation steps in order, beginning with safety.", 409)
    changed = db.execute(update(Attempt).where(Attempt.id == attempt.id, Attempt.revision == action.expected_revision,
        Attempt.status == "active", Attempt.step == attempt.step).values(step=Attempt.step + 1, revision=Attempt.revision + 1)).rowcount
    if not changed:
        db.rollback()
        raise DomainError("revision_conflict", "The session changed. Refresh before continuing.", 409)
    db.add(AttemptEvent(attempt_id=attempt.id, key=action.request_key, action=action.action, revision=action.expected_revision + 1))
    db.commit()
    db.refresh(attempt)
    return attempt


def ordered_options(options: list[dict], attempt_id: str, salt: str) -> list[dict]:
    """Deterministically shuffle public choices per session without revealing private answer keys."""
    return sorted(options, key=lambda x: hashlib.sha256(f"{attempt_id}:{salt}:{x['id']}".encode()).digest())


def public_snapshot(db, attempt: Attempt) -> dict:
    """Return allowlisted trainee state with staged evidence; never expose private diagnosis or quiz keys."""
    scenario = db.get(Scenario, attempt.scenario_id)
    payload = scenario.payload
    if content_hash(payload) != scenario.content_hash:
        raise DomainError("integrity_failure", "Scenario integrity check failed.", 409)
    readings = payload["readings"] if attempt.step >= 3 else []
    validate_readings(db, scenario.machine_id, readings)
    components = list(db.scalars(select(Component).where(Component.machine_id == scenario.machine_id)))
    public_components = [{"id": c.id, "name": c.config["name"], "geometry": c.config["geometry"],
        "sensors": [{"id": s["id"], "label": s["label"], "unit": s["unit"], "normal": s["normal"]} for s in c.config["sensors"]]}
        for c in components]
    public_readings = [{"component_id": x["component_id"], "sensor_id": x["sensor_id"], "value": x["value"]} for x in readings]
    review = db.scalar(select(GradeReview).where(GradeReview.attempt_id == attempt.id))
    result = dict(attempt.result) if attempt.result else None
    if result and review:
        result.update({"review_points": review.points, "score": result["automatic_score"] + review.points,
                       "review_feedback": review.feedback, "review_pending": False,
                       "passed": result["automatic_score"] + review.points >= 70})
    diagnosis_ids = payload["diagnoses"]
    # Diagnosis options are source-owned and hidden until evidence collection is complete.
    diagnosis_choices = ordered_options(diagnosis_ids, attempt.id, "diagnosis") if attempt.step == 5 else []
    return {"id": attempt.id, "scenario_id": scenario.id, "machine_id": scenario.machine_id,
        "title": payload["title"], "briefing": payload["briefing"], "difficulty": scenario.difficulty,
        "synthetic": payload["synthetic"], "status": attempt.status, "revision": attempt.revision, "step": attempt.step,
        "steps": [{"id": action, "text": text} for action, text in zip(ACTION_IDS, payload["steps"], strict=True)],
        "hints": payload["hints"] if PROFILES[scenario.difficulty]["hints"] else [],
        "free_text_required": PROFILES[scenario.difficulty]["free_text"], "components": public_components,
        "readings": public_readings, "evidence": [{k: e[k] for k in ("id", "label", "text")} for e in payload["evidence"]
                                                       if e["reveal_step"] <= attempt.step],
        "diagnoses": diagnosis_choices,
        "quiz": [{"id": q["id"], "text": q["text"], "options": ordered_options(q["options"], attempt.id, q["id"])}
                 for q in payload["quiz"]] if attempt.step == 5 else [],
        "result": result, "started_at": attempt.started_at.isoformat(),
        "engine_version": payload["engine_version"], "rationale_rubric": payload["rationale_rubric"]}


def replay(db, attempt: Attempt) -> dict:
    """Verify ordered persisted actions against the current step; return safe replay evidence or fail closed."""
    events = list(db.scalars(select(AttemptEvent).where(AttemptEvent.attempt_id == attempt.id).order_by(AttemptEvent.revision)))
    if len(events) != attempt.step or any(e.revision != i + 1 or e.action != ACTION_IDS[i] for i, e in enumerate(events)):
        raise DomainError("replay_mismatch", "The recorded investigation history failed verification.", 409)
    return {"verified": True, "engine_version": "training-state/1.0", "events": [
        {"action": e.action, "revision": e.revision, "created_at": e.created_at.isoformat()} for e in events]}
