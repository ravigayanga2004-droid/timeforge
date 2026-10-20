"""Durable job execution with idempotent result persistence and cooperative cancellation."""

from datetime import timedelta

from celery import Celery
from sqlalchemy import select

from app import models as m
from app.config import settings
from app.db import SessionLocal, utcnow
from app.domain import load_problem
from app.schemas import GenerationIn
from app.solver import Cancelled, Scheduler, SchedulingError
from app.timetable_service import assignments, notify, persist_version

celery = Celery("timeforge", broker=settings().redis_url, backend=settings().redis_url)
celery.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_expires=86400,
    broker_connection_retry_on_startup=True,
)


def cancel_requested(job_id):
    with SessionLocal() as db:
        job = db.get(m.GenerationJob, job_id)
        return not job or job.cancel_requested


def progress(job_id, stage, amount):
    with SessionLocal() as db:
        job = db.get(m.GenerationJob, job_id)
        if job and job.status == "RUNNING":
            job.stage, job.progress = stage, amount
            db.commit()


def run_generation(job_id: int):
    with SessionLocal() as db:
        job = db.scalar(
            select(m.GenerationJob).where(m.GenerationJob.id == job_id).with_for_update()
        )
        if not job or job.status != "QUEUED":
            return  # Re-delivery cannot create duplicate versions.
        job.status, job.started_at, job.stage, job.progress = (
            "RUNNING",
            utcnow(),
            "Validation",
            5,
        )
        db.commit()
    try:
        with SessionLocal() as db:
            job = db.get(m.GenerationJob, job_id)
            if not job:
                return
            timetable = db.get(m.Timetable, job.timetable_id)
            if not timetable:
                raise SchedulingError("Timetable was removed before generation")
            configuration = GenerationIn.model_validate(job.configuration)
            locks = (
                [a for a in assignments(db, timetable.current_version_id) if a.is_locked]
                if timetable.current_version_id and configuration.respect_locked
                else []
            )
            problem = load_problem(db, timetable, job.configuration, locks)
            if any(a.section_id not in problem.sections for a in locks):
                raise SchedulingError(
                    "The selected scope excludes a locked section; include it or explicitly disable locked-session preservation."
                )
            results = Scheduler(problem, configuration).solve(
                lambda: cancel_requested(job_id),
                lambda stage, amount: progress(job_id, stage, amount),
            )
            progress(job_id, "Validation", 85)
        # Re-read inputs before persistence: data may have changed while solving.
        with SessionLocal() as db:
            job = db.scalar(
                select(m.GenerationJob).where(m.GenerationJob.id == job_id).with_for_update()
            )
            if not job:
                return
            timetable = db.scalar(
                select(m.Timetable).where(m.Timetable.id == job.timetable_id).with_for_update()
            )
            if not timetable:
                raise SchedulingError("Timetable was removed before persistence")
            if job.cancel_requested:
                raise Cancelled("Generation cancelled")
            problem = load_problem(db, timetable, job.configuration, locks)
            job.stage, job.progress = "Persistence", 95
            versions = []
            for result in results:
                version = persist_version(
                    db,
                    timetable,
                    result["sessions"],
                    problem,
                    job.configuration,
                    job_id=job_id,
                )
                db.add(
                    m.GenerationResult(
                        job_id=job_id,
                        version_id=version.id,
                        solver_status=result["solver_status"],
                        duration_seconds=result["duration_seconds"],
                        random_seed=result["random_seed"],
                    )
                )
                versions.append(version)
            if not versions:
                raise SchedulingError("Time limit elapsed before a valid solution was available")
            timetable.current_version_id = min(versions, key=lambda x: x.score).id
            timetable.status = "GENERATED"
            job.status, job.progress, job.stage, job.completed_at = (
                "COMPLETED",
                100,
                "Completion",
                utcnow(),
            )
            notify(
                db,
                timetable,
                f"Generation completed: {len(versions)} valid alternatives for {timetable.name}.",
            )
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            job = db.get(m.GenerationJob, job_id)
            if not job:
                return
            timetable = db.get(m.Timetable, job.timetable_id)
            if not timetable:
                return
            job.status = "CANCELLED" if isinstance(exc, Cancelled) else "FAILED"
            job.stage = "Cancelled" if isinstance(exc, Cancelled) else "Failed"
            job.error_message = (
                str(exc)[:1800]
                if isinstance(exc, SchedulingError)
                else "Generation could not be completed. Validate scheduling data and retry; contact an administrator if this persists."
            )
            job.completed_at = utcnow()
            timetable.status = "GENERATED" if timetable.current_version_id else "DRAFT"
            notify(
                db,
                timetable,
                f"{timetable.name}: {job.stage.lower()}. {job.error_message}",
            )
            db.commit()


@celery.task(name="timeforge.generate")
def generate(job_id: int):
    run_generation(job_id)


@celery.task(name="timeforge.cleanup")
def cleanup():
    from sqlalchemy import delete

    with SessionLocal() as db:
        db.execute(delete(m.AuthSession).where(m.AuthSession.expires_at < utcnow()))
        db.execute(delete(m.ResetToken).where(m.ResetToken.expires_at < utcnow()))
        db.execute(
            delete(m.LoginAttempt).where(m.LoginAttempt.updated_at < utcnow() - timedelta(days=1))
        )
        db.commit()


celery.conf.beat_schedule = {
    "expired-auth-cleanup": {"task": "timeforge.cleanup", "schedule": 3600.0}
}
