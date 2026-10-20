"""Scheduling input snapshot and independent conflict/score analysis."""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from itertools import combinations
from typing import Any

from sqlalchemy import select

from app import models as m
from app.schemas import Assignment

HARD_CONSTRAINTS = {
    "HC001": "Lecturer overlap",
    "HC002": "Room overlap",
    "HC003": "Student-group overlap",
    "HC004": "Inactive room",
    "HC005": "Room capacity",
    "HC006": "Room type",
    "HC007": "Required equipment",
    "HC008": "Lecturer availability",
    "HC009": "Group availability",
    "HC010": "Room availability",
    "HC011": "Weekly session count",
    "HC012": "Duration and valid contiguous periods",
    "HC013": "Assigned lecturer",
    "HC014": "Enrolled student groups",
    "HC015": "Valid room",
    "HC016": "Term and fixed day",
    "HC017": "Locked assignment",
    "HC018": "Duplicate session",
    "HC019": "Daily and weekly workload",
    "HC020": "Section availability and spacing",
}
DEFAULT_WEIGHTS = {
    "preferred_time": 10,
    "preferred_room": 8,
    "preferred_day": 5,
    "early": 2,
    "late": 2,
    "weekend": 10,
    "compact": 1,
    "spread": 1,
    "room_changes": 3,
    "consistent_time": 2,
    "room_balance": 1,
}


@dataclass
class Violation:
    code: str
    severity: str
    description: str
    related_sessions: list[str] = field(default_factory=list)
    penalty: int = 0
    suggestion: str = "Choose another compatible room or time and validate again."

    def json(self):
        return asdict(self)


@dataclass
class Problem:
    term: m.AcademicTerm
    sections: dict[int, m.CourseSection]
    rooms: dict[int, m.Room]
    lecturers: dict[int, Any]
    groups: dict[int, Any]
    slots: dict[int, m.TimeSlot]
    enrollment: dict[int, set[int]]
    features: dict[int, set[str]]
    availability: list[m.Availability]
    preferred_rooms: dict[int, set[int]]
    preferred_slots: dict[int, set[int]]
    weights: dict[str, int]
    locks: list[Assignment] = field(default_factory=list)


def load_problem(db, timetable, configuration: dict | None = None, locks=None):
    config = configuration or {}
    sections = list(
        db.scalars(
            select(m.CourseSection).where(
                m.CourseSection.term_id == timetable.term_id,
                m.CourseSection.department_id == timetable.department_id,
                m.CourseSection.status == "active",
            )
        )
    )
    if config.get("section_ids"):
        sections = [x for x in sections if x.id in config["section_ids"]]
    rooms = list(db.scalars(select(m.Room).where(m.Room.department_id == timetable.department_id)))
    if config.get("room_ids"):
        rooms = [x for x in rooms if x.id in config["room_ids"]]
    slots = list(db.scalars(select(m.TimeSlot).where(m.TimeSlot.is_active.is_(True))))
    if config.get("slot_ids"):
        slots = [x for x in slots if x.id in config["slot_ids"]]
    enrollment: dict[int, set[int]] = defaultdict(set)
    for x in db.scalars(
        select(m.CourseEnrollmentGroup).where(
            m.CourseEnrollmentGroup.section_id.in_([s.id for s in sections])
        )
    ):
        enrollment[x.section_id].add(x.group_id)
    features: dict[int, set[str]] = defaultdict(set)
    for room_id, name in db.execute(
        select(m.RoomFeatureLink.room_id, m.RoomFeature.name).join(
            m.RoomFeature, m.RoomFeature.id == m.RoomFeatureLink.feature_id
        )
    ):
        features[room_id].add(name)
    pref_rooms: dict[int, set[int]] = defaultdict(set)
    pref_slots: dict[int, set[int]] = defaultdict(set)
    for x in db.scalars(select(m.CoursePreferredRoom)):
        pref_rooms[x.section_id].add(x.room_id)
    for x in db.scalars(select(m.CoursePreferredSlot)):
        pref_slots[x.section_id].add(x.slot_id)
    weights = dict(DEFAULT_WEIGHTS)
    for x in db.scalars(
        select(m.ConstraintDefinition).where(
            m.ConstraintDefinition.term_id == timetable.term_id,
            m.ConstraintDefinition.department_id == timetable.department_id,
        )
    ):
        weights[x.code] = x.weight if x.is_enabled else 0
    return Problem(
        term=db.get(m.AcademicTerm, timetable.term_id),
        sections={x.id: x for x in sections},
        rooms={x.id: x for x in rooms},
        lecturers={
            x.id: x
            for x in db.scalars(
                select(m.Lecturer).where(m.Lecturer.department_id == timetable.department_id)
            )
        },
        groups={
            x.id: x
            for x in db.scalars(
                select(m.StudentGroup).where(
                    m.StudentGroup.department_id == timetable.department_id
                )
            )
        },
        slots={x.id: x for x in slots},
        enrollment=dict(enrollment),
        features=dict(features),
        availability=list(
            db.scalars(
                select(m.Availability).where(
                    m.Availability.term_id == timetable.term_id,
                    m.Availability.department_id == timetable.department_id,
                )
            )
        ),
        preferred_rooms=dict(pref_rooms),
        preferred_slots=dict(pref_slots),
        weights=weights,
        locks=locks or [],
    )


