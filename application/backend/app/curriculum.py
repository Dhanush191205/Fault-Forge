"""Schema for versioned, instructor-authored curriculum packs and source ingestion."""
from typing import Literal
from pydantic import Field, model_validator
from .contracts import Contract, Text, Identifier, MachineSpec, Reading
from .errors import DomainError
from .models import Machine, Component, Source, AuditEvent
from .rag import content_hash
from .safety import screen_text


class Option(Contract):
    """An approved diagnosis or quiz option with a stable non-semantic identifier."""
    id: Identifier
    text: Text


class Question(Contract):
    """Private source question with five options and an instructor-owned scoring key."""
    id: Identifier
    text: Text
    options: list[Option] = Field(min_length=5, max_length=5)
    correct_id: Identifier
    explanation: Text


class Evidence(Contract):
    """A bounded recorded observation revealed only at its configured investigation stage."""
    id: Identifier
    label: Text
    text: Text
    reveal_step: int = Field(ge=2, le=5)


class CaseContent(Contract):
    """Complete diagnostic case; no free-form generated scoring keys are accepted."""
    title: Text
    briefing: Text
    manual_ids: list[Identifier] = Field(min_length=1, max_length=6)
    component_ids: list[Identifier] = Field(min_length=1, max_length=30)
    readings: list[Reading] = Field(min_length=1, max_length=30)
    hints: list[Text] = Field(min_length=1, max_length=5)
    steps: list[Text] = Field(min_length=5, max_length=5)
    quiz: list[Question] = Field(min_length=3, max_length=3)
    diagnoses: list[Option] = Field(min_length=5, max_length=5)
    correct_diagnosis_id: Identifier
    evidence: list[Evidence] = Field(min_length=3, max_length=10)
    required_evidence_ids: list[Identifier] = Field(min_length=2, max_length=5)
    explanation: Text
    rationale_rubric: list[Text] = Field(min_length=2, max_length=2)
    synthetic: bool

    @model_validator(mode="after")
    def linked_keys(self):
        """Check key uniqueness and referential integrity; reject incomplete grading definitions."""
        for values in [self.quiz, self.diagnoses, self.evidence, *[q.options for q in self.quiz]]:
            if len({v.id for v in values}) != len(values):
                raise ValueError("Duplicate curriculum identifiers")
        if self.correct_diagnosis_id not in {d.id for d in self.diagnoses}:
            raise ValueError("Unknown diagnosis key")
        if not set(self.required_evidence_ids) <= {e.id for e in self.evidence}:
            raise ValueError("Unknown evidence key")
        if any(q.correct_id not in {o.id for o in q.options} for q in self.quiz):
            raise ValueError("Unknown quiz key")
        if not any("lockout/tagout" in step.lower() for step in self.steps[:1]):
            raise ValueError("The first step must include lockout/tagout review")
        return self


class ManualContent(Contract):
    """Small authorized manual chunk with explicit page/section provenance."""
    text: Text


class SourceInput(Contract):
    """One immutable source version; approval is a separate authenticated operation."""
    id: Identifier
    kind: Literal["case", "manual"]
    title: Text
    locator: Text
    content: dict
    synthetic: bool
    external_inference_allowed: bool = False


class CurriculumPack(Contract):
    """Portable machine/case/manual data; enables machine additions without engine edits."""
    machine: MachineSpec
    sources: list[SourceInput] = Field(min_length=2, max_length=30)


def import_pack(db, pack: CurriculumPack, actor_id: str, demo_mode: bool) -> list[str]:
    """Import a new immutable machine revision and unapproved sources; reject overwrite and invalid data."""
    if db.get(Machine, pack.machine.id):
        raise DomainError("version_exists", "Use a new machine revision ID; existing configuration is immutable.", 409)
    if pack.machine.synthetic and not demo_mode:
        raise DomainError("synthetic_source", "Synthetic curriculum requires demo mode.")
    if len({c.id for c in pack.machine.components}) != len(pack.machine.components):
        raise DomainError("invalid_component", "Duplicate component IDs are not allowed.")
    for source in pack.sources:
        if db.get(Source, source.id) or source.synthetic != pack.machine.synthetic:
            raise DomainError("invalid_source", "Use unique source versions with matching synthetic labels.")
        model = CaseContent if source.kind == "case" else ManualContent
        try:
            source.content = model.model_validate(source.content).model_dump()
        except ValueError as exc:
            raise DomainError("invalid_curriculum", "A source has an incomplete case or manual contract.") from exc
        if source.kind == "case" and source.content["synthetic"] != source.synthetic:
            raise DomainError("invalid_source", "Case and source synthetic labels must agree.")
        screen_text(str(source.content))
    source_ids = {s.id for s in pack.sources}
    manuals = {s.id for s in pack.sources if s.kind == "manual"}
    if len(source_ids) != len(pack.sources):
        raise DomainError("invalid_source", "Source IDs must be unique.")
    if any(not set(s.content["manual_ids"]) <= manuals for s in pack.sources if s.kind == "case"):
        raise DomainError("invalid_source", "Every case must reference manuals included in this pack.")
    db.add(Machine(id=pack.machine.id, name=pack.machine.name, config=pack.machine.model_dump(exclude={"components"})))
    db.flush()
    for component in pack.machine.components:
        if db.get(Component, component.id):
            raise DomainError("invalid_component", "Component IDs must be globally unique and versioned.")
        db.add(Component(id=component.id, machine_id=pack.machine.id, config=component.model_dump()))
    db.flush()
    from .validation import validate_readings
    valid_components = {c.id for c in pack.machine.components}
    for source in pack.sources:
        if source.kind == "case":
            if not set(source.content["component_ids"]) <= valid_components:
                raise DomainError("invalid_component", "The case references a component outside this machine.")
            validate_readings(db, pack.machine.id, source.content["readings"])
        db.add(Source(id=source.id, machine_id=pack.machine.id, kind=source.kind, title=source.title,
            locator=source.locator, content=source.content, checksum=content_hash(source.content),
            approved=False, external_inference_allowed=source.external_inference_allowed, synthetic=source.synthetic))
    db.add(AuditEvent(actor_id=actor_id, action="curriculum_imported", target_id=pack.machine.id,
                      details={"source_ids": sorted(source_ids)}))
    db.flush()
    return sorted(source_ids)
