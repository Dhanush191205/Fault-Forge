"""HTTP-level curriculum publication, training, grading and security contracts."""
import secrets
import pytest
from sqlalchemy import select, update, delete
from sqlalchemy.exc import DBAPIError
from app.models import Scenario, User, Attempt, GradeReview
from app.security import password_hash


def publish_one(teacher, difficulty="Beginner"):
    """Review one exact draft hash and return its private reference for test assertions."""
    drafts = teacher.get("/api/instructor/scenarios").json()
    draft = next(x for x in drafts if x["difficulty"] == difficulty)
    result = teacher.post(f"/api/instructor/scenarios/{draft['id']}/publish", json={
        "content_hash": draft["content_hash"], "safety_reviewed": True, "grounding_reviewed": True})
    assert result.status_code == 200, result.text
    return draft


def investigate(trainee, draft):
    """Complete all five ordered actions against real API state and return the public snapshot."""
    response = trainee.post(f"/api/scenarios/{draft['id']}/start", json={})
    assert response.status_code == 200, response.text
    snapshot = response.json()
    for action in ["safety", "inspect", "measure", "history", "verify"]:
        result = trainee.post(f"/api/attempts/{snapshot['id']}/actions", json={
            "action": action, "expected_revision": snapshot["revision"], "request_key": secrets.token_hex(10)})
        assert result.status_code == 200, result.text
        snapshot = result.json()
    return snapshot


def answers(db, snapshot, rationale=""):
    """Build source-key-correct answers without trusting any client-provided scoring values."""
    payload = db.get(Scenario, snapshot["scenario_id"]).payload
    return {"diagnosis_id": payload["correct_diagnosis_id"], "evidence_ids": payload["required_evidence_ids"],
        "answers": {q["id"]: q["correct_id"] for q in payload["quiz"]}, "rationale": rationale,
        "expected_revision": snapshot["revision"], "request_key": secrets.token_hex(10)}