def key(a: Assignment) -> str:
    return f"{a.section_id}:{a.session_number}"


def overlap(a, b) -> bool:
    return a.day == b.day and a.start < b.end and b.start < a.end


def covers_periods(p: Problem, a: Assignment) -> bool:
    cursor = a.start
    for slot in sorted(p.slots.values(), key=lambda x: x.start):
        if slot.day == a.day and slot.start == cursor and slot.end <= a.end:
            cursor = slot.end
    return cursor == a.end and a.end > a.start


def occurs_in_term(p: Problem, day: int) -> bool:
    first = p.term.start_date + timedelta(days=(day - p.term.start_date.weekday()) % 7)
    return first <= p.term.end_date


def relevant(p: Problem, rule, a: Assignment) -> bool:
    return (
        rule.lecturer_id == a.lecturer_id
        if rule.lecturer_id
        else (
            rule.room_id == a.room_id
            if rule.room_id
            else (
                rule.group_id in p.enrollment.get(a.section_id, set())
                if rule.group_id
                else rule.section_id == a.section_id
            )
        )
    )


def validate_solution(p: Problem, sessions: list[Assignment], check_counts=True) -> list[Violation]:
    result: list[Violation] = []

    def fail(code, text, affected):
        result.append(Violation(code, "hard", text, [key(x) for x in affected]))

    counts = Counter((x.section_id, x.session_number) for x in sessions)
    for a in sessions:
        section = p.sections.get(a.section_id)
        room = p.rooms.get(a.room_id)
        if not section:
            fail("HC011", "This session references a section outside the generation scope.", [a])
            continue
        if not room:
            fail("HC015", "This session has no permitted room.", [a])
        else:
            if not room.is_active:
                fail("HC004", "This room is inactive.", [a])
            enrollment_size = sum(
                p.groups[g].size for g in p.enrollment.get(section.id, set()) if g in p.groups
            )
            if room.capacity < max(section.expected_enrollment, enrollment_size):
                fail("HC005", "This room is too small for the selected student groups.", [a])
            if room.room_type != section.required_room_type:
                fail("HC006", "This room does not support the required session type.", [a])
            if not set(section.required_features) <= p.features.get(room.id, set()):
                fail("HC007", "This room lacks required equipment.", [a])
        if a.lecturer_id not in p.lecturers or a.lecturer_id != section.lecturer_id:
            fail("HC013", "The session must use its section's assigned lecturer.", [a])
        if not p.enrollment.get(section.id) or not p.enrollment[section.id] <= p.groups.keys():
            fail("HC014", "This section needs valid enrolled student groups.", [a])
        if a.end - a.start != section.minutes_per_session or not covers_periods(p, a):
            fail(
                "HC012",
                "Session duration must match the requirement and contiguous active periods.",
                [a],
            )
        if (
            not occurs_in_term(p, a.day)
            or section.term_id != p.term.id
            or (section.fixed_day is not None and section.fixed_day != a.day)
        ):
            fail("HC016", "The day is outside the term or violates the required weekday.", [a])
        if a.session_number > section.sessions_per_week:
            fail("HC011", "Session number exceeds the weekly requirement.", [a])
        if counts[(a.section_id, a.session_number)] > 1:
            fail("HC018", "Duplicate assignment for this section and session number.", [a])
        for rule in p.availability:
            slot = p.slots.get(rule.slot_id)
            if slot and rule.kind == "unavailable" and relevant(p, rule, a) and overlap(a, slot):
                code = (
                    "HC008"
                    if rule.lecturer_id
                    else "HC009" if rule.group_id else "HC010" if rule.room_id else "HC020"
                )
                fail(
                    code,
                    f"This {'lecturer' if rule.lecturer_id else 'student group' if rule.group_id else 'room' if rule.room_id else 'section'} is unavailable during the selected time. {rule.reason}",
                    [a],
                )
    for a, b in combinations(sessions, 2):
        if overlap(a, b):
            if a.lecturer_id == b.lecturer_id:
                fail("HC001", "This lecturer is already teaching another session.", [a, b])
            if a.room_id == b.room_id:
                fail("HC002", "This room is already occupied by another session.", [a, b])
            if p.enrollment.get(a.section_id, set()) & p.enrollment.get(b.section_id, set()):
                fail(
                    "HC003",
                    "This session overlaps with another session for the same student group.",
                    [a, b],
                )
        if a.section_id == b.section_id and a.section_id in p.sections:
            section = p.sections[a.section_id]
            if abs(a.day - b.day) < section.min_day_spacing or (
                section.no_back_to_back
                and a.day == b.day
                and (a.end == b.start or b.end == a.start)
            ):
                fail("HC020", "Sessions violate the section's required spacing.", [a, b])
    if check_counts:
        for section in p.sections.values():
            for number in range(1, section.sessions_per_week + 1):
                if counts[(section.id, number)] == 0:
                    fail("HC011", f"Section {section.code} is missing weekly session {number}.", [])
    for locked in p.locks:
        found = next((x for x in sessions if key(x) == key(locked)), None)
        if not found or any(
            getattr(found, f) != getattr(locked, f)
            for f in ["day", "start", "end", "room_id", "lecturer_id"]
        ):
            fail("HC017", "A locked session was moved or removed.", [locked])
    for entity, owners in [("lecturer", p.lecturers), ("group", p.groups)]:
        for owner in owners.values():
            own = [
                x
                for x in sessions
                if (
                    x.lecturer_id == owner.id
                    if entity == "lecturer"
                    else owner.id in p.enrollment.get(x.section_id, set())
                )
            ]
            daily: Counter[int] = Counter()
            for a in own:
                daily[a.day] += a.end - a.start
            if any(minutes > owner.max_daily_hours * 60 for minutes in daily.values()) or (
                entity == "lecturer" and sum(daily.values()) > owner.max_weekly_hours * 60
            ):
                fail(
                    "HC019",
                    f"The {entity}'s maximum daily or weekly teaching hours are exceeded.",
                    own,
                )
    return result


