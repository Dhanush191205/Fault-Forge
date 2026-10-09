"""Deterministic rubric scoring with explicit human review for open-ended diagnosis reasoning."""
from datetime import timezone
from sqlalchemy import update
from .contracts import PROFILES
from .errors import DomainError
from .models import Scenario, Attempt, GradeReview, AuditEvent, utcnow
from .rag import content_hash
from .safety import screen_text
from .simulation import replay


def submit(db, attempt: Attempt, submission, user_id: str) -> Attempt:
    """Validate selections and server replay, then freeze one result with CAS/idempotency; reject forged inputs."""
    if attempt.user_id != user_id:
        raise DomainError("forbidden", "Only the assigned trainee can submit this session.", 403)
    body = submission.model_dump()
    if attempt.submission:
        if attempt.submit_key == submission.request_key and content_hash(attempt.submission) == content_hash(body):
            return attempt
        raise DomainError("already_submitted", "This attempt already has a recorded result.", 409)
    if attempt.step != 5:
        raise DomainError("investigation_required", "Complete all safety and evidence steps before submitting.", 409)
    replay(db, attempt)
    scenario = db.get(Scenario, attempt.scenario_id)
    p = scenario.payload
    if content_hash(p) != scenario.content_hash:
        raise DomainError("integrity_failure", "Scenario integrity check failed.", 409)
    diagnosis_ids = {x["id"] for x in p["diagnoses"]}
    evidence_ids = {x["id"] for x in p["evidence"]}
    questions = {x["id"]: x for x in p["quiz"]}
    if submission.diagnosis_id not in diagnosis_ids or not set(submission.evidence_ids) <= evidence_ids:
        raise DomainError("invalid_answer", "Choose diagnosis and evidence IDs from this session.")
    if len(set(submission.evidence_ids)) != len(submission.evidence_ids):
        raise DomainError("invalid_answer", "Evidence selections must be unique.")
    if submission.answers.keys() != questions.keys() or any(
        answer not in {o["id"] for o in questions[qid]["options"]} for qid, answer in submission.answers.items()):
        raise DomainError("invalid_answer", "Answer every question using the supplied options.")
    needs_review = PROFILES[scenario.difficulty]["free_text"]
    if needs_review and len(submission.rationale.strip()) < 40:
        raise DomainError("reasoning_required", "Explain your evidence and alternative diagnosis in at least 40 characters.")
    screen_text(submission.rationale)
    diagnosis_points = (40 if needs_review else 50) if submission.diagnosis_id == p["correct_diagnosis_id"] else 0
    required = set(p["required_evidence_ids"])
    chosen = set(submission.evidence_ids)
    evidence_points = round(20 * max(0, len(chosen & required) - len(chosen - required)) / len(required))
    quiz_points = round((20 if needs_review else 30) * sum(submission.answers[q["id"]] == q["correct_id"] for q in p["quiz"]) / len(p["quiz"]))
    automatic = diagnosis_points + evidence_points + quiz_points
    now = utcnow()
    start = attempt.started_at.replace(tzinfo=timezone.utc) if attempt.started_at.tzinfo is None else attempt.started_at
    result = {"automatic_score": automatic, "automatic_max": 80 if needs_review else 100,
        "score": None if needs_review else automatic, "passed": None if needs_review else automatic >= 70,
        "review_pending": needs_review, "diagnosis_points": diagnosis_points, "evidence_points": evidence_points,
        "quiz_points": quiz_points, "duration_seconds": max(0, int((now - start).total_seconds())),
        "explanation": p["explanation"], "quiz_feedback": [{"id": q["id"],
            "correct": submission.answers[q["id"]] == q["correct_id"], "explanation": q["explanation"]} for q in p["quiz"]],
        "rubric_version": p["rubric_version"], "scenario_hash": scenario.content_hash,
        "next_step": "Compare the strongest evidence with one plausible alternative before your next exercise."}
    changed = db.execute(update(Attempt).where(Attempt.id == attempt.id, Attempt.status == "active",
        Attempt.revision == submission.expected_revision).values(status="pending_review" if needs_review else "completed",
        result=result, submission=body, submit_key=submission.request_key, finished_at=now, revision=Attempt.revision + 1)).rowcount
    if not changed:
        db.rollback()
        raise DomainError("revision_conflict", "The session changed before submission. Refresh it.", 409)
    db.add(AuditEvent(actor_id=user_id, action="assessment_submitted", target_id=attempt.id,
                      details={"automatic_score": automatic, "review_pending": needs_review}))
    db.commit()
    db.refresh(attempt)
    return attempt


def review_reasoning(db, attempt: Attempt, reviewer_id: str, review) -> GradeReview:
    """Append a single rubric-based rationale grade; preserve original automatic assessment and history."""
    if attempt.user_id == reviewer_id:
        raise DomainError("self_review", "An instructor cannot score their own open-ended assessment.", 403)
    if attempt.status != "pending_review":
        raise DomainError("review_not_pending", "This assessment is not awaiting review.", 409)
    screen_text(review.feedback)
    points = review.evidence_reasoning + review.alternative_reasoning
    changed = db.execute(update(Attempt).where(Attempt.id == attempt.id, Attempt.status == "pending_review")
                         .values(status="completed", revision=Attempt.revision + 1)).rowcount
    if not changed:
        db.rollback()
        raise DomainError("review_conflict", "Another instructor already reviewed this attempt.", 409)
    row = GradeReview(attempt_id=attempt.id, reviewer_id=reviewer_id, points=points, feedback=review.feedback)
    db.add(row)
    db.add(AuditEvent(actor_id=reviewer_id, action="reasoning_reviewed", target_id=attempt.id,
                      details={"evidence_reasoning": review.evidence_reasoning, "alternative_reasoning": review.alternative_reasoning}))
    db.commit()
    return row
