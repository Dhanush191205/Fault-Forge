"""Idempotent local synthetic bootstrap; real-source approvals are never inferred from fixture setup."""
import argparse
from pathlib import Path
from sqlalchemy import select
from .config import get_settings
from .contracts import PROFILES
from .curriculum import CurriculumPack, import_pack
from .db import SessionLocal
from .models import User, Machine, Source, AuditEvent
from .provider import FixtureProvider, generate_candidate
from .rag import retrieve
from .scenarios import persist_validated
from .security import password_hash


def seed_demo(db, settings, fixture_directory: Path) -> dict:
    """Create environment-configured accounts and nine validated drafts; never publish generated scenarios."""
    if not settings.demo_mode:
        raise ValueError("Synthetic bootstrap is disabled outside demo mode")
    identities = []
    for role, email, password, name in [("instructor", settings.instructor_email, settings.instructor_password, "Training instructor"),
                                       ("trainee", settings.trainee_email, settings.trainee_password, "Alex Morgan")]:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            if len(password) < 12:
                raise ValueError("Set environment bootstrap passwords with at least 12 characters")
            user = User(email=email, name=name, role=role, password_hash=password_hash(password))
            db.add(user)
            db.flush()
        identities.append(user)
    owner = identities[0]
    imported = 0
    for file in sorted(fixture_directory.glob("*.json")):
        pack = CurriculumPack.model_validate_json(file.read_text(encoding="utf-8"))
        if db.get(Machine, pack.machine.id):
            continue
        ids = import_pack(db, pack, owner.id, demo_mode=True)
        for source in db.scalars(select(Source).where(Source.id.in_(ids))):
            source.approved = True
            db.add(AuditEvent(actor_id=owner.id, action="synthetic_fixture_loaded", target_id=source.id,
                              details={"checksum": source.checksum, "scope": "demo only; not instructor-qualified"}))
        db.flush()
        for difficulty in PROFILES:
            request = {"machine_id": pack.machine.id, "difficulty": difficulty, "source_ids": ids,
                       "brief": "Select the authored synthetic diagnostic exercise."}
            bundle = retrieve(db, settings.model_copy(update={"rag_backend": "fixture", "llm_provider": "fixture"}),
                              pack.machine.id, ids, request["brief"])
            candidate = generate_candidate(FixtureProvider(), bundle, request)
            persist_validated(db, owner.id, candidate, bundle, request, "synthetic-fixture/1.0")
        imported += 1
    db.commit()
    return {"machines_imported": imported, "drafts_created": imported * 3}


def main():
    """Run explicit synthetic seeding or vector indexing; return counts and never print credentials."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["demo", "index"])
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "demo":
            print(seed_demo(db, get_settings(), Path(__file__).resolve().parents[2] / "data"))
        else:
            from .rag import index_sources
            print({"indexed": index_sources(db, get_settings())})


if __name__ == "__main__":
    main()
