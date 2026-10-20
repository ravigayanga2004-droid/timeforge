import secrets
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, utcnow
from app.models import AuthSession, LoginAttempt, ResetToken, User
from app.schemas import LoginIn, ResetIn, ResetRequest
from app.security import (
    DUMMY_HASH,
    create_audit_log,
    digest,
    hash_password,
    new_session,
    require_auth,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def public_user(user: User):
    return {
        k: getattr(user, k)
        for k in ["id", "name", "email", "role", "department_id", "group_id", "is_active"]
    }


def origin_check(request: Request):
    origin = request.headers.get("origin")
    if origin and origin != settings().allowed_origin:
        raise HTTPException(403, "Origin is not permitted")


def throttle(db: Session, key: str) -> LoginAttempt:
    attempt = db.scalar(
        select(LoginAttempt).where(LoginAttempt.key == digest(key)).with_for_update()
    )
    if attempt and attempt.next_at > utcnow():
        raise HTTPException(
            429,
            "Too many attempts. Please try again later.",
            headers={"Retry-After": str(max(1, int((attempt.next_at - utcnow()).total_seconds())))},
        )
    if not attempt:
        attempt = LoginAttempt(key=digest(key), next_at=utcnow(), failures=0)
        db.add(attempt)
        db.flush()
    return attempt


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    origin_check(request)
    ip = request.client.host if request.client else "unknown"
    attempt = throttle(db, f"login:{ip}:{str(data.email).lower()}")
    ip_attempt = throttle(db, f"login-ip:{ip}")
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not valid or not user or not user.is_active:
        for record in [attempt, ip_attempt]:
            record.failures += 1
            record.next_at = utcnow() + timedelta(seconds=min(900, 2 ** min(record.failures, 10)))
        db.commit()  # Persist throttling even though the HTTP transaction fails.
        raise HTTPException(401, "Email or password is incorrect")
    attempt.failures = 0
    ip_attempt.failures = 0
    token, csrf = new_session(db, user, settings().session_hours)
    user.last_login_at = utcnow()
    for name, value, http_only in [("tf_session", token, True), ("tf_csrf", csrf, False)]:
        response.set_cookie(
            name,
            value,
            httponly=http_only,
            secure=settings().cookie_secure,
            samesite="lax",
            max_age=settings().session_hours * 3600,
            path="/",
        )
    create_audit_log(db, user, "login", "user", user.id)
    return public_user(user)


@router.get("/me")
def me(user: User = Depends(require_auth)):
    return public_user(user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    db.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == digest(request.cookies.get("tf_session", ""))
        )
    )
    response.delete_cookie("tf_session")
    response.delete_cookie("tf_csrf")
    create_audit_log(db, user, "logout", "user", user.id)
    return {"message": "Signed out"}


@router.post("/forgot-password")
def forgot(data: ResetRequest, request: Request, db: Session = Depends(get_db)):
    origin_check(request)
    attempt = throttle(db, "reset:" + (request.client.host if request.client else "unknown"))
    attempt.next_at = utcnow() + timedelta(seconds=30)
    user = db.scalar(
        select(User).where(User.email == str(data.email).lower(), User.is_active.is_(True))
    )
    if user:
        token = secrets.token_urlsafe(48)
        db.execute(delete(ResetToken).where(ResetToken.user_id == user.id))
        db.add(
            ResetToken(
                user_id=user.id,
                token_hash=digest(token),
                expires_at=utcnow() + timedelta(minutes=30),
            )
        )
        # File delivery is an explicit local mail adapter; deploy an SMTP adapter before public use.
        directory: Path = settings().mail_directory
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"reset-{secrets.token_hex(12)}.txt"
        destination.write_text(
            f"To: {user.email}\nReset your TimeForge password (expires in 30 minutes):\n{settings().public_url}/?reset={token}\n",
            encoding="utf-8",
        )
        create_audit_log(db, user, "password_reset_requested", "user", user.id)
    return {"message": "If this account exists, password reset instructions have been sent."}


@router.post("/reset-password")
def reset(data: ResetIn, request: Request, db: Session = Depends(get_db)):
    origin_check(request)
    record = db.scalar(
        select(ResetToken).where(ResetToken.token_hash == digest(data.token)).with_for_update()
    )
    if not record or record.used or record.expires_at < utcnow():
        raise HTTPException(400, "The reset link is invalid or expired")
    user = db.get(User, record.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, "The reset link is invalid or expired")
    user.password_hash = hash_password(data.password)
    record.used = True
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    create_audit_log(db, user, "password_reset_completed", "user", user.id)
    return {"message": "Password changed. Please sign in."}
