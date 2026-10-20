import re

import pytest
from sqlalchemy import select

from app import models as m
from app.config import settings
from app.security import hash_password, verify_password


def test_argon2_password_hashing():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("incorrect", hashed)
    assert not verify_password("incorrect", "invalid hash")


@pytest.mark.parametrize("role", ["student", "lecturer", "viewer"])
def test_readers_cannot_edit_generate_or_export_drafts(login, role):
    client = login(role)
    assert client.post("/api/data/courses", json={}).status_code == 403
    assert client.post("/api/timetables/1/generate", json={}).status_code == 403
    assert client.get("/api/timetables/1").status_code == 404
    assert client.get("/api/users").status_code == 403
    assert client.get("/api/audit").status_code == 403
    assert client.post("/api/users", json={"role": "admin"}).status_code == 403


def test_department_idor_and_scope_change_are_blocked(login, database):
    admin = login()
    other = admin.post("/api/data/departments", json={"name": "Other", "code": "OTHER"}).json()
    coordinator = login("coordinator")
    response = coordinator.post(
        "/api/data/courses",
        json={"name": "Escape", "code": "ESC", "department_id": other["id"]},
    )
    assert response.status_code == 403
    with database() as db:
        t = m.Timetable(name="Private", department_id=other["id"], term_id=1, created_by=1)
        db.add(t)
        db.commit()
        tid = t.id
    assert coordinator.get(f"/api/timetables/{tid}").status_code == 403


def test_csrf_logout_and_session_invalidation(login):
    client = login()
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/data/departments", json={"name": "X", "code": "X"}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_origin_and_progressive_login_throttle(database):
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "x@example.com", "password": "bad"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        c.post("/api/auth/login", json={"email": "x@example.com", "password": "bad"}).status_code
        == 401
    )
    assert (
        c.post("/api/auth/login", json={"email": "x@example.com", "password": "bad"}).status_code
        == 429
    )


def test_reset_tokens_expire_are_single_use_and_revoke_sessions(login, database):
    c = login()
    response = c.post("/api/auth/forgot-password", json={"email": "admin@timeforge.example"})
    assert response.status_code == 200
    assert "token" not in response.text
    message = next(settings().mail_directory.glob("*.txt")).read_text()
    token = re.search(r"reset=([\w-]+)", message).group(1)
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "A-new-long-password!"},
        ).status_code
        == 200
    )
    assert c.get("/api/auth/me").status_code == 401
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "A-new-long-password!"},
        ).status_code
        == 400
    )
    with database() as db:
        assert db.scalar(select(m.ResetToken)).used


def test_audit_logs_and_user_responses_never_expose_credentials(login):
    c = login()
    response = c.get("/api/users")
    assert "password" not in response.text
    assert "token" not in response.text
    assert "argon2" not in c.get("/api/audit").text
    assert c.delete("/api/audit/1").status_code == 404


def test_validation_errors_do_not_echo_passwords(database):
    from fastapi.testclient import TestClient

    from app.main import app

    password = "secret" * 100
    response = TestClient(app).post(
        "/api/auth/login", json={"email": "invalid", "password": password}
    )
    assert response.status_code == 422
    assert password not in response.text


def test_viewers_cannot_read_unpublished_academic_data(login):
    c = login("viewer")
    for entity in [
        "courses",
        "sections",
        "rooms",
        "lecturers",
        "student-groups",
        "availability",
    ]:
        assert c.get(f"/api/data/{entity}").json()["items"] == []
    assert c.get("/api/data/constraints").status_code == 403


def test_expired_reset_token_is_rejected(login, database):
    from datetime import timedelta

    from app.db import utcnow

    c = login()
    c.post("/api/auth/forgot-password", json={"email": "admin@timeforge.example"})
    message = next(settings().mail_directory.glob("*.txt")).read_text()
    match = re.search(r"reset=([\w-]+)", message)
    assert match
    with database() as db:
        token = db.scalar(select(m.ResetToken))
        assert token
        token.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": match.group(1), "password": "A-valid-new-password!"},
        ).status_code
        == 400
    )
