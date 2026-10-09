"""Validated service and API contracts; unknown fields and control characters are rejected."""
import math
import re
import unicodedata
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator


def clean_text(value: str) -> str:
    """Normalize bounded plain text; reject hidden controls/markup before storage or prompting."""
    value = unicodedata.normalize("NFKC", value).strip()
    if any(unicodedata.category(c).startswith("C") and c not in "\n\t" for c in value):
        raise ValueError("Control characters are forbidden")
    if "<" in value or ">" in value:
        raise ValueError("Use plain text without markup")
    return value


Text = Annotated[str, Field(min_length=1, max_length=3000), AfterValidator(clean_text)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")]
Difficulty = Literal["Beginner", "Intern", "Expert"]
PROFILES = {
    "Beginner": {"hints": True, "distractors": 2, "free_text": False},
    "Intern": {"hints": True, "distractors": 3, "free_text": True},
    "Expert": {"hints": False, "distractors": 4, "free_text": True},
}


class Contract(BaseModel):
    """Base contract rejecting unknown fields and non-finite numeric values."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class LoginInput(Contract):
    """Bounded identity credentials, never included in generation prompts."""
    email: Annotated[str, Field(min_length=3, max_length=254), AfterValidator(clean_text)]
    password: str = Field(min_length=12, max_length=128)


class GenerateInput(Contract):
    """Instructor request that pins machine, source IDs and difficulty."""
    machine_id: Identifier
    difficulty: Difficulty
    source_ids: list[Identifier] = Field(min_length=2, max_length=12)
    brief: Text = Field(max_length=500)
    request_key: Identifier


class Reading(Contract):
    """A finite simulated measurement with an explicit component and sensor binding."""
    component_id: Identifier
    sensor_id: Identifier
    value: float
    state: Literal["normal", "abnormal"]


class QuizSelection(Contract):
    """Selected source question and approved option IDs; grading keys stay source-owned."""
    question_id: Identifier
    option_ids: list[Identifier] = Field(min_length=3, max_length=5)


class SelfValidation(Contract):
    """Untrusted model assertions are checked independently by application code."""
    grounded: bool
    safe: bool


class Candidate(Contract):
    """LLM JSON contract using reviewed source prose and physically bounded readings."""
    machine_id: Identifier
    difficulty: Difficulty
    case_id: Identifier
    title: Text = Field(max_length=150)
    briefing: Text
    component_ids: list[Identifier] = Field(min_length=1, max_length=30)
    readings: list[Reading] = Field(min_length=1, max_length=30)
    hints: list[Text] = Field(max_length=5)
    steps: list[Text] = Field(min_length=5, max_length=5)
    quiz: list[QuizSelection] = Field(min_length=3, max_length=5)
    citations: list[Identifier] = Field(min_length=2, max_length=12)
    self_validation: SelfValidation


class PublishInput(Contract):
    """Instructor approval must name the exact reviewed payload hash."""
    content_hash: str = Field(pattern="^[a-f0-9]{64}$")
    safety_reviewed: Literal[True]
    grounding_reviewed: Literal[True]


class ActionInput(Contract):
    """CAS and idempotency contract for ordered simulation transitions."""
    action: Literal["safety", "inspect", "measure", "history", "verify"]
    expected_revision: int = Field(ge=0, le=100)
    request_key: Identifier


class SubmitInput(Contract):
    """Learner selections; time, state, scores and evidence history are server-owned."""
    diagnosis_id: Identifier
    evidence_ids: list[Identifier] = Field(min_length=1, max_length=10)
    answers: dict[Identifier, Identifier] = Field(min_length=3, max_length=5)
    rationale: Annotated[str, Field(max_length=3000), AfterValidator(clean_text)] = ""
    expected_revision: int = Field(ge=0, le=100)
    request_key: Identifier


class ReviewInput(Contract):
    """Human scoring uses two explicit 0–10 criteria and required explanatory feedback."""
    evidence_reasoning: int = Field(ge=0, le=10)
    alternative_reasoning: int = Field(ge=0, le=10)
    feedback: Text = Field(min_length=20, max_length=1000)


class SensorSpec(Contract):
    """Non-overlapping physical training envelopes in declared units."""
    id: Identifier
    label: Text = Field(max_length=100)
    unit: Text = Field(max_length=20)
    normal: tuple[float, float]
    abnormal: list[tuple[float, float]] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def ordered_ranges(self):
        """Check finite ordered disjoint ranges; return a valid sensor or reject config."""
        ranges = [self.normal, *self.abnormal]
        if any(not all(math.isfinite(x) for x in pair) or pair[0] > pair[1] for pair in ranges):
            raise ValueError("Ranges must be finite and ordered")
        for index, left in enumerate(ranges):
            for right in ranges[index + 1:]:
                if max(left[0], right[0]) <= min(left[1], right[1]):
                    raise ValueError("Normal and abnormal ranges must not overlap")
        return self


class Geometry(Contract):
    """Data-driven primitive geometry avoids remote 3D asset dependencies."""
    shape: Literal["box", "cylinder"]
    position: tuple[float, float, float]
    scale: tuple[float, float, float]
    color: str = Field(pattern="^#[a-fA-F0-9]{6}$")


class ComponentSpec(Contract):
    """Portable component definition consumed by validation and twin rendering."""
    id: Identifier
    name: Text = Field(max_length=100)
    sensors: list[SensorSpec] = Field(max_length=10)
    geometry: Geometry


class MachineSpec(Contract):
    """Machine configuration import contract; new equipment needs only config and sources."""
    id: Identifier
    name: Text = Field(max_length=100)
    description: Text
    synthetic: bool
    components: list[ComponentSpec] = Field(min_length=1, max_length=30)


def validate_email(value: str) -> str:
    """Return normalized basic email syntax or raise ValueError; no deliverability claim is made."""
    value = value.lower().strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Invalid email")
    return value
