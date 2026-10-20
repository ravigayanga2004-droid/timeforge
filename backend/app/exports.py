import io
from datetime import UTC, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.config import settings
from app.db import get_db
from app.domain import load_problem, score_solution, validate_solution
from app.imports import csv_bytes
from app.security import MANAGERS, create_audit_log, require_auth
from app.timetable_service import assignments, personal_filter, version_access

router = APIRouter(prefix="/api/versions", tags=["Exports"])
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def clock(value):
    return f"{value//60:02d}:{value%60:02d}"


def ics_escape(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
    )


def fold_line(line):
    # RFC 5545 folds at 75 octets, preserving UTF-8 character boundaries.
    result, current = [], ""
    for char in line:
        if len((current + char).encode()) > 75:
            result.append(current)
            current = " " + char
        else:
            current += char
    result.append(current)
    return "\r\n".join(result)


def calendar_bytes(timetable, version, term, sessions, labels, timezone_name=None):
    timezone_name = timezone_name or settings().timezone
    zone = ZoneInfo(timezone_name)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TimeForge//Academic Scheduling 1.0//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(timetable.name)}",
        f"X-WR-TIMEZONE:{ics_escape(timezone_name)}",
        f"X-TIMEFORGE-TERM:{ics_escape(term.name)}",
        f"X-TIMEFORGE-VERSION:{version.version_number}",
    ]
    for a in sessions:
        first = term.start_date + timedelta(days=(a.day - term.start_date.weekday()) % 7)
        if first > term.end_date:
            continue
        starts = []
        day = first
        while day <= term.end_date:
            dt = datetime.combine(day, time.min, tzinfo=zone) + timedelta(minutes=a.start)
            starts.append(dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ"))
            day += timedelta(days=7)
        end = (
            (datetime.combine(first, time.min, tzinfo=zone) + timedelta(minutes=a.end))
            .astimezone(UTC)
            .strftime("%Y%m%dT%H%M%SZ")
        )
        label = labels[a.section_id]
        lines += [
            "BEGIN:VEVENT",
            f"UID:tf-{timetable.id}-v{version.id}-s{a.section_id}-{a.session_number}@timeforge",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{starts[0]}",
            f"DTEND:{end}",
            f"SUMMARY:{ics_escape(label['course'])}",
            f"LOCATION:{ics_escape(label['rooms'][a.room_id])}",
            f"DESCRIPTION:{ics_escape(term.name+' · version '+str(version.version_number)+' · '+label['lecturer']+' · '+label['groups']+' · '+timezone_name)}",
        ]
        if len(starts) > 1:
            lines.append("RDATE:" + ",".join(starts[1:]))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode()


def pdf_bytes(title, subtitle, headers, rows, timezone_name=None):
    timezone_name = timezone_name or settings().timezone
    output = io.BytesIO()
    style = getSampleStyleSheet()
    style["BodyText"].fontSize = 8
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4), rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=30
    )
    elements = [
        Paragraph(escape(title), style["Title"]),
        Paragraph(escape(subtitle), style["BodyText"]),
        Spacer(1, 15),
    ]
    table = LongTable(
        [
            [Paragraph(escape(str(value)), style["BodyText"]) for value in row]
            for row in [headers] + rows
        ],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcece6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f6")]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#164b45")),
            ]
        )
    )
    elements.append(table)

    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(28, 16, f"TimeForge | {timezone_name} | Page {document.page}")

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


