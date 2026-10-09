"""Explicit account provisioning for private, single-organization installations."""
import argparse
import os
from sqlalchemy import select
from .contracts import validate_email, clean_text
from .db import SessionLocal
from .models import User, AuditEvent
from .security import password_hash


def main():
    """Provision one account from CLI identity and an environment password; reject overwrite and weak input."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["instructor", "trainee"], required=True)
    args = parser.parse_args()
    password = os.environ.get("BOOTSTRAP_PASSWORD", "")
    email, name = validate_email(args.email), clean_text(args.name)
    if not 12 <= len(password) <= 128 or not 1 <= len(name) <= 80:
        raise SystemExit("Set BOOTSTRAP_PASSWORD to 12–128 characters and provide a name of 1–80 characters.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("Account already exists. No account or password was overwritten.")
        user = User(email=email, name=name, role=args.role, password_hash=password_hash(password))
        db.add(user)
        db.flush()
        db.add(AuditEvent(actor_id=user.id, action="account_provisioned", target_id=user.id, details={"role": args.role}))
        db.commit()
    print("Account provisioned. Credentials were not logged.")


if __name__ == "__main__":
    main()
