import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import jobs
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.seed import seed

PASSWORD = "Test-Only-Strong-Password!"


@pytest.fixture(scope="session")
def seed_database(tmp_path_factory):
    path = tmp_path_factory.mktemp("template") / "seed.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as db:
        seed(db, PASSWORD)
    engine.dispose()
    return path


@pytest.fixture
def database(seed_database, tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    shutil.copy2(seed_database, path)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    monkeypatch.setattr(settings(), "jobs_eager", True)
    monkeypatch.setattr(settings(), "mail_directory", tmp_path / "mail")
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def login(database):
    clients = []

    def authenticate(role="admin"):
        client = TestClient(app)
        response = client.post(
            "/api/auth/login",
            json={"email": f"{role}@timeforge.example", "password": PASSWORD},
        )
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = client.cookies["tf_csrf"]
        clients.append(client)
        return client

    yield authenticate
    for client in clients:
        client.close()
