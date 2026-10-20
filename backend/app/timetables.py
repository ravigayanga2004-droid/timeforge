from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models as m
from app.config import settings
from app.db import get_db, utcnow
from app.domain import HARD_CONSTRAINTS, load_problem, score_solution, validate_solution
from app.jobs import generate, run_generation
from app.reference import serialize
from app.schemas import DecisionIn, EditIn, GenerationIn, SelectIn, TimetableIn
from app.security import (
    MANAGERS,
    create_audit_log,
    require_auth,
    require_department_access,
    require_permission,
)
from app.timetable_service import (
    assignments,
    metrics,
    notify,
    persist_version,
    personal_filter,
    timetable_access,
    transition,
    version_access,
)

router = APIRouter(prefix="/api", tags=["Timetables"])


@router.get("/constraints/hard")
def hard_constraints(user: m.User = Depends(require_auth)):
    return HARD_CONSTRAINTS


@router.get("/timetables")
def listing(
    user: m.User = Depends(require_auth),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    query = select(m.Timetable)
    if user.role != "admin":
        query = query.where(m.Timetable.department_id == user.department_id)
    if user.role not in MANAGERS:
        query = query.where(
            m.Timetable.published_version_id.is_not(None), m.Timetable.status != "ARCHIVED"
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            serialize(t)
            for t in db.scalars(query.order_by(m.Timetable.id.desc()).offset(offset).limit(limit))
        ],
        "total": total,
    }