@router.get("/{version_id}/export/{format}")
def export(
    version_id: int,
    format: str,
    report: str = "schedule",
    lecturer_id: int | None = None,
    group_id: int | None = None,
    room_id: int | None = None,
    user: m.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    timetable, version = version_access(db, version_id, user)
    department = db.get(m.Department, timetable.department_id)
    university = (
        db.get(m.University, department.university_id)
        if department and department.university_id
        else None
    )
    timezone_name = university.timezone if university else settings().timezone
    if format not in {"csv", "ics", "pdf"} or report not in {"schedule", "conflicts", "generation"}:
        raise HTTPException(422, "Choose PDF, CSV or ICS and a supported report")
    if report != "schedule" and user.role not in MANAGERS:
        raise HTTPException(403, "This report requires a coordinator role")
    sessions = personal_filter(db, assignments(db, version_id), user)
    if lecturer_id:
        sessions = [a for a in sessions if a.lecturer_id == lecturer_id]
    if group_id:
        enrolled = set(
            db.scalars(
                select(m.CourseEnrollmentGroup.section_id).where(
                    m.CourseEnrollmentGroup.group_id == group_id
                )
            )
        )
        sessions = [a for a in sessions if a.section_id in enrolled]
    if room_id:
        sessions = [a for a in sessions if a.room_id == room_id]
    p = load_problem(db, timetable, version.configuration)
    term = p.term
    rooms = {r.id: r.name for r in p.rooms.values()}
    labels = {}
    for section_id in {a.section_id for a in sessions}:
        section = db.get(m.CourseSection, section_id)
        if not section:
            raise HTTPException(409, "A referenced course section is no longer available")
        course = db.get(m.Course, section.course_id)
        lecturer = db.get(m.Lecturer, section.lecturer_id)
        if not course or not lecturer:
            raise HTTPException(409, "Referenced course or lecturer data is no longer available")
        groups = ", ".join(
            g.name for g in p.groups.values() if g.id in p.enrollment.get(section_id, set())
        )
        labels[section_id] = {
            "course": f"{course.code} · {course.name}",
            "lecturer": lecturer.name,
            "groups": groups,
            "rooms": rooms,
        }
    subtitle = f"{term.name} | {term.start_date} to {term.end_date} | Version {version.version_number} | {timezone_name} | Exported {datetime.now(ZoneInfo(timezone_name)).isoformat(timespec='seconds')}"
    if report == "conflicts":
        headers = ["Code", "Severity", "Explanation", "Penalty", "Suggested resolution"]
        rows = [
            [v.code, v.severity, v.description, v.penalty, v.suggestion]
            for v in validate_solution(p, sessions) + score_solution(p, sessions)
        ]
    elif report == "generation":
        headers = ["Metric", "Value"]
        rows = [
            ["Total penalty", version.score],
            ["Hard violations", version.hard_violations],
            ["Soft violations", version.soft_violations],
            ["Configuration", str(version.configuration)],
            ["Metrics", str(version.metrics)],
        ]
    else:
        headers = ["Course", "Day", "Start", "End", "Room", "Lecturer", "Groups"]
        rows = [
            [
                labels[a.section_id]["course"],
                DAYS[a.day],
                clock(a.start),
                clock(a.end),
                rooms.get(a.room_id, "Removed room"),
                labels[a.section_id]["lecturer"],
                labels[a.section_id]["groups"],
            ]
            for a in sorted(sessions, key=lambda a: (a.day, a.start))
        ]
    if format == "ics":
        if report != "schedule":
            raise HTTPException(422, "ICS is available for schedules only")
        content = calendar_bytes(timetable, version, term, sessions, labels, timezone_name)
        media = "text/calendar"
    elif format == "pdf":
        content, media = (
            pdf_bytes(timetable.name, subtitle, headers, rows, timezone_name),
            "application/pdf",
        )
    else:
        content, media = (
            csv_bytes(
                ["Term", "Version", "Timezone", "Exported"] + headers,
                [
                    [
                        term.name,
                        version.version_number,
                        timezone_name,
                        datetime.now(UTC).isoformat(),
                    ]
                    + row
                    for row in rows
                ],
            ),
            "text/csv",
        )
    db.add(m.ExportJob(created_by=user.id, version_id=version_id, format=format))
    create_audit_log(
        db,
        user,
        "export",
        "version",
        version_id,
        {"format": format, "report": report, "sessions": len(sessions)},
    )
    return Response(
        content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="timeforge-v{version.version_number}-{report}.{format}"'
        },
    )
