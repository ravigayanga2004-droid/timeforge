from collections import Counter

from fastapi import HTTPException
from sqlalchemy import func, select

from app import models as m
from app.db import utcnow
from app.domain import load_problem, score_solution, validate_solution
from app.reference import serialize
from app.schemas import Assignment
from app.security import MANAGERS, create_audit_log, require_department_access


def timetable_access(db, timetable_id, user, write=False, lock=False):
    query = select(m.Timetable).where(m.Timetable.id == timetable_id)
    if lock:
        query = query.with_for_update()
    timetable = db.scalar(query)
    if not timetable:
        raise HTTPException(404, "Timetable not found")
    require_department_access(user, timetable.department_id)
    if write and user.role not in MANAGERS:
        raise HTTPException(403, "Your role cannot modify timetables")
    if user.role not in MANAGERS and (
        not timetable.published_version_id or timetable.status == "ARCHIVED"
    ):
        raise HTTPException(404, "Published timetable not found")
    return timetable


def version_access(db, version_id, user, write=False):
    version = db.get(m.TimetableVersion, version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    timetable = timetable_access(db, version.timetable_id, user, write)
    if user.role not in MANAGERS and timetable.published_version_id != version.id:
        raise HTTPException(403, "Only the published version is available to your role")
    return timetable, version


def assignments(db, version_id):
    return [
        Assignment.model_validate({key: getattr(row, key) for key in Assignment.model_fields})
        for row in db.scalars(
            select(m.ScheduledSession)
            .where(m.ScheduledSession.version_id == version_id)
            .order_by(m.ScheduledSession.section_id, m.ScheduledSession.session_number)
        )
    ]


def personal_filter(db, sessions, user):
    if user.role == "lecturer":
        ids = set(db.scalars(select(m.Lecturer.id).where(m.Lecturer.user_id == user.id)))
        return [a for a in sessions if a.lecturer_id in ids]
    if user.role == "student":
        section_ids = set(
            db.scalars(
                select(m.CourseEnrollmentGroup.section_id).where(
                    m.CourseEnrollmentGroup.group_id == user.group_id
                )
            )
        )
        return [a for a in sessions if a.section_id in section_ids]
    return sessions


def metrics(p, sessions, violations):
    duration = sum(a.end - a.start for a in sessions)
    available = sum(s.end - s.start for s in p.slots.values()) * sum(
        r.is_active for r in p.rooms.values()
    )
    penalties: Counter[str] = Counter()
    for v in violations:
        if v.severity == "soft":
            penalties[v.code] += v.penalty
    return {
        "session_count": len(sessions),
        "teaching_minutes": duration,
        "room_utilization": round(100 * duration / available, 2) if available else 0,
        "penalties": dict(penalties),
        "total_penalty": sum(penalties.values()),
        "sessions_per_day": dict(Counter(a.day for a in sessions)),
        "lecturer_minutes": dict(
            Counter(
                {
                    str(lecturer): sum(
                        a.end - a.start for a in sessions if a.lecturer_id == lecturer
                    )
                    for lecturer in p.lecturers
                }
            )
        ),
        "group_minutes": {
            str(g): sum(
                a.end - a.start for a in sessions if g in p.enrollment.get(a.section_id, set())
            )
            for g in p.groups
        },
        "room_minutes": {
            str(r): sum(a.end - a.start for a in sessions if a.room_id == r) for r in p.rooms
        },
        "room_capacity_utilization": round(
            sum(
                p.sections[a.section_id].expected_enrollment / p.rooms[a.room_id].capacity
                for a in sessions
                if a.section_id in p.sections and a.room_id in p.rooms
            )
            / max(1, len(sessions))
            * 100,
            2,
        ),
    }


def persist_version(
    db, timetable, sessions, problem, configuration, job_id=None, allow_conflicts=False
):
    violations = validate_solution(problem, sessions) + score_solution(problem, sessions)
    hard = [v for v in violations if v.severity == "hard"]
    if hard and not allow_conflicts:
        raise HTTPException(
            422,
            {
                "message": "Hard conflicts must be resolved before saving",
                "violations": [v.json() for v in violations],
            },
        )
    number = (
        db.scalar(
            select(func.max(m.TimetableVersion.version_number)).where(
                m.TimetableVersion.timetable_id == timetable.id
            )
        )
        or 0
    ) + 1
    version = m.TimetableVersion(
        timetable_id=timetable.id,
        version_number=number,
        generation_job_id=job_id,
        hard_violations=len(hard),
        soft_violations=len(violations) - len(hard),
        score=sum(v.penalty for v in violations),
        status="DRAFT" if hard else "GENERATED",
        metrics=metrics(problem, sessions, violations),
        configuration=configuration,
    )
    db.add(version)
    db.flush()
    # A draft can retain conflicts, but duplicate keys cannot be persisted as separate assignments.
    if len({(a.section_id, a.session_number) for a in sessions}) != len(sessions):
        raise HTTPException(
            422,
            "Duplicate session identifiers cannot be saved; use a new session number",
        )
    for a in sessions:
        row = m.ScheduledSession(version_id=version.id, **a.model_dump())
        db.add(row)
        db.flush()
        db.add(m.SessionRoom(session_id=row.id, room_id=a.room_id))
        for slot in problem.slots.values():
            if slot.day == a.day and a.start <= slot.start and slot.end <= a.end:
                db.add(m.SessionTimeSlot(session_id=row.id, slot_id=slot.id))
    db.add_all(m.ConstraintViolation(version_id=version.id, **v.json()) for v in violations)
    return version


def notify(db, timetable, message, all_roles=False):
    query = select(m.User).where(
        m.User.is_active.is_(True),
        (m.User.department_id == timetable.department_id) | (m.User.role == "admin"),
    )
    if not all_roles:
        query = query.where(m.User.role.in_(MANAGERS))
    for user in db.scalars(query):
        db.add(m.Notification(user_id=user.id, message=message, timetable_id=timetable.id))


def transition(db, timetable, user, action, notes):
    if timetable.status == "GENERATING":
        raise HTTPException(409, "Wait for generation to finish or cancel the job")
    if not timetable.current_version_id:
        raise HTTPException(409, "Generate a timetable before changing its workflow state")
    version = db.get(m.TimetableVersion, timetable.current_version_id)
    allowed = {
        "submit": {"GENERATED", "DRAFT", "REJECTED"},
        "approve": {"UNDER_REVIEW"},
        "reject": {"UNDER_REVIEW"},
        "publish": {"APPROVED"},
        "archive": {"DRAFT", "GENERATED", "REJECTED", "APPROVED", "PUBLISHED"},
        "reopen": {"ARCHIVED"},
    }
    if action in {"approve", "reject", "publish", "reopen"} and user.role != "admin":
        raise HTTPException(403, "An administrator must perform this action")
    if timetable.status not in allowed[action]:
        raise HTTPException(409, f"Cannot {action} a timetable in state {timetable.status}")
    if action in {"reject", "reopen"} and not notes.strip():
        raise HTTPException(422, "Please provide decision notes")
    if action in {"submit", "approve", "publish"}:
        p = load_problem(db, timetable, version.configuration)
        violations = validate_solution(p, assignments(db, version.id))
        if violations:
            raise HTTPException(
                422,
                {
                    "message": "Hard conflicts block submission, approval and publication",
                    "violations": [v.json() for v in violations],
                },
            )
        soft = score_solution(p, assignments(db, version.id))
        if action == "publish" and soft and not notes.strip():
            raise HTTPException(
                422, "Publication notes are required when soft constraints are violated"
            )
        if action == "publish":
            # Serialize publications for a department/term and prevent two active
            # snapshots from representing the same academic week.
            db.scalar(
                select(m.AcademicTerm)
                .where(m.AcademicTerm.id == timetable.term_id)
                .with_for_update()
            )
            existing = db.scalar(
                select(m.Timetable).where(
                    m.Timetable.id != timetable.id,
                    m.Timetable.department_id == timetable.department_id,
                    m.Timetable.term_id == timetable.term_id,
                    m.Timetable.published_version_id.is_not(None),
                    m.Timetable.status != "ARCHIVED",
                )
            )
            if existing:
                raise HTTPException(
                    409,
                    "Archive the previously published timetable for this department and term before publishing another.",
                )
    states = {
        "submit": "UNDER_REVIEW",
        "approve": "APPROVED",
        "reject": "REJECTED",
        "publish": "PUBLISHED",
        "archive": "ARCHIVED",
        "reopen": "DRAFT",
    }
    timetable.status = states[action]
    if action == "approve":
        timetable.approved_by = user.id
    if action == "publish":
        timetable.published_version_id = version.id
        timetable.published_at = utcnow()
    db.add(
        m.ScheduleApproval(
            timetable_id=timetable.id,
            version_id=version.id,
            actor_id=user.id,
            decision=action,
            notes=notes,
        )
    )
    create_audit_log(
        db,
        user,
        action,
        "timetable",
        timetable.id,
        {"version_id": version.id, "notes": notes},
    )
    notify(
        db,
        timetable,
        f"{timetable.name}: {states[action].replace('_',' ').lower()}. {notes}",
        all_roles=action == "publish",
    )
    return serialize(timetable)
