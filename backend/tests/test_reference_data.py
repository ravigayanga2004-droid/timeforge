import pytest


@pytest.mark.parametrize(
    "entity,payload",
    [
        ("departments", {"name": "Research", "code": "RES"}),
        ("academic-years", {"name": "2027/28"}),
        ("buildings", {"name": "South", "code": "SOUTH"}),
        (
            "rooms",
            {
                "name": "South Hall",
                "code": "S-1",
                "building_id": 1,
                "department_id": 1,
                "capacity": 40,
                "feature_ids": [1],
            },
        ),
        (
            "lecturers",
            {
                "name": "Dr Test",
                "email": "test@example.com",
                "employee_number": "EMP99",
                "department_id": 1,
            },
        ),
        (
            "student-groups",
            {"name": "Test group", "code": "G99", "department_id": 1, "size": 35},
        ),
        ("courses", {"name": "Test course", "code": "TC99", "department_id": 1}),
        (
            "sections",
            {
                "code": "TC99-A",
                "course_id": 1,
                "term_id": 1,
                "department_id": 1,
                "lecturer_id": 1,
                "expected_enrollment": 35,
                "group_ids": [1],
            },
        ),
    ],
)
def test_reference_crud_validation_and_archival(login, entity, payload):
    c = login()
    response = c.post(f"/api/data/{entity}", json=payload)
    assert response.status_code == 201, response.text
    record = response.json()
    response = c.put(f"/api/data/{entity}/{record['id']}", json=payload)
    assert response.status_code == 200, response.text
    assert c.delete(f"/api/data/{entity}/{record['id']}").status_code == 200


def test_room_limits_foreign_keys_and_slot_overlap_are_validated(login):
    c = login()
    base = {
        "name": "Bad",
        "code": "BAD",
        "building_id": 1,
        "department_id": 1,
        "capacity": 0,
    }
    assert c.post("/api/data/rooms", json=base).status_code == 422
    assert (
        c.post("/api/data/rooms", json={**base, "capacity": 30, "building_id": 999}).status_code
        == 422
    )
    assert (
        c.post(
            "/api/data/time-slots",
            json={"day": 0, "start": 500, "end": 550, "period": 9},
        ).status_code
        == 422
    )
    assert c.get("/api/data/rooms?sort=drop_table").status_code == 422
    assert c.get("/api/data/courses?q=%27%20OR%201=1--").status_code == 200


def test_section_requires_groups_and_correct_department(login):
    c = login()
    base = {
        "code": "NO-GROUP",
        "course_id": 1,
        "term_id": 1,
        "department_id": 1,
        "lecturer_id": 1,
        "expected_enrollment": 35,
        "group_ids": [],
    }
    assert c.post("/api/data/sections", json=base).status_code == 422


def test_lecturer_availability_ownership_cannot_be_stolen(login):
    c = login("lecturer")
    response = c.put(
        "/api/data/availability/1",
        json={
            "department_id": 1,
            "term_id": 1,
            "lecturer_id": 2,
            "slot_id": 1,
            "kind": "unavailable",
        },
    )
    assert response.status_code == 403
