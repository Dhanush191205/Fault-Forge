"""Alembic migration runtime; connection credentials come exclusively from environment settings."""
from alembic import context
from sqlalchemy import create_engine
from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    existing = context.config.attributes.get("connection")
    def migrate(connection):
        """Apply migrations on a supplied connection; transaction failures propagate to Alembic."""
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    if existing is not None:
        migrate(existing)
    else:
        with create_engine(get_settings().database_url).connect() as connection:
            migrate(connection)
