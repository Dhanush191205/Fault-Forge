"""Isolated real-schema fixtures: every test migrates a fresh database and uses generated credentials."""
import secrets
import os
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from fastapi.testclient import TestClient
from app.config import Settings
from app.db import make_engine, get_db
from app.main import app
from app.models import User
from app.seed import seed_demo


@pytest.fixture
def system(tmp_path):
    """Yield a migrated SQLite system with independent sessions and generated bootstrap secrets."""
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    engine = make_engine(url)
    schema = "ff_test_" + secrets.token_hex(8)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine.dispose()
        from sqlalchemy import create_engine
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    with engine.connect() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    factory = sessionmaker(engine, expire_on_commit=False)
    settings = Settings(instructor_password=secrets.token_urlsafe(20), trainee_password=secrets.token_urlsafe(20))
    with factory() as db:
        seed_demo(db, settings, Path("../data"))
        users = {u.role: u.id for u in db.scalars(select(User))}
    yield factory, settings, users
    if engine.dialect.name == "postgresql":
        # Only the random schema created by this fixture is removed; never the caller's public schema.
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


@pytest.fixture
def clients(system):
    """Yield authenticated instructor/trainee HTTP clients against the isolated session factory."""
    factory, settings, users = system
    def dependency():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as teacher, TestClient(app) as trainee:
        for client, email, password in [(teacher, settings.instructor_email, settings.instructor_password),
                                         (trainee, settings.trainee_email, settings.trainee_password)]:
            client.headers["origin"] = "http://localhost:5173"
            response = client.post("/api/auth/login", json={"email": email, "password": password})
            assert response.status_code == 200, response.text
            client.headers["x-csrf-token"] = response.json()["csrf"]
        yield teacher, trainee, factory, settings, users
    app.dependency_overrides.clear()