def candidate_penalties(p: Problem, a: Assignment) -> list[tuple[str, int, str]]:
    section = p.sections[a.section_id]
    penalties = []
    for code, condition, message in [
        (
            "preferred_room",
            bool(p.preferred_rooms.get(section.id))
            and a.room_id not in p.preferred_rooms[section.id],
            "A preferred room could not be used.",
        ),
        (
            "preferred_day",
            bool(section.preferred_days) and a.day not in section.preferred_days,
            "Session is outside the preferred weekdays.",
        ),
        (
            "preferred_time",
            bool(p.preferred_slots.get(section.id))
            and not any(
                p.slots[s].day == a.day and p.slots[s].start == a.start
                for s in p.preferred_slots[section.id]
                if s in p.slots
            ),
            "A preferred course time could not be used.",
        ),
        ("early", a.start < 9 * 60, "Session starts before 09:00."),
        ("late", a.end > 17 * 60, "Session ends after 17:00."),
        ("weekend", a.day >= 5, "Session is scheduled on a weekend."),
    ]:
        if condition and p.weights.get(code, 0):
            penalties.append((code, p.weights[code], message))
    preferred = [
        r
        for r in p.availability
        if r.kind == "preferred" and relevant(p, r, a) and r.slot_id in p.slots
    ]
    if preferred and not any(overlap(a, p.slots[r.slot_id]) for r in preferred):
        penalties.append(
            (
                "preferred_time",
                p.weights["preferred_time"],
                "Session is outside the resource's preferred times.",
            )
        )
    if any(
        r.kind == "discouraged"
        and relevant(p, r, a)
        and r.slot_id in p.slots
        and overlap(a, p.slots[r.slot_id])
        for r in p.availability
    ):
        penalties.append(
            (
                "preferred_time",
                p.weights["preferred_time"],
                "Session uses a discouraged resource time.",
            )
        )
    return penalties


