from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models as m
from app.auth import public_user
from app.db import get_db
from app.reference import serialize
from app.schemas import Input, UserIn, UserUpdate
from app.security import create_audit_log, hash_password, require_auth, require_permission

router = APIRouter(prefix="/api", tags=["Administration"])


@router.get("/users")
def users(
    user: m.User = Depends(require_permission("users")),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return {
        "items": [
            public_user(u)
            for u in db.scalars(select(m.User).order_by(m.User.id).offset(offset).limit(limit))
        ],
        "total": db.scalar(select(func.count(m.User.id))),
    }


def validate_user(db, data):
    if data.role != "admin" and data.department_id is None:
        raise HTTPException(422, "Non-administrator users need a department")
    if data.department_id and not db.get(m.Department, data.department_id):
        raise HTTPException(422, "Department does not exist")
    if data.group_id:
        group = db.get(m.StudentGroup, data.group_id)
        if not group or group.department_id != data.department_id:
            raise HTTPException(422, "Student group must belong to the user's department")


@router.post("/users", status_code=201)
def create_user(
    data: UserIn, user: m.User = Depends(require_permission("users")), db: Session = Depends(get_db)
):
    validate_user(db, data)
    values = data.model_dump(exclude={"password"})
    values["email"] = str(data.email).lower()
    record = m.User(**values, password_hash=hash_password(data.password))
    db.add(record)
    db.flush()
    create_audit_log(db, user, "user_created", "user", record.id, {"role": record.role})
    return public_user(record)


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    user: m.User = Depends(require_permission("users")),
    db: Session = Depends(get_db),
):
    record = db.get(m.User, user_id)
    if not record:
        raise HTTPException(404, "User not found")
    if record.id == user.id and (data.role != "admin" or not data.is_active):
        raise HTTPException(422, "You cannot disable or demote your own administrator account")
    validate_user(db, data)
    before = public_user(record)
    for key, value in data.model_dump().items():
        setattr(record, key, value)
    db.execute(delete(m.AuthSession).where(m.AuthSession.user_id == record.id))
    create_audit_log(
        db,
        user,
        "user_updated",
        "user",
        record.id,
        {"before": before, "after": public_user(record)},
    )
    return public_user(record)


@router.get("/audit")
def audit(
    user: m.User = Depends(require_permission("audit")),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    action: str = "",
):
    query = select(m.AuditLog)
    if action:
        query = query.where(m.AuditLog.action == action)
    return {
        "items": [
            serialize(a)
            for a in db.scalars(query.order_by(m.AuditLog.id.desc()).offset(offset).limit(limit))
        ],
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
    }


@router.get("/notifications")
def notifications(
    user: m.User = Depends(require_auth),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
):
    return {
        "items": [
            serialize(n)
            for n in db.scalars(
                select(m.Notification)
                .where(m.Notification.user_id == user.id)
                .order_by(m.Notification.id.desc())
                .offset(offset)
                .limit(100)
            )
        ]
    }


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int, user: m.User = Depends(require_auth), db: Session = Depends(get_db)
):
    n = db.get(m.Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    return {"message": "Marked as read"}


class IssueIn(Input):
    message: str


@router.post("/timetables/{timetable_id}/issues", status_code=201)
def report_issue(
    timetable_id: int,
    data: IssueIn,
    user: m.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    from app.timetable_service import notify, timetable_access

    t = timetable_access(db, timetable_id, user)
    if not data.message.strip() or len(data.message) > 2000:
        raise HTTPException(422, "Issue text must contain 1–2000 characters")
    notify(db, t, f"Issue reported by {user.name}: {data.message}")
    create_audit_log(db, user, "issue_reported", "timetable", t.id, {"message": data.message})
    return {"message": "Issue sent to your timetable coordinators"}
