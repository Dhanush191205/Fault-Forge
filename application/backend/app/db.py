"""SQLAlchemy transaction boundaries shared through public session interfaces."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    """Declarative model registry used by migrations."""


def make_engine(url: str):
    """Create a pooled engine for a database URL; connection failures propagate to the caller."""
    engine = create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _record):
            """Enable foreign keys and bounded busy waits for local fixture databases."""
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    """Yield a request session; rollback uncommitted work and release the connection on exit."""
    with SessionLocal() as session:
        yield session
