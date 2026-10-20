from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models as m
from app.db import get_db
from app.domain import load_problem, validate_solution
from app.reference import can_write, save_record
from app.schemas import AvailabilityIn, Input
from app.security import create_audit_log, require_auth
from app.timetable_service import assignments, notify

router = APIRouter(prefix="/api/availability", tags=["Availability"])


class BulkIn(Input):
    records: list[AvailabilityIn] = Field(min_length=1, max_length=500)


@router.post("/bulk")
def bulk(data: BulkIn, user: m.User = Depends(require_auth), db: Session = Depends(get_db)):
    can_write("availability", user)
    # Validate every row before replacing anything; the request is one transaction.
    from app.reference import validate_references

    for record in data.records:
        validate_references(db, "availability", record.model_dump(), user)
    seen = set()
    for record in data.records:
        owner = next(
            k for k in ["lecturer_id", "room_id", "group_id", "section_id"] if getattr(record, k)
        )
        marker = (record.term_id, owner, getattr(record, owner), record.slot_id)
        if marker in seen:
            raise HTTPException(422, "The same period and resource appear more than once")
        seen.add(marker)
        db.execute(
            delete(m.Availability).where(
                m.Availability.term_id == record.term_id,
                getattr(m.Availability, owner) == getattr(record, owner),
                m.Availability.slot_id == record.slot_id,
            )
        )
        save_record(db, "availability", record.model_dump(), user)
    for department, term in {(r.department_id, r.term_id) for r in data.records}:
        for timetable in db.scalars(
            select(m.Timetable).where(
                m.Timetable.department_id == department,
                m.Timetable.term_id == term,
                m.Timetable.status != "ARCHIVED",
            )
        ):
            if timetable.current_version_id:
                p = load_problem(db, timetable)
                conflicts = validate_solution(p, assignments(db, timetable.current_version_id))
                if conflicts:
                    notify(
                        db,
                        timetable,
                        f"Availability changed: {len(conflicts)} hard conflicts require review in {timetable.name}.",
                    )
    create_audit_log(
        db,
        user,
        "availability_bulk",
        "availability",
        "batch",
        {"records": len(data.records)},
    )
    return {"saved": len(data.records)}