def test_full_beginner_flow_and_pdf(clients):
    teacher, trainee, factory, _, _ = clients
    assert trainee.get("/api/scenarios").json() == []
    draft = publish_one(teacher)
    snapshot = investigate(trainee, draft)
    with factory() as db:
        body = answers(db, snapshot)
    response = trainee.post(f"/api/attempts/{snapshot['id']}/submit", json=body)
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["score"] == 100 and result["passed"] and not result["review_pending"]
    repeat = trainee.post(f"/api/attempts/{snapshot['id']}/submit", json=body)
    assert repeat.status_code == 200
    assert repeat.json()["result"] == result
    pdf = trainee.get(f"/api/attempts/{snapshot['id']}/report.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert trainee.get("/api/dashboard").json()["average"] == 100


@pytest.mark.parametrize("difficulty", ["Intern", "Expert"])
def test_open_reasoning_is_provisional_until_human_review(clients, difficulty):
    teacher, trainee, factory, _, _ = clients
    draft = publish_one(teacher, difficulty)
    snapshot = investigate(trainee, draft)
    with factory() as db:
        body = answers(db, snapshot)
    assert trainee.post(f"/api/attempts/{snapshot['id']}/submit", json=body).status_code == 422
    body["rationale"] = "I correlate the controlled comparison with the initial observation and compare the alternative against the recorded history."
    response = trainee.post(f"/api/attempts/{snapshot['id']}/submit", json=body)
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["score"] is None and result["automatic_score"] == 80 and result["review_pending"]
    review = teacher.post(f"/api/instructor/attempts/{snapshot['id']}/review", json={
        "evidence_reasoning": 8, "alternative_reasoning": 7, "feedback": "The evidence is connected clearly; name the alternative and its distinguishing observation more precisely."})
    assert review.status_code == 200, review.text
    final = trainee.get(f"/api/attempts/{snapshot['id']}").json()
    assert final["result"]["score"] == 95 and final["status"] == "completed"
    with factory() as db:
        assert db.get(Attempt, snapshot["id"]).result["score"] is None
        assert db.scalar(select(GradeReview).where(GradeReview.attempt_id == snapshot["id"])).points == 15


def test_safety_sequence_and_duplicate_action(clients):
    teacher, trainee, _, _, _ = clients
    draft = publish_one(teacher)
    snapshot = trainee.post(f"/api/scenarios/{draft['id']}/start", json={}).json()
    assert not snapshot["readings"] and not snapshot["quiz"] and not snapshot["diagnoses"]
    body = {"action": "measure", "expected_revision": 0, "request_key": "action-1"}
    assert trainee.post(f"/api/attempts/{snapshot['id']}/actions", json=body).status_code == 409
    body["action"] = "safety"
    for _ in range(2):
        response = trainee.post(f"/api/attempts/{snapshot['id']}/actions", json=body)
        assert response.status_code == 200 and response.json()["step"] == 1
    body.update(action="inspect", request_key="action-2")
    assert trainee.post(f"/api/attempts/{snapshot['id']}/actions", json=body).status_code == 409


def test_private_answer_keys_never_appear_in_trainee_projection(clients):
    teacher, trainee, _, _, _ = clients
    draft = publish_one(teacher, "Expert")
    snapshot = investigate(trainee, draft)
    for key in ["correct_diagnosis_id", "correct_id", "source_case_ids", "required_evidence_ids", "self_validation"]:
        assert key not in str(snapshot)
    assert snapshot["hints"] == []
    for route in ["/api/instructor/scenarios", "/api/instructor/sources", "/api/instructor/attempts", "/api/instructor/audit"]:
        assert trainee.get(route).status_code == 403


def test_error_envelopes_and_validation_redaction(clients):
    teacher, trainee, _, _, _ = clients
    response = teacher.post("/api/scenarios/generate", json={"private": "DO_NOT_EXPOSE_THIS"})
    assert response.status_code == 422 and "DO_NOT_EXPOSE_THIS" not in response.text
    assert set(response.json()["error"]) == {"code", "message", "request_id"}
    malformed = teacher.post("/api/scenarios/generate", content='{private invalid json', headers={"content-type": "application/json"})
    assert malformed.status_code == 422 and "private invalid" not in malformed.text
    assert "error" in trainee.get("/api/missing").json()


def test_csrf_login_origin_and_revocation(clients):
    teacher, trainee, _, _, _ = clients
    denied = teacher.post("/api/auth/logout", json={}, headers={"x-csrf-token": "wrong"})
    assert denied.status_code == 403
    denied = trainee.post("/api/auth/logout", json={}, headers={"origin": "https://untrusted.example"})
    assert denied.status_code == 403
    assert trainee.post("/api/auth/logout", json={}).status_code == 200
    assert trainee.get("/api/auth/me").status_code == 401


def test_another_learner_cannot_read_session(clients):
    teacher, trainee, factory, _, users = clients
    draft = publish_one(teacher)
    snapshot = trainee.post(f"/api/scenarios/{draft['id']}/start", json={}).json()
    with factory() as db:
        stranger = User(email="other@example.test", name="Other learner", role="trainee", password_hash=password_hash(secrets.token_urlsafe(20)))
        db.add(stranger)
        db.flush()
        db.execute(update(Attempt).where(Attempt.id == snapshot["id"]).values(user_id=stranger.id))
        db.commit()
    assert trainee.get(f"/api/attempts/{snapshot['id']}").status_code == 404
    assert trainee.get(f"/api/attempts/{snapshot['id']}/report.pdf").status_code == 404


def test_stale_approval_and_soft_retirement(clients):
    teacher, trainee, _, _, _ = clients
    draft = teacher.get("/api/instructor/scenarios").json()[0]
    response = teacher.post(f"/api/instructor/scenarios/{draft['id']}/publish", json={
        "content_hash": "0" * 64, "safety_reviewed": True, "grounding_reviewed": True})
    assert response.status_code == 409
    draft = publish_one(teacher)
    snapshot = trainee.post(f"/api/scenarios/{draft['id']}/start", json={}).json()
    assert teacher.post(f"/api/instructor/scenarios/{draft['id']}/retire", json={}).status_code == 200
    assert trainee.post(f"/api/scenarios/{draft['id']}/start", json={}).status_code == 404
    assert trainee.get(f"/api/attempts/{snapshot['id']}").status_code == 200


def test_database_prevents_destructive_scenario_changes(system):
    factory, _, _ = system
    with factory() as db:
        row = db.scalar(select(Scenario))
        with pytest.raises(DBAPIError):
            db.execute(delete(Scenario).where(Scenario.id == row.id))
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(update(Scenario).where(Scenario.id == row.id).values(payload={}))
        db.rollback()


def test_reject_raw_sql_like_ids_and_forged_scores(clients):
    teacher, trainee, factory, _, _ = clients
    draft = publish_one(teacher)
    snapshot = investigate(trainee, draft)
    with factory() as db:
        body = answers(db, snapshot)
    body["score"] = 100
    assert trainee.post(f"/api/attempts/{snapshot['id']}/submit", json=body).status_code == 422
    body.pop("score")
    body["diagnosis_id"] = "'; DROP TABLE users; --"
    assert trainee.post(f"/api/attempts/{snapshot['id']}/submit", json=body).status_code == 422
