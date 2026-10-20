from sqlalchemy import func, select

from app import models as m
from app.jobs import run_generation


def generate(client):
    response = client.post(
        "/api/timetables/1/generate",
        json={"alternatives": 2, "time_limit": 20, "section_ids": [1, 2, 3]},
    )
    assert response.status_code == 202, response.text
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "COMPLETED", job
    timetable = client.get("/api/timetables/1").json()
    return (
        timetable,
        client.get(f"/api/versions/{timetable['current_version_id']}").json(),
        job,
    )


def test_generation_edit_approval_publication_and_scoped_exports(login, database):
    coordinator = login("coordinator")
    admin = login()
    timetable, version, job = generate(coordinator)
    assert len(timetable["versions"]) == 2
    assert version["hard_violations"] == 0
    assert len(version["sessions"]) == 6
    assert (
        coordinator.get("/api/timetables/1/compare").json()["differences"][0]["changed_sessions"]
        > 0
    )
    run_generation(job["id"])
    assert len(coordinator.get("/api/timetables/1").json()["versions"]) == 2
    sessions = version["sessions"]
    sessions[0]["is_locked"] = True
    result = coordinator.post(
        "/api/timetables/1/edit",
        json={"base_version_id": version["id"], "sessions": sessions},
    )
    assert result.status_code == 201, result.text
    new = result.json()
    assert new["version_number"] == 3
    assert (
        coordinator.post(
            "/api/timetables/1/edit",
            json={"base_version_id": version["id"], "sessions": sessions},
        ).status_code
        == 409
    )
    moved = [dict(a) for a in sessions]
    moved[0]["day"] = (moved[0]["day"] + 1) % 5
    preview = coordinator.post(
        "/api/timetables/1/preview",
        json={"base_version_id": new["id"], "sessions": moved},
    ).json()
    assert not preview["valid"]
    assert any(v["code"] == "HC017" for v in preview["violations"])
    assert (
        coordinator.post(
            "/api/timetables/1/edit",
            json={"base_version_id": new["id"], "sessions": moved, "allow_draft_conflicts": True},
        ).status_code
        == 422
    )
    assert (
        coordinator.post("/api/timetables/1/workflow", json={"action": "submit"}).status_code == 200
    )
    assert (
        coordinator.post("/api/timetables/1/workflow", json={"action": "approve"}).status_code
        == 403
    )
    assert admin.post("/api/timetables/1/workflow", json={"action": "approve"}).status_code == 200
    assert (
        admin.post(
            "/api/timetables/1/workflow",
            json={
                "action": "publish",
                "notes": "Accepted preferences after academic review",
            },
        ).status_code
        == 200
    )
    student = login("student")
    viewer = login("viewer")
    lecturer = login("lecturer")
    published = student.get(f"/api/versions/{new['id']}").json()
    assert published["sessions"]
    assert viewer.get(f"/api/versions/{version['id']}").status_code == 403
    assert all(
        a["lecturer_id"] == 1 for a in lecturer.get(f"/api/versions/{new['id']}").json()["sessions"]
    )
    for format, signature in [
        ("ics", b"BEGIN:VCALENDAR"),
        ("pdf", b"%PDF"),
        ("csv", b"\xef\xbb\xbf"),
    ]:
        exported = student.get(f"/api/versions/{new['id']}/export/{format}")
        assert exported.status_code == 200, exported.text
        assert exported.content.startswith(signature)
    assert student.get(f"/api/versions/{new['id']}/export/pdf?report=conflicts").status_code == 403
    # Creating a new draft must preserve the public snapshot.
    sessions[0]["notes"] = "Reviewed"
    draft = coordinator.post(
        "/api/timetables/1/edit",
        json={"base_version_id": new["id"], "sessions": sessions},
    )
    assert draft.status_code == 201, draft.text
    assert student.get(f"/api/versions/{new['id']}").status_code == 200
    assert student.get(f"/api/versions/{draft.json()['id']}").status_code == 403
    with database() as db:
        assert db.scalar(select(func.count(m.AuditLog.id))) > 10
        assert db.scalar(select(func.count(m.ExportJob.id))) == 3
        assert db.scalar(select(func.count(m.Notification.id))) > 0


def test_invalid_draft_cannot_be_submitted_or_published(login):
    c = login()
    _, version, _ = generate(c)
    sessions = version["sessions"][:-1]
    rejected = c.post(
        "/api/timetables/1/edit",
        json={"base_version_id": version["id"], "sessions": sessions},
    )
    assert rejected.status_code == 422
    draft = c.post(
        "/api/timetables/1/edit",
        json={
            "base_version_id": version["id"],
            "sessions": sessions,
            "allow_draft_conflicts": True,
        },
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["hard_violations"] > 0
    assert c.post("/api/timetables/1/workflow", json={"action": "submit"}).status_code == 422
    assert c.post("/api/timetables/1/workflow", json={"action": "publish"}).status_code in [
        409,
        422,
    ]


def test_bulk_availability_is_atomic_and_lecturers_cannot_change_others(login):
    c = login("lecturer")
    data = {
        "department_id": 1,
        "term_id": 1,
        "lecturer_id": 1,
        "slot_id": 1,
        "kind": "preferred",
    }
    response = c.post("/api/availability/bulk", json={"records": [data]})
    assert response.status_code == 200, response.text
    assert (
        c.post("/api/availability/bulk", json={"records": [{**data, "lecturer_id": 2}]}).status_code
        == 403
    )
    assert c.get("/api/data/availability").json()["items"][0]["lecturer_id"] == 1


def test_job_cancel_and_failed_retry(login, database, monkeypatch):
    from app.config import settings
    from app.jobs import generate as task

    monkeypatch.setattr(settings(), "jobs_eager", False)
    monkeypatch.setattr(task, "apply_async", lambda **kwargs: None)
    c = login()
    first = c.post(
        "/api/timetables/1/generate",
        json={"section_ids": [1, 2, 3], "alternatives": 2, "time_limit": 20},
    ).json()
    assert first["status"] == "QUEUED"
    assert c.post(f"/api/jobs/{first['id']}/cancel").json()["status"] == "CANCELLED"
    run_generation(first["id"])
    with database() as db:
        assert db.scalar(select(func.count(m.TimetableVersion.id))) == 0
    monkeypatch.setattr(settings(), "jobs_eager", True)
    retried = c.post(f"/api/jobs/{first['id']}/retry")
    assert retried.status_code == 202
    assert c.get(f"/api/jobs/{retried.json()['id']}").json()["status"] == "COMPLETED"
