from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Id = Annotated[int, Field(gt=0)]
Name = Annotated[str, Field(min_length=1, max_length=160)]
Code = Annotated[str, Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9 _./-]+$")]
RoleName = Literal["admin", "coordinator", "lecturer", "student", "viewer"]
RoomType = Literal["lecture", "laboratory", "tutorial", "seminar", "computer_lab", "workshop"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DepartmentIn(Input):
    name: Name
    code: Code
    description: str = Field(default="", max_length=2000)
    head: str = Field(default="", max_length=160)
    is_active: bool = True


class YearIn(Input):
    name: Name


class TermIn(Input):
    name: Name
    department_id: Id
    academic_year_id: Id
    semester: int = Field(default=1, ge=1, le=4)
    start_date: date
    end_date: date
    status: Literal["active", "draft", "archived"] = "active"

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 730:
            raise ValueError("Term dates must be ordered and span at most two years")
        return self


class BuildingIn(Input):
    name: Name
    code: Code
    location: str = Field(default="", max_length=300)


class FeatureIn(Input):
    name: Name


class RoomIn(Input):
    name: Name
    code: Code
    building_id: Id
    department_id: Id
    capacity: int = Field(gt=0, le=20000)
    room_type: RoomType = "lecture"
    floor: int = Field(default=0, ge=-5, le=200)
    is_active: bool = True
    feature_ids: list[Id] = Field(default_factory=list, max_length=50)


class SlotIn(Input):
    day: int = Field(ge=0, le=6)
    start: int = Field(ge=0, le=1439)
    end: int = Field(ge=1, le=1440)
    period: int = Field(ge=1, le=48)
    is_active: bool = True

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("End time must follow start time")
        return self


class LecturerIn(Input):
    name: Name
    email: EmailStr
    employee_number: Code
    user_id: Id | None = None
    department_id: Id
    max_daily_hours: int = Field(default=6, ge=1, le=16)
    max_weekly_hours: int = Field(default=24, ge=1, le=80)


class GroupIn(Input):
    name: Name
    code: Code
    department_id: Id
    academic_year: int = Field(default=1, ge=1, le=10)
    size: int = Field(gt=0, le=20000)
    group_type: Literal["cohort", "elective", "tutorial"] = "cohort"
    max_daily_hours: int = Field(default=7, ge=1, le=16)


class CourseIn(Input):
    name: Name
    code: Code
    description: str = Field(default="", max_length=5000)
    department_id: Id
    credits: int = Field(default=3, ge=0, le=60)
    course_type: Literal["core", "elective", "practical"] = "core"
    is_active: bool = True


class SectionIn(Input):
    code: Code
    course_id: Id
    term_id: Id
    department_id: Id
    lecturer_id: Id
    expected_enrollment: int = Field(gt=0, le=20000)
    sessions_per_week: int = Field(default=2, ge=1, le=20)
    minutes_per_session: int = Field(default=60, ge=15, le=480)
    required_room_type: RoomType = "lecture"
    required_features: list[Name] = Field(default_factory=list, max_length=50)
    preferred_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list)
    fixed_day: int | None = Field(default=None, ge=0, le=6)
    min_day_spacing: int = Field(default=0, ge=0, le=6)
    no_back_to_back: bool = False
    status: Literal["active", "inactive"] = "active"
    group_ids: list[Id] = Field(min_length=1, max_length=100)
    preferred_room_ids: list[Id] = Field(default_factory=list, max_length=100)
    preferred_slot_ids: list[Id] = Field(default_factory=list, max_length=200)


class AvailabilityIn(Input):
    department_id: Id
    term_id: Id
    lecturer_id: Id | None = None
    room_id: Id | None = None
    group_id: Id | None = None
    section_id: Id | None = None
    slot_id: Id
    kind: Literal["available", "unavailable", "preferred", "discouraged"] = "unavailable"
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def owner(self):
        if (
            sum(
                x is not None
                for x in [self.lecturer_id, self.room_id, self.group_id, self.section_id]
            )
            != 1
        ):
            raise ValueError("Choose exactly one availability owner")
        return self


SOFT_CODES = [
    "preferred_time",
    "preferred_room",
    "preferred_day",
    "early",
    "late",
    "weekend",
    "compact",
    "spread",
    "room_changes",
    "consistent_time",
    "room_balance",
]


class ConstraintIn(Input):
    department_id: Id
    term_id: Id
    name: Name
    code: Literal[
        "preferred_time",
        "preferred_room",
        "preferred_day",
        "early",
        "late",
        "weekend",
        "compact",
        "spread",
        "room_changes",
        "consistent_time",
        "room_balance",
    ]
    description: str = Field(default="", max_length=500)
    weight: int = Field(default=10, ge=0, le=10000)
    is_hard: Literal[False] = False
    is_enabled: bool = True
    configuration: dict = Field(default_factory=dict)


class TimetableIn(Input):
    name: Name
    department_id: Id
    term_id: Id


class UserIn(Input):
    name: Name
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: RoleName = "viewer"
    department_id: Id | None = None
    group_id: Id | None = None
    is_active: bool = True


class UserUpdate(Input):
    name: Name
    role: RoleName
    department_id: Id | None = None
    group_id: Id | None = None
    is_active: bool = True


class LoginIn(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ResetRequest(Input):
    email: EmailStr


class ResetIn(Input):
    token: str = Field(min_length=30, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class GenerationIn(Input):
    alternatives: int = Field(default=3, ge=1, le=8)
    time_limit: int = Field(default=30, ge=1, le=120)
    random_seed: int = Field(default=42, ge=0, le=2147483647)
    optimize: bool = True
    respect_locked: bool = True
    section_ids: list[Id] = Field(default_factory=list, max_length=2000)
    room_ids: list[Id] = Field(default_factory=list, max_length=1000)
    slot_ids: list[Id] = Field(default_factory=list, max_length=500)


class Assignment(Input):
    section_id: Id
    session_number: int = Field(ge=1, le=20)
    day: int = Field(ge=0, le=6)
    start: int = Field(ge=0, le=1439)
    end: int = Field(ge=1, le=1440)
    room_id: Id
    lecturer_id: Id
    is_locked: bool = False
    notes: str = Field(default="", max_length=1000)


class EditIn(Input):
    base_version_id: Id
    sessions: list[Assignment] = Field(max_length=5000)
    allow_draft_conflicts: bool = False


class DecisionIn(Input):
    action: Literal["submit", "approve", "reject", "publish", "archive", "reopen"]
    notes: str = Field(default="", max_length=2000)


class SelectIn(Input):
    version_id: Id
