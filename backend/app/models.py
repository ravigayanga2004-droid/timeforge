"""Relational domain model. JSON uses JSONB on PostgreSQL, JSON in test SQLite."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Record

J = JSON().with_variant(JSONB, "postgresql")


class University(Record, Base):
    __tablename__ = "universities"
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    address: Mapped[str] = mapped_column(String(500), default="")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Colombo")
    is_active: Mapped[bool] = mapped_column(default=True)


class Department(Record, Base):
    __tablename__ = "departments"
    university_id: Mapped[int | None] = mapped_column(ForeignKey("universities.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    head: Mapped[str] = mapped_column(String(160), default="")
    is_active: Mapped[bool] = mapped_column(default=True)


class Role(Record, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(30), unique=True)


class Permission(Record, Base):
    __tablename__ = "permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(60))
    __table_args__ = (UniqueConstraint("role_id", "code"),)


class User(Record, Base):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(ForeignKey("roles.name"), default="viewer")
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("student_groups.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuthSession(Record, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class ResetToken(Record, Base):
    __tablename__ = "reset_tokens"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(default=False)


class LoginAttempt(Record, Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String(64), unique=True)
    failures: Mapped[int] = mapped_column(default=0)
    next_at: Mapped[datetime] = mapped_column(DateTime)


class AcademicYear(Record, Base):
    __tablename__ = "academic_years"
    name: Mapped[str] = mapped_column(String(40), unique=True)


class AcademicTerm(Record, Base):
    __tablename__ = "academic_terms"
    name: Mapped[str] = mapped_column(String(160))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"))
    semester: Mapped[int] = mapped_column(default=1)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="active")
    __table_args__ = (CheckConstraint("end_date >= start_date", name="dates"),)


class Building(Record, Base):
    __tablename__ = "buildings"
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    location: Mapped[str] = mapped_column(String(300), default="")


class RoomFeature(Record, Base):
    __tablename__ = "room_features"
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Room(Record, Base):
    __tablename__ = "rooms"
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    capacity: Mapped[int]
    room_type: Mapped[str] = mapped_column(String(40), default="lecture")
    floor: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (CheckConstraint("capacity > 0", name="capacity"),)


class RoomFeatureLink(Base):
    __tablename__ = "room_feature_links"
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    feature_id: Mapped[int] = mapped_column(ForeignKey("room_features.id"), primary_key=True)


class TimeSlot(Record, Base):
    __tablename__ = "time_slots"
    day: Mapped[int]
    start: Mapped[int]
    end: Mapped[int]
    period: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        UniqueConstraint("day", "start", "end"),
        CheckConstraint(
            "day >= 0 AND day <= 6 AND start >= 0 AND end <= 1440 AND end > start", name="interval"
        ),
    )


class Lecturer(Record, Base):
    __tablename__ = "lecturers"
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254))
    employee_number: Mapped[str] = mapped_column(String(40), unique=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    max_daily_hours: Mapped[int] = mapped_column(default=6)
    max_weekly_hours: Mapped[int] = mapped_column(default=24)


class StudentGroup(Record, Base):
    __tablename__ = "student_groups"
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(40), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    academic_year: Mapped[int] = mapped_column(default=1)
    size: Mapped[int]
    group_type: Mapped[str] = mapped_column(String(40), default="cohort")
    max_daily_hours: Mapped[int] = mapped_column(default=7)
    __table_args__ = (CheckConstraint("size > 0", name="size"),)


class Course(Record, Base):
    __tablename__ = "courses"
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    credits: Mapped[int] = mapped_column(default=3)
    course_type: Mapped[str] = mapped_column(String(30), default="core")
    is_active: Mapped[bool] = mapped_column(default=True)


class CourseSection(Record, Base):
    __tablename__ = "course_sections"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"))
    expected_enrollment: Mapped[int]
    sessions_per_week: Mapped[int] = mapped_column(default=2)
    minutes_per_session: Mapped[int] = mapped_column(default=60)
    required_room_type: Mapped[str] = mapped_column(String(40), default="lecture")
    required_features: Mapped[list[str]] = mapped_column(J, default=list)
    preferred_days: Mapped[list[int]] = mapped_column(J, default=list)
    fixed_day: Mapped[int | None]
    min_day_spacing: Mapped[int] = mapped_column(default=0)
    no_back_to_back: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(30), default="active")
    __table_args__ = (
        CheckConstraint(
            "sessions_per_week > 0 AND minutes_per_session > 0 AND expected_enrollment > 0",
            name="requirements",
        ),
    )


class CourseEnrollmentGroup(Base):
    __tablename__ = "course_enrollment_groups"
    section_id: Mapped[int] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(ForeignKey("student_groups.id"), primary_key=True)


class CourseRequirement(Record, Base):
    __tablename__ = "course_requirements"
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    configuration: Mapped[dict[str, Any]] = mapped_column(J, default=dict)


class SectionRequirement(Record, Base):
    __tablename__ = "section_requirements"
    section_id: Mapped[int] = mapped_column(ForeignKey("course_sections.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    configuration: Mapped[dict[str, Any]] = mapped_column(J, default=dict)


class CoursePreferredSlot(Base):
    __tablename__ = "course_preferred_slots"
    section_id: Mapped[int] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE"), primary_key=True
    )
    slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"), primary_key=True)


class CoursePreferredRoom(Base):
    __tablename__ = "course_preferred_rooms"
    section_id: Mapped[int] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE"), primary_key=True
    )
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), primary_key=True)


class Availability(Record, Base):
    __tablename__ = "availability"
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id"), index=True)
    lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("lecturers.id"))
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("student_groups.id"))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("course_sections.id"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"))
    kind: Mapped[str] = mapped_column(String(30), default="unavailable")
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN lecturer_id IS NULL THEN 0 ELSE 1 END + CASE WHEN room_id IS NULL THEN 0 ELSE 1 END + CASE WHEN group_id IS NULL THEN 0 ELSE 1 END + CASE WHEN section_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_owner",
        ),
    )


# Availability uses one table with enforced foreign keys and exactly one owner,
# rather than four duplicated tables; these names expose the domain vocabulary.
LecturerAvailability = Availability
StudentGroupAvailability = Availability


class ConstraintDefinition(Record, Base):
    __tablename__ = "constraint_definitions"
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id"))
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(500), default="")
    weight: Mapped[int] = mapped_column(default=10)
    is_hard: Mapped[bool] = mapped_column(default=False)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(J, default=dict)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("term_id", "department_id", "code"),)


class Timetable(Record, Base):
    __tablename__ = "timetables"
    name: Mapped[str] = mapped_column(String(160))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("timetable_versions.id", use_alter=True, name="fk_current_version")
    )
    published_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("timetable_versions.id", use_alter=True, name="fk_published_version")
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    revision: Mapped[int] = mapped_column(default=0)
    __mapper_args__ = {"version_id_col": revision}


class GenerationConfiguration(Record, Base):
    __tablename__ = "generation_configurations"
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    name: Mapped[str] = mapped_column(String(160))
    configuration: Mapped[dict[str, Any]] = mapped_column(J, default=dict)


class GenerationJob(Record, Base):
    __tablename__ = "generation_jobs"
    timetable_id: Mapped[int] = mapped_column(ForeignKey("timetables.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    progress: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(String(80), default="Queued")
    configuration: Mapped[dict[str, Any]] = mapped_column(J, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(String(2000))
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class TimetableVersion(Record, Base):
    __tablename__ = "timetable_versions"
    timetable_id: Mapped[int] = mapped_column(ForeignKey("timetables.id"), index=True)
    version_number: Mapped[int]
    generation_job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"))
    score: Mapped[int] = mapped_column(default=0)
    hard_violations: Mapped[int] = mapped_column(default=0)
    soft_violations: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    metrics: Mapped[dict[str, Any]] = mapped_column(J, default=dict)
    configuration: Mapped[dict[str, Any]] = mapped_column(J, default=dict)
    __table_args__ = (UniqueConstraint("timetable_id", "version_number"),)


class ScheduledSession(Record, Base):
    __tablename__ = "scheduled_sessions"
    version_id: Mapped[int] = mapped_column(
        ForeignKey("timetable_versions.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[int] = mapped_column(ForeignKey("course_sections.id"))
    session_number: Mapped[int]
    day: Mapped[int]
    start: Mapped[int]
    end: Mapped[int]
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"))
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(String(1000), default="")
    __table_args__ = (
        UniqueConstraint("version_id", "section_id", "session_number"),
        Index("ix_session_calendar", "version_id", "day", "start"),
    )


class SessionTimeSlot(Base):
    __tablename__ = "session_time_slots"
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"), primary_key=True)


class SessionRoom(Base):
    __tablename__ = "session_rooms"
    session_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), primary_key=True)


class ConstraintViolation(Record, Base):
    __tablename__ = "constraint_violations"
    version_id: Mapped[int] = mapped_column(
        ForeignKey("timetable_versions.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(1000))
    related_sessions: Mapped[list[str]] = mapped_column(J, default=list)
    penalty: Mapped[int] = mapped_column(default=0)
    suggestion: Mapped[str] = mapped_column(String(1000), default="")
    is_resolved: Mapped[bool] = mapped_column(default=False)


class GenerationResult(Record, Base):
    __tablename__ = "generation_results"
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("timetable_versions.id"), unique=True)
    solver_status: Mapped[str] = mapped_column(String(30))
    duration_seconds: Mapped[float]
    random_seed: Mapped[int]


class ScheduleApproval(Record, Base):
    __tablename__ = "schedule_approvals"
    timetable_id: Mapped[int] = mapped_column(ForeignKey("timetables.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("timetable_versions.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(String(2000), default="")


class Notification(Record, Base):
    __tablename__ = "notifications"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(1000))
    timetable_id: Mapped[int | None] = mapped_column(ForeignKey("timetables.id"))
    is_read: Mapped[bool] = mapped_column(default=False)


class AuditLog(Record, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(J, default=dict)


class ImportJob(Record, Base):
    __tablename__ = "import_jobs"
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    row_count: Mapped[int]
    errors: Mapped[list[dict[str, Any]]] = mapped_column(J, default=list)


class ExportJob(Record, Base):
    __tablename__ = "export_jobs"
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version_id: Mapped[int] = mapped_column(ForeignKey("timetable_versions.id"))
    format: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED")