@router.post("/timetables", status_code=201)
def create(
    data: TimetableIn,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    require_department_access(user, data.department_id)
    term = db.get(m.AcademicTerm, data.term_id)
    if not term or term.department_id != data.department_id or term.status == "archived":
        raise HTTPException(422, "Choose an active term in the same department")
    timetable = m.Timetable(**data.model_dump(), created_by=user.id)
    db.add(timetable)
    db.flush()
    create_audit_log(db, user, "create", "timetable", timetable.id)
    return serialize(timetable)


@router.get("/timetables/{timetable_id}")
def detail(timetable_id: int, user: m.User = Depends(require_auth), db: Session = Depends(get_db)):
    t = timetable_access(db, timetable_id, user)
    result = serialize(t)
    versions = select(m.TimetableVersion).where(m.TimetableVersion.timetable_id == t.id)
    if user.role not in MANAGERS:
        versions = versions.where(m.TimetableVersion.id == t.published_version_id)
    result["versions"] = [
        serialize(v)
        for v in db.scalars(versions.order_by(m.TimetableVersion.version_number.desc()))
    ]
    result["jobs"] = (
        [
            serialize(j)
            for j in db.scalars(
                select(m.GenerationJob)
                .where(m.GenerationJob.timetable_id == t.id)
                .order_by(m.GenerationJob.id.desc())
                .limit(20)
            )
        ]
        if user.role in MANAGERS
        else []
    )
    result["approvals"] = [
        serialize(a)
        for a in db.scalars(
            select(m.ScheduleApproval)
            .where(m.ScheduleApproval.timetable_id == t.id)
            .order_by(m.ScheduleApproval.id.desc())
            .limit(100)
        )
    ]
    if user.role not in MANAGERS:
        result["current_version_id"] = t.published_version_id
    return result


@router.post("/timetables/{timetable_id}/generate", status_code=202)
def start(
    timetable_id: int,
    config: GenerationIn,
    tasks: BackgroundTasks,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    timetable = timetable_access(db, timetable_id, user, True, True)
    if timetable.status in {"GENERATING", "UNDER_REVIEW", "APPROVED", "ARCHIVED"}:
        raise HTTPException(409, "Generation is unavailable in the current workflow state")
    problem = load_problem(db, timetable, config.model_dump())
    if not problem.sections:
        raise HTTPException(422, "Add active course sections for this term before generation")
    for key, available in [
        ("section_ids", problem.sections),
        ("room_ids", problem.rooms),
        ("slot_ids", problem.slots),
    ]:
        if not set(getattr(config, key)) <= available.keys():
            raise HTTPException(422, f"{key} contains records outside this timetable's scope")
    job = m.GenerationJob(
        timetable_id=timetable.id, created_by=user.id, configuration=config.model_dump()
    )
    db.add(job)
    timetable.status = "GENERATING"
    db.flush()
    create_audit_log(db, user, "generation_requested", "job", job.id, config.model_dump())
    db.commit()  # Workers must see the durable request before enqueueing.
    if settings().jobs_eager:
        tasks.add_task(run_generation, job.id)
    else:
        try:
            generate.apply_async(args=[job.id], task_id=f"timeforge-{job.id}", retry=False)
        except Exception:
            job.status, job.stage, job.error_message = (
                "FAILED",
                "Queue unavailable",
                "The job queue is unavailable. Restore Redis and retry this job.",
            )
            timetable.status = "GENERATED" if timetable.current_version_id else "DRAFT"
            db.commit()
    return serialize(job)


@router.get("/jobs/{job_id}")
def job_detail(
    job_id: int, user: m.User = Depends(require_permission("manage")), db: Session = Depends(get_db)
):
    job = db.get(m.GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    timetable_access(db, job.timetable_id, user)
    return serialize(job)


@router.post("/jobs/{job_id}/cancel")
def cancel(
    job_id: int, user: m.User = Depends(require_permission("manage")), db: Session = Depends(get_db)
):
    job = db.get(m.GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    timetable = timetable_access(db, job.timetable_id, user, True, True)
    if job.status not in {"QUEUED", "RUNNING"}:
        raise HTTPException(409, "This job has already finished")
    job.cancel_requested = True
    if job.status == "QUEUED":
        job.status, job.stage, job.completed_at = "CANCELLED", "Cancelled", utcnow()
        timetable.status = "GENERATED" if timetable.current_version_id else "DRAFT"
    create_audit_log(db, user, "generation_cancelled", "job", job.id)
    return serialize(job)


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry(
    job_id: int,
    tasks: BackgroundTasks,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    job = db.get(m.GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    if job.status == "RUNNING" and job.updated_at < utcnow() - timedelta(minutes=10):
        job.status = "FAILED"
        t = timetable_access(db, job.timetable_id, user, True, True)
        t.status = "GENERATED" if t.current_version_id else "DRAFT"
    if job.status not in {"FAILED", "CANCELLED"}:
        raise HTTPException(409, "Only failed, cancelled, or stale jobs can be retried")
    return start(job.timetable_id, GenerationIn.model_validate(job.configuration), tasks, user, db)


@router.get("/versions/{version_id}")
def version_detail(
    version_id: int, user: m.User = Depends(require_auth), db: Session = Depends(get_db)
):
    _, version = version_access(db, version_id, user)
    sessions = personal_filter(db, assignments(db, version_id), user)
    return {
        **serialize(version),
        "sessions": [a.model_dump() for a in sessions],
        "violations": (
            [
                serialize(v)
                for v in db.scalars(
                    select(m.ConstraintViolation).where(
                        m.ConstraintViolation.version_id == version_id
                    )
                )
            ]
            if user.role in MANAGERS
            else []
        ),
    }


@router.post("/versions/{version_id}/validate")
def validate(
    version_id: int,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    timetable, version = version_access(db, version_id, user, True)
    p = load_problem(db, timetable, version.configuration)
    sessions = assignments(db, version_id)
    violations = validate_solution(p, sessions) + score_solution(p, sessions)
    return {
        "valid": not any(v.severity == "hard" for v in violations),
        "violations": [v.json() for v in violations],
        "metrics": metrics(p, sessions, violations),
    }


@router.post("/timetables/{timetable_id}/preview")
def preview(
    timetable_id: int,
    data: EditIn,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    timetable = timetable_access(db, timetable_id, user, True)
    _, base = version_access(db, data.base_version_id, user, True)
    if base.timetable_id != timetable.id:
        raise HTTPException(422, "Base version belongs to another timetable")
    p = load_problem(
        db, timetable, base.configuration, [a for a in assignments(db, base.id) if a.is_locked]
    )
    violations = validate_solution(p, data.sessions) + score_solution(p, data.sessions)
    # Return actual compatible placements for affected sessions, bounded for interactive use.
    suggestions = []
    affected = {k for v in violations if v.severity == "hard" for k in v.related_sessions}

    for a in data.sessions:
        if (
            f"{a.section_id}:{a.session_number}" not in affected
            or a.section_id not in p.sections
            or a.is_locked
        ):
            continue
        for slot in sorted(p.slots.values(), key=lambda x: (x.day, x.start)):
            for room in p.rooms.values():
                if slot.start + p.sections[a.section_id].minutes_per_session > 1440:
                    continue
                candidate = a.model_copy(
                    update={
                        "day": slot.day,
                        "start": slot.start,
                        "end": slot.start + p.sections[a.section_id].minutes_per_session,
                        "room_id": room.id,
                    }
                )
                revised = [candidate if x is a else x for x in data.sessions]
                if not validate_solution(p, revised):
                    suggestions.append(candidate.model_dump())
                    break
            if len(suggestions) >= 5:
                break
        if len(suggestions) >= 5:
            break
    return {
        "valid": not any(v.severity == "hard" for v in violations),
        "violations": [v.json() for v in violations],
        "suggestions": suggestions,
    }


@router.post("/timetables/{timetable_id}/edit", status_code=201)
def edit(
    timetable_id: int,
    data: EditIn,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    timetable = timetable_access(db, timetable_id, user, True, True)
    if timetable.status in {"GENERATING", "UNDER_REVIEW", "APPROVED", "ARCHIVED"}:
        raise HTTPException(409, "Editing is unavailable in this workflow state")
    if timetable.current_version_id != data.base_version_id:
        raise HTTPException(409, "A newer active version exists. Reload before saving your edits.")
    base = db.get(m.TimetableVersion, data.base_version_id)
    if not base:
        raise HTTPException(404, "Base version not found")
    p = load_problem(
        db, timetable, base.configuration, [a for a in assignments(db, base.id) if a.is_locked]
    )
    version = persist_version(
        db,
        timetable,
        data.sessions,
        p,
        base.configuration,
        allow_conflicts=data.allow_draft_conflicts,
    )
    timetable.current_version_id, timetable.status = version.id, version.status
    create_audit_log(
        db,
        user,
        "edit_version",
        "timetable",
        timetable.id,
        {
            "base": base.id,
            "new_version": version.id,
            "locked_sessions": [
                f"{a.section_id}:{a.session_number}" for a in data.sessions if a.is_locked
            ],
        },
    )
    notify(db, timetable, f"Schedule changed: {timetable.name}, version {version.version_number}.")
    return serialize(version)


@router.post("/timetables/{timetable_id}/select")
def select_version(
    timetable_id: int,
    data: SelectIn,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    timetable = timetable_access(db, timetable_id, user, True, True)
    if timetable.status in {"GENERATING", "UNDER_REVIEW", "APPROVED", "ARCHIVED"}:
        raise HTTPException(409, "Selecting versions is unavailable in this workflow state")
    _, version = version_access(db, data.version_id, user, True)
    if version.timetable_id != timetable.id:
        raise HTTPException(422, "Version belongs to another timetable")
    timetable.current_version_id, timetable.status = version.id, "GENERATED"
    create_audit_log(db, user, "select_version", "timetable", timetable.id, {"version": version.id})
    return serialize(timetable)


@router.post("/timetables/{timetable_id}/workflow")
def workflow(
    timetable_id: int,
    data: DecisionIn,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    timetable = timetable_access(db, timetable_id, user, True, True)
    return transition(db, timetable, user, data.action, data.notes)


@router.get("/timetables/{timetable_id}/compare")
def compare(
    timetable_id: int,
    user: m.User = Depends(require_permission("manage")),
    db: Session = Depends(get_db),
):
    timetable_access(db, timetable_id, user)
    versions = list(
        db.scalars(
            select(m.TimetableVersion)
            .where(m.TimetableVersion.timetable_id == timetable_id)
            .order_by(m.TimetableVersion.version_number.desc())
            .limit(30)
        )
    )
    fingerprints = {
        v.id: {
            (a.section_id, a.session_number, a.day, a.start, a.room_id)
            for a in assignments(db, v.id)
        }
        for v in versions
    }
    return {
        "versions": [serialize(v) for v in versions],
        "differences": [
            {"a": a.id, "b": b.id, "changed_sessions": len(fingerprints[a.id] - fingerprints[b.id])}
            for i, a in enumerate(versions)
            for b in versions[i + 1 :]
        ],
    }


@router.get("/versions/{version_id}/analytics")
def analytics(version_id: int, user: m.User = Depends(require_auth), db: Session = Depends(get_db)):
    t, v = version_access(db, version_id, user)
    p = load_problem(db, t, v.configuration)
    sessions = personal_filter(db, assignments(db, v.id), user)
    violations = score_solution(p, sessions)
    return metrics(p, sessions, violations)
