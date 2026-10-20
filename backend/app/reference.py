"""Validated reference-data services shared by CRUD and atomic CSV imports."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app.db import get_db
from app.security import MANAGERS, create_audit_log, require_auth, require_department_access

REGISTRY: dict[str, tuple[Any, Any]] = {
    "departments": (m.Department, s.DepartmentIn),
    "academic-years": (m.AcademicYear, s.YearIn),
    "terms": (m.AcademicTerm, s.TermIn),
    "buildings": (m.Building, s.BuildingIn),
    "room-features": (m.RoomFeature, s.FeatureIn),
    "rooms": (m.Room, s.RoomIn),
    "time-slots": (m.TimeSlot, s.SlotIn),
    "lecturers": (m.Lecturer, s.LecturerIn),
    "student-groups": (m.StudentGroup, s.GroupIn),
    "courses": (m.Course, s.CourseIn),
    "sections": (m.CourseSection, s.SectionIn),
    "availability": (m.Availability, s.AvailabilityIn),
    "constraints": (m.ConstraintDefinition, s.ConstraintIn),
}
GLOBAL = {"departments", "academic-years", "buildings", "room-features", "time-slots"}
ADMIN_WRITE = GLOBAL | {"rooms", "terms"}
router = APIRouter(prefix="/api/data", tags=["Academic data"])


def serialize(record):
    return {
        column.key: getattr(record, column.key) for column in inspect(record).mapper.column_attrs
    }


def definition(entity: str):
    if entity not in REGISTRY:
        raise HTTPException(404, "Unknown data collection")
    return REGISTRY[entity]


def scoped(query, model, user):
    if user.role != "admin" and hasattr(model, "department_id"):
        query = query.where(model.department_id == user.department_id)
    return query


def can_write(entity: str, user):
    if user.role not in MANAGERS and not (entity == "availability" and user.role == "lecturer"):
        raise HTTPException(403, "Your role cannot edit academic data")
    if entity in ADMIN_WRITE and user.role != "admin":
        raise HTTPException(403, "Only administrators can edit this collection")


def enrich(db, entity, row):
    result = serialize(row)
    if entity == "rooms":
        result["feature_ids"] = list(
            db.scalars(
                select(m.RoomFeatureLink.feature_id).where(m.RoomFeatureLink.room_id == row.id)
            )
        )
    if entity == "sections":
        result["group_ids"] = list(
            db.scalars(
                select(m.CourseEnrollmentGroup.group_id).where(
                    m.CourseEnrollmentGroup.section_id == row.id
                )
            )
        )
        result["preferred_room_ids"] = list(
            db.scalars(
                select(m.CoursePreferredRoom.room_id).where(
                    m.CoursePreferredRoom.section_id == row.id
                )
            )
        )
        result["preferred_slot_ids"] = list(
            db.scalars(
                select(m.CoursePreferredSlot.slot_id).where(
                    m.CoursePreferredSlot.section_id == row.id
                )
            )
        )
    return result


def validate_references(db: Session, entity: str, data: dict, user):
    if "department_id" in data:
        require_department_access(user, data["department_id"])
        dep = db.get(m.Department, data["department_id"])
        if not dep or not dep.is_active:
            raise HTTPException(422, "Choose an active department")
    model, _ = definition(entity)
    for column in model.__table__.columns:
        if column.key not in data or data[column.key] is None:
            continue
        for fk in column.foreign_keys:
            target = next(
                (
                    cls.class_
                    for cls in m.Base.registry.mappers
                    if getattr(cls.local_table, "name", None) == fk.column.table.name
                ),
                None,
            )
            record = db.get(target, data[column.key]) if target else None
            if not record:
                raise HTTPException(422, f"{column.key}: referenced record does not exist")
            if hasattr(record, "department_id") and record.department_id is not None:
                require_department_access(user, record.department_id)
                if "department_id" in data and record.department_id != data["department_id"]:
                    raise HTTPException(422, f"{column.key}: record belongs to another department")
    links = {
        "group_ids": m.StudentGroup,
        "preferred_room_ids": m.Room,
        "preferred_slot_ids": m.TimeSlot,
        "feature_ids": m.RoomFeature,
    }
    for key, target in links.items():
        for value in set(data.get(key, [])):
            record = db.get(target, value)
            if not record:
                raise HTTPException(422, f"{key}: referenced record does not exist")
            if hasattr(record, "department_id") and record.department_id != data.get(
                "department_id"
            ):
                raise HTTPException(422, f"{key}: record belongs to another department")
    if entity == "lecturers" and data.get("user_id"):
        linked = db.get(m.User, data["user_id"])
        if not linked or linked.role != "lecturer":
            raise HTTPException(422, "Linked user must have the lecturer role")
    if entity == "availability":
        if user.role == "lecturer":
            owner = db.get(m.Lecturer, data.get("lecturer_id")) if data.get("lecturer_id") else None
            if not owner or owner.user_id != user.id:
                raise HTTPException(403, "Lecturers can change only their own availability")
        if data.get("section_id"):
            section = db.get(m.CourseSection, data["section_id"])
            if not section or section.term_id != data["term_id"]:
                raise HTTPException(422, "Section belongs to a different term")
    if entity == "time-slots" and data["is_active"]:
        overlaps = db.scalar(
            select(m.TimeSlot).where(
                m.TimeSlot.day == data["day"],
                m.TimeSlot.start < data["end"],
                m.TimeSlot.end > data["start"],
                m.TimeSlot.is_active.is_(True),
            )
        )
        if overlaps and overlaps.id != data.get("_id"):
            raise HTTPException(422, "Active time slots cannot overlap")


def save_record(db: Session, entity: str, raw: dict, user, record=None):
    can_write(entity, user)
    model, schema = definition(entity)
    try:
        data = schema.model_validate(raw).model_dump(mode="json")
        # Dates remain Python dates for SQLAlchemy.
        data = schema.model_validate(raw).model_dump()
    except ValidationError as exc:
        raise HTTPException(
            422, [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        ) from exc
    if record:
        if hasattr(record, "department_id"):
            require_department_access(user, record.department_id)
        if entity == "availability" and user.role == "lecturer":
            previous = db.get(m.Lecturer, record.lecturer_id) if record.lecturer_id else None
            if not previous or previous.user_id != user.id:
                raise HTTPException(403, "Cannot change another owner's availability")
    validate_references(db, entity, {**data, "_id": record.id if record else None}, user)
    before = enrich(db, entity, record) if record else {}
    links = {}
    for key in ["group_ids", "feature_ids", "preferred_room_ids", "preferred_slot_ids"]:
        if key in data:
            links[key] = data.pop(key)
    if entity in {"availability", "constraints"}:
        data["created_by"] = user.id
    if record is None:
        record = model(**data)
        db.add(record)
    else:
        for key, value in data.items():
            setattr(record, key, value)
    db.flush()
    link_specs = {
        "feature_ids": (m.RoomFeatureLink, "room_id", "feature_id"),
        "group_ids": (m.CourseEnrollmentGroup, "section_id", "group_id"),
        "preferred_room_ids": (m.CoursePreferredRoom, "section_id", "room_id"),
        "preferred_slot_ids": (m.CoursePreferredSlot, "section_id", "slot_id"),
    }
    for key, ids in links.items():
        table, owner, target = link_specs[key]
        db.execute(delete(table).where(getattr(table, owner) == record.id))
        db.add_all(table(**{owner: record.id, target: value}) for value in set(ids))
    db.flush()
    after = enrich(db, entity, record)
    # Use JSON-safe values, excluding authentication fields by construction.
    from fastapi.encoders import jsonable_encoder

    create_audit_log(
        db,
        user,
        "update" if before else "create",
        entity,
        record.id,
        jsonable_encoder({"before": before, "after": after}),
    )
    return after


@router.get("/schema")
def schemas(user: m.User = Depends(require_auth)):
    return {
        name: {
            "schema": schema.model_json_schema(),
            "writable": (
                user.role in MANAGERS and (name not in ADMIN_WRITE or user.role == "admin")
            )
            or (name == "availability" and user.role == "lecturer"),
        }
        for name, (_, schema) in REGISTRY.items()
    }


@router.get("/{entity}")
def listing(
    entity: str,
    q: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    sort: str = "id",
    department_id: int | None = None,
    term_id: int | None = None,
    user: m.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    model, _ = definition(entity)
    query = scoped(select(model), model, user)
    if entity == "departments" and user.role != "admin":
        query = query.where(m.Department.id == user.department_id)
    for key, value in [("department_id", department_id), ("term_id", term_id)]:
        if value is not None and hasattr(model, key):
            query = query.where(getattr(model, key) == value)
    if q and hasattr(model, "name"):
        query = query.where(model.name.ilike(f"%{q}%"))
    if entity == "availability" and user.role == "lecturer":
        query = query.where(
            m.Availability.lecturer_id.in_(
                select(m.Lecturer.id).where(m.Lecturer.user_id == user.id)
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = getattr(model, sort.removeprefix("-"), None)
    if order is None or sort.removeprefix("-") not in model.__table__.columns:
        raise HTTPException(422, "Unknown sort field")
    rows = db.scalars(
        query.order_by(order.desc() if sort.startswith("-") else order).offset(offset).limit(limit)
    )
    return {
        "items": [enrich(db, entity, row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/{entity}", status_code=201)
def create(
    entity: str, data: dict, user: m.User = Depends(require_auth), db: Session = Depends(get_db)
):
    return save_record(db, entity, data, user)


@router.put("/{entity}/{record_id}")
def update(
    entity: str,
    record_id: int,
    data: dict,
    user: m.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    model, _ = definition(entity)
    record = db.get(model, record_id)
    if not record:
        raise HTTPException(404, "Record not found")
    return save_record(db, entity, data, user, record)


@router.delete("/{entity}/{record_id}")
def remove(
    entity: str, record_id: int, user: m.User = Depends(require_auth), db: Session = Depends(get_db)
):
    can_write(entity, user)
    model, _ = definition(entity)
    record = db.get(model, record_id)
    if not record:
        raise HTTPException(404, "Record not found")
    if hasattr(record, "department_id"):
        require_department_access(user, record.department_id)
    if entity == "availability" and user.role == "lecturer":
        lecturer = db.get(m.Lecturer, record.lecturer_id) if record.lecturer_id else None
        if not lecturer or lecturer.user_id != user.id:
            raise HTTPException(403, "Cannot remove another owner's availability")
    if hasattr(record, "is_active"):
        record.is_active = False
    elif hasattr(record, "status"):
        record.status = "archived" if entity == "terms" else "inactive"
    else:
        db.delete(record)
    create_audit_log(db, user, "archive_or_delete", entity, record_id)
    return {"message": "Record archived or removed"}
