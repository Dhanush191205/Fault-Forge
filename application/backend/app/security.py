"""Password hashing, revocable sessions, CSRF and shared rate limits."""
import hashlib
import hmac
import secrets
import time
from datetime import timedelta
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import Depends, Request
from .config import get_settings
from .db import get_db
from .errors import DomainError
from .models import AuthSession, User, RateBucket, utcnow


def password_hash(password: str) -> str:
    """Hash a bounded password using a random salt and scrypt; return a versioned stored string."""
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Verify supplied password in constant time; return false for malformed stored hashes."""
    try:
        kind, salt, expected = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return kind == "scrypt" and hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def limit(db, scope: str, key: str, maximum: int, seconds: int = 60) -> None:
    """Atomically consume a DB-backed rate allowance; commit before work and raise 429 on exhaustion."""
    bucket = f"{scope}:{hashlib.sha256(key.encode()).hexdigest()}:{int(time.time()) // seconds}"
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(RateBucket).values(key=bucket, count=0).on_conflict_do_nothing())
    accepted = db.execute(update(RateBucket).where(RateBucket.key == bucket, RateBucket.count < maximum)
                          .values(count=RateBucket.count + 1)).rowcount
    db.commit()
    if not accepted:
        raise DomainError("rate_limited", "Too many requests. Please try again later.", 429)


def create_session(db, user: User) -> tuple[str, str]:
    """Persist a hashed expiring session for a user; return cookie secret and CSRF token."""
    token, csrf = secrets.token_urlsafe(32), secrets.token_hex(24)
    db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                       csrf=csrf, expires_at=utcnow() + timedelta(hours=get_settings().session_hours)))
    db.commit()
    return token, csrf


def current_user(request: Request, db=Depends(get_db)) -> User:
    """Authenticate the HttpOnly session and enforce CSRF for mutations; raise safe 401/403 errors."""
    token = request.cookies.get("ff_session", "")
    session = db.scalar(select(AuthSession).where(
        AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest(),
        AuthSession.expires_at > utcnow(), AuthSession.revoked.is_(False)))
    if not session:
        raise DomainError("unauthenticated", "Sign in to continue.", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") not in get_settings().allowed_origins:
            raise DomainError("origin_denied", "This origin is not permitted.", 403)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            raise DomainError("csrf_failed", "Refresh the page and try again.", 403)
    request.state.auth_session = session
    user = db.get(User, session.user_id)
    if not user:
        raise DomainError("unauthenticated", "Sign in to continue.", 401)
    return user


def instructor(user=Depends(current_user)) -> User:
    """Require an authenticated instructor; return identity or a safe 403 error."""
    if user.role != "instructor":
        raise DomainError("forbidden", "Instructor access is required.", 403)
    return user