def score_solution(p: Problem, sessions: list[Assignment]) -> list[Violation]:
    result = []

    def add(code, units, message, affected):
        penalty = int(units) * p.weights.get(code, 0)
        if penalty:
            result.append(
                Violation(
                    code,
                    "soft",
                    message,
                    [key(x) for x in affected],
                    penalty,
                    "Adjust preferences or move sessions and validate again.",
                )
            )

    for a in sessions:
        if a.section_id not in p.sections:
            continue
        for code, penalty, text in candidate_penalties(p, a):
            if penalty:
                result.append(Violation(code, "soft", text, [key(a)], penalty))
    for entity, owners in [("lecturer", p.lecturers), ("group", p.groups)]:
        for owner in owners:
            own = [
                a
                for a in sessions
                if (
                    a.lecturer_id == owner
                    if entity == "lecturer"
                    else owner in p.enrollment.get(a.section_id, set())
                )
            ]
            for day in range(7):
                day_sessions = [a for a in own if a.day == day]
                if day_sessions:
                    idle = max(
                        0,
                        max(a.end for a in day_sessions)
                        - min(a.start for a in day_sessions)
                        - sum(a.end - a.start for a in day_sessions),
                    )
                    add(
                        "compact",
                        idle,
                        f"{entity.title()} has {idle} idle minutes on day {day+1}.",
                        day_sessions,
                    )
                    add(
                        "spread",
                        len(day_sessions) ** 2,
                        f"Daily workload concentration: {len(day_sessions)} sessions for this {entity}.",
                        day_sessions,
                    )
    for a, b in combinations(sessions, 2):
        if a.section_id == b.section_id:
            add(
                "room_changes",
                a.room_id != b.room_id,
                "Sessions of the same section use different rooms.",
                [a, b],
            )
            add(
                "consistent_time",
                a.start != b.start,
                "Sessions of the same section start at different times.",
                [a, b],
            )
    if p.rooms:
        loads = Counter(a.room_id for a in sessions)
        imbalance = max(loads.get(r, 0) for r in p.rooms) - min(loads.get(r, 0) for r in p.rooms)
        add(
            "room_balance",
            imbalance,
            "Difference between the most and least used room session counts.",
            sessions,
        )
    return result
