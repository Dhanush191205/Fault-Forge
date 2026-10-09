"""Independent physical, curriculum, citation and safety checks performed before any scenario write."""
from sqlalchemy import select
from .contracts import Candidate, PROFILES, SensorSpec
from .errors import DomainError
from .models import Component
from .rag import EvidenceBundle
from .safety import require_approved_text, screen_text


def validate_readings(db, machine_id: str, readings: list[dict]) -> None:
    """Validate every reading against the Component Schema table; reject unknown IDs, ranges and duplicates."""
    components = {x.id: x for x in db.scalars(select(Component).where(Component.machine_id == machine_id))}
    seen = set()
    for reading in readings:
        component = components.get(reading["component_id"])
        if not component:
            raise DomainError("invalid_component", "The scenario references an unknown machine component.")
        sensors = {s["id"]: SensorSpec.model_validate(s) for s in component.config["sensors"]}
        spec = sensors.get(reading["sensor_id"])
        key = (reading["component_id"], reading["sensor_id"])
        if not spec or key in seen:
            raise DomainError("invalid_sensor", "The scenario has an unknown or duplicate sensor.")
        seen.add(key)
        ranges = [spec.normal] if reading["state"] == "normal" else spec.abnormal
        if not any(low <= reading["value"] <= high for low, high in ranges):
            raise DomainError("sensor_out_of_range", "A simulated reading is outside its defined range.")


def validate_candidate(db, candidate: Candidate, bundle: EvidenceBundle, requested: dict) -> dict:
    """Validate model selection against scoped sources and DB components; return a frozen private payload."""
    bundle.require_grounding()
    if candidate.machine_id != bundle.machine_id or candidate.difficulty != requested["difficulty"]:
        raise DomainError("profile_mismatch", "The generated scenario differs from the requested profile.")
    sources = {s["id"]: s for s in bundle.sources}
    source = sources.get(candidate.case_id)
    if not source or source["kind"] != "case":
        raise DomainError("ungrounded_case", "The scenario does not reference a retrieved failure case.")
    case = source["content"]
    expected_citations = {candidate.case_id, *case["manual_ids"]}
    if set(candidate.citations) != expected_citations or not expected_citations <= sources.keys():
        raise DomainError("invalid_citations", "Case and manual citations must resolve to retrieved evidence.")
    component_ids = set(db.scalars(select(Component.id).where(Component.machine_id == candidate.machine_id)))
    if not set(candidate.component_ids) <= component_ids or set(candidate.component_ids) != set(case["component_ids"]):
        raise DomainError("invalid_component", "The scenario references incompatible machine components.")
    if len(candidate.component_ids) != len(set(candidate.component_ids)):
        raise DomainError("invalid_component", "Duplicate components are not permitted.")
    readings = [x.model_dump() for x in candidate.readings]
    validate_readings(db, candidate.machine_id, readings)
    # Exact case envelopes prevent individually plausible but jointly impossible sensor combinations.
    def canonical(rows):
        return sorted(rows, key=lambda x: (x["component_id"], x["sensor_id"]))
    if canonical(readings) != canonical(case["readings"]):
        raise DomainError("physical_inconsistency", "The readings do not match the approved case operating state.")
    require_approved_text(candidate.title, [case["title"]])
    require_approved_text(candidate.briefing, [case["briefing"]])
    if candidate.steps != case["steps"]:
        raise DomainError("procedure_mismatch", "The safety and investigation sequence must match the approved case.")
    for step in candidate.steps:
        require_approved_text(step, case["steps"])
    profile = PROFILES[candidate.difficulty]
    if candidate.hints != (case["hints"] if profile["hints"] else []):
        raise DomainError("difficulty_mismatch", "Hint visibility does not match the requested difficulty.")
    for hint in candidate.hints:
        require_approved_text(hint, case["hints"])
    questions = {q["id"]: q for q in case["quiz"]}
    if {q.question_id for q in candidate.quiz} != questions.keys() or len(candidate.quiz) != len(questions):
        raise DomainError("quiz_mismatch", "The question selection must match the approved case rubric.")
    selected_questions = []
    for selected in candidate.quiz:
        q = questions[selected.question_id]
        options = {o["id"]: o for o in q["options"]}
        if (len(selected.option_ids) != profile["distractors"] + 1
                or len(set(selected.option_ids)) != len(selected.option_ids)
                or q["correct_id"] not in selected.option_ids or not set(selected.option_ids) <= options.keys()):
            raise DomainError("difficulty_mismatch", "Quiz distractors do not match the difficulty profile.")
        selected_questions.append({**q, "options": [options[x] for x in selected.option_ids]})
    if not candidate.self_validation.safe or not candidate.self_validation.grounded:
        raise DomainError("self_validation_failed", "The model flagged its own scenario as ungrounded or unsafe.")
    payload = candidate.model_dump()
    payload.update({"diagnoses": case["diagnoses"], "correct_diagnosis_id": case["correct_diagnosis_id"],
                    "evidence": case["evidence"], "required_evidence_ids": case["required_evidence_ids"],
                    "explanation": case["explanation"], "quiz": selected_questions,
                    "rationale_rubric": case["rationale_rubric"], "synthetic": case["synthetic"],
                    "engine_version": "training-state/1.0", "rubric_version": "diagnostic-reasoning/1.0"})
    # All displayed source-authored prose is screened too. Novel model procedures cannot enter this payload.
    def inspect(value):
        if isinstance(value, str):
            screen_text(value)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
        elif isinstance(value, dict):
            for item in value.values():
                inspect(item)
    inspect(payload)
    return payload
