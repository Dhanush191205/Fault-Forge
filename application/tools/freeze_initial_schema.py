"""Development-time migration generator. The checked-in generated schema is independent of future models."""
from pathlib import Path
from alembic.autogenerate import produce_migrations, render_python_code
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from app.db import Base
from app import models  # noqa: F401


def main():
    """Render initial create-table operations into a frozen migration module; never connect to a real database."""
    with create_engine("sqlite://").connect() as connection:
        changes = produce_migrations(MigrationContext.configure(connection), Base.metadata)
        code = render_python_code(changes.upgrade_ops)
    output = '"""Frozen v1 DDL, generated once before release. Do not regenerate against later models."""\nfrom alembic import op\nimport sqlalchemy as sa\n\n\ndef create_schema():\n    """Create the original v1 tables and indexes; caller owns the migration transaction."""\n' + code + '\n'
    Path("migrations/schema_v1.py").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
