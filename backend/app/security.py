import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.models import AuditLog, AuthSession, User

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
MANAGERS = {"admin", "coordinator"}
PERMISSIONS = {"manage": MANAGERS, "approve": {"admin"}, "users": {"admin"}, "audit": {"admin"}}


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("tf_session", "")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token)))
    if not session or session.expires_at < utcnow():
        raise HTTPException(401, "Please sign in to continue")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Session is no longer valid")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(digest(csrf), session.csrf_hash):
            raise HTTPException(403, "Invalid CSRF token; refresh and try again")
    request.state.user = user
    return user


def require_role(*roles: str):
    def dependency(user: User = Depends(require_auth)):
        if user.role not in roles:
            raise HTTPException(403, "Your role cannot perform this action")
        return user

    return dependency


def require_permission(permission: str):
    return require_role(*PERMISSIONS.get(permission, set()))


def require_department_access(user: User, department_id: int) -> None:
    if user.role != "admin" and user.department_id != department_id:
        raise HTTPException(403, "This record belongs to another department")


def create_audit_log(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str,
    details: dict | None = None,
):
    # Callers pass only explicitly selected, non-secret metadata.
    db.add(
        AuditLog(
            actor_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details or {},
        )
    )


def new_session(db: Session, user: User, hours: int):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=utcnow() + timedelta(hours=hours),
        )
    )
    return token, csrf
