"""Fail-closed safety screening plus exact allowlists for all generated procedural prose."""
import re
import unicodedata
from .errors import DomainError

_UNSAFE = re.compile(
    r"\b(?:bypass|skip|disable|defeat|ignore|override|remove)\b.{0,70}"
    r"\b(?:safety|interlock|guard|lockout|tagout|loto|isolation)\b|"
    r"\b(?:without|no need for)\b.{0,30}\b(?:lockout|tagout|loto|isolation)\b|"
    r"\b(?:touch|repair|service|adjust)\b.{0,50}\b(?:energized|running|live)\b",
    re.IGNORECASE | re.DOTALL,
)


def screen_text(value: str) -> None:
    """Reject recognized unsafe procedural suggestions; no regex can prove arbitrary prose safe."""
    normalized = unicodedata.normalize("NFKC", value)
    if _UNSAFE.search(normalized):
        raise DomainError("unsafe_content", "Content requires a safety review.")


def require_approved_text(value: str, approved: list[str]) -> None:
    """Require exact reviewed source text and pass safety screening; reject all novel instructions."""
    screen_text(value)
    if value not in approved:
        raise DomainError("unapproved_prose", "Generated text is outside the approved source library.")
