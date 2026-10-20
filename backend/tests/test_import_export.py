from datetime import date
from types import SimpleNamespace

from app.exports import calendar_bytes, fold_line, pdf_bytes
from app.schemas import Assignment


def test_csv_preview_is_rolled_back_and_import_is_atomic(login):
    c = login()
    good = b"name,code,description\nAstronomy,ASTRO,Science\n"
    path = "/api/imports/departments"
    preview = c.post(
        path, files={"file": ("departments.csv", good, "text/csv")}, data={"dry_run": "true"}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["status"] == "PREVIEW"
    assert c.get("/api/data/departments").json()["total"] == 1
    bad = b"name,code\nAstro,ASTRO\nDuplicate,SOC\n"
    result = c.post(path, files={"file": ("bad.csv", bad, "text/csv")}, data={"dry_run": "false"})
    assert result.json()["status"] == "INVALID"
    assert result.json()["errors"][0]["row"] == 3
    assert c.get("/api/data/departments").json()["total"] == 1
    result = c.post(path, files={"file": ("good.csv", good, "text/csv")}, data={"dry_run": "false"})
    assert result.json()["committed"]
    assert c.get("/api/data/departments").json()["total"] == 2


def test_malformed_and_oversize_csv_are_rejected(login):
    c = login()
    assert c.post("/api/imports/departments", files={"file": ("evil.exe", b"x")}).status_code == 422
    assert (
        c.post(
            "/api/imports/departments", files={"file": ("bad.csv", b"wrong,headers\nx,y")}
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/imports/departments", files={"file": ("bad.csv", b"x" * 2_000_001)}
        ).status_code
        == 413
    )


def test_csv_exports_escape_spreadsheet_formulas(login):
    c = login()
    assert (
        c.post("/api/data/departments", json={"name": "=CMD()", "code": "SAFE"}).status_code == 201
    )
    response = c.get("/api/imports/departments/export")
    assert "'=CMD()" in response.text


def test_ics_is_stable_folded_and_term_bounded():
    timetable = SimpleNamespace(id=1, name="Test, calendar")
    version = SimpleNamespace(id=1, version_number=1)
    term = SimpleNamespace(name="Autumn", start_date=date(2026, 10, 20), end_date=date(2026, 11, 2))
    sessions = [
        Assignment(
            section_id=1, session_number=1, day=0, start=540, end=600, room_id=1, lecturer_id=1
        )
    ]
    labels = {
        1: {
            "course": "Algorithms; " + "é" * 80,
            "rooms": {1: "Lab, 1"},
            "lecturer": "Dr X",
            "groups": "Y1",
        }
    }
    content = calendar_bytes(timetable, version, term, sessions, labels).decode()
    assert "DTSTART:20261026T033000Z" in content
    assert "RDATE:20261102T033000Z" in content
    assert "20261109" not in content
    assert "UID:tf-1-v1-s1-1@timeforge" in content
    assert "Lab\\, 1" in content
    assert all(len(line.encode()) <= 75 for line in content.split("\r\n"))
    assert fold_line("a" * 76) == "a" * 75 + "\r\n a"


def test_pdf_supports_long_escaped_content_and_multipage_tables():
    content = pdf_bytes(
        "<Timetable>",
        "Test term",
        ["Course", "Description"],
        [["CS101", "A & B < C " * 20] for _ in range(100)],
    )
    assert content.startswith(b"%PDF")
    assert len(content) > 5000
