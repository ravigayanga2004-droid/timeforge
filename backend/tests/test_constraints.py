from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app import models as m
from app.domain import (
    DEFAULT_WEIGHTS,
    HARD_CONSTRAINTS,
    Problem,
    covers_periods,
    overlap,
    score_solution,
    validate_solution,
)
from app.schemas import Assignment, GenerationIn
from app.solver import Cancelled, Scheduler, SchedulingError


def problem():
    term = m.AcademicTerm(
        id=1,
        name="Term",
        department_id=1,
        start_date=date(2026, 10, 19),
        end_date=date(2026, 12, 18),
    )
    sections = {
        i: m.CourseSection(
            id=i,
            code=f"CS{i}",
            term_id=1,
            lecturer_id=1,
            expected_enrollment=30,
            sessions_per_week=1,
            minutes_per_session=60,
            required_room_type="lecture",
            required_features=["Projector"],
            preferred_days=[],
            fixed_day=None,
            min_day_spacing=0,
            no_back_to_back=False,
        )
        for i in [1, 2]
    }
    rooms = {
        i: m.Room(id=i, name=f"Room {i}", capacity=60, room_type="lecture", is_active=True)
        for i in [1, 2]
    }
    lecturers = {1: m.Lecturer(id=1, max_daily_hours=3, max_weekly_hours=8)}
    groups = {1: m.StudentGroup(id=1, size=30, max_daily_hours=3)}
    slots = {
        d * 3
        + i
        + 1: m.TimeSlot(
            id=d * 3 + i + 1, day=d, start=(9 + i) * 60, end=(10 + i) * 60, is_active=True
        )
        for d in range(2)
        for i in range(3)
    }
    return Problem(
        term,
        sections,
        rooms,
        lecturers,
        groups,
        slots,
        {1: {1}, 2: {1}},
        {1: {"Projector"}, 2: {"Projector"}},
        [],
        {},
        {},
        dict(DEFAULT_WEIGHTS),
    )


def assignments():
    return [
        Assignment(
            section_id=i,
            session_number=1,
            day=0,
            start=(8 + i) * 60,
            end=(9 + i) * 60,
            room_id=1,
            lecturer_id=1,
        )
        for i in [1, 2]
    ]


@pytest.mark.parametrize("code", list(HARD_CONSTRAINTS))
def test_every_hard_constraint_has_independent_detection(code):
    p = problem()
    sessions = assignments()
    if code in {"HC001", "HC002", "HC003"}:
        sessions[1] = sessions[1].model_copy(update={"start": 540, "end": 600})
    elif code == "HC004":
        p.rooms[1].is_active = False
    elif code == "HC005":
        p.rooms[1].capacity = 20
    elif code == "HC006":
        p.rooms[1].room_type = "laboratory"
    elif code == "HC007":
        p.features[1] = set()
    elif code in {"HC008", "HC009", "HC010", "HC020"}:
        owner = {
            "HC008": "lecturer_id",
            "HC009": "group_id",
            "HC010": "room_id",
            "HC020": "section_id",
        }[code]
        p.availability = [
            m.Availability(slot_id=1, kind="unavailable", reason="Blocked", **{owner: 1})
        ]
    elif code == "HC011":
        sessions = sessions[:1]
    elif code == "HC012":
        sessions[0] = sessions[0].model_copy(update={"end": 570})
    elif code == "HC013":
        sessions[0] = sessions[0].model_copy(update={"lecturer_id": 999})
    elif code == "HC014":
        p.enrollment[1] = set()
    elif code == "HC015":
        sessions[0] = sessions[0].model_copy(update={"room_id": 999})
    elif code == "HC016":
        p.sections[1].fixed_day = 2
    elif code == "HC017":
        p.locks = [sessions[0].model_copy(update={"day": 1})]
    elif code == "HC018":
        sessions.append(sessions[0])
    elif code == "HC019":
        p.lecturers[1].max_daily_hours = 1
    assert code in {v.code for v in validate_solution(p, sessions)}


def test_adjacent_intervals_do_not_overlap_and_duration_spans_periods():
    p = problem()
    a, b = assignments()
    assert not overlap(a, b)
    assert covers_periods(p, a.model_copy(update={"end": 660}))
    p.slots.pop(2)
    assert not covers_periods(p, a.model_copy(update={"end": 660}))


@given(st.integers(min_value=0, max_value=100000), st.integers(min_value=30, max_value=100))
@settings(max_examples=15, deadline=None)
def test_solver_solutions_always_validate_and_remain_repeatable(seed, capacity):
    p = problem()
    for room in p.rooms.values():
        room.capacity = capacity
    results = Scheduler(p, GenerationIn(alternatives=2, time_limit=2, random_seed=seed)).solve()
    assert results
    fingerprints = []
    for result in results:
        assert validate_solution(p, result["sessions"]) == []
        assert validate_solution(p, result["sessions"]) == []
        fingerprints.append(
            tuple((a.section_id, a.day, a.start, a.room_id) for a in result["sessions"])
        )
    assert len(set(fingerprints)) == len(results)


def test_solver_preserves_locked_sessions():
    p = problem()
    p.locks = [assignments()[0].model_copy(update={"is_locked": True})]
    for result in Scheduler(p, GenerationIn(alternatives=3, time_limit=3)).solve():
        a = result["sessions"][0]
        assert (a.day, a.start, a.room_id, a.is_locked) == (0, 540, 1, True)


def test_infeasible_capacity_is_explained():
    p = problem()
    for room in p.rooms.values():
        room.capacity = 10
    with pytest.raises(SchedulingError, match="No valid assignment"):
        Scheduler(p, GenerationIn()).solve()


def test_cancelled_generation_never_returns_partial_results():
    with pytest.raises(Cancelled):
        Scheduler(problem(), GenerationIn()).solve(cancelled=lambda: True)


def test_soft_weights_are_disabled_and_explained():
    p = problem()
    p.sections[1].preferred_days = [1]
    p.preferred_rooms[1] = {2}
    penalties = score_solution(p, assignments())
    assert any(v.code == "preferred_day" and v.penalty == 5 for v in penalties)
    assert any(v.code == "preferred_room" and v.penalty == 8 for v in penalties)
    p.weights = {k: 0 for k in p.weights}
    assert score_solution(p, assignments()) == []


def test_optimization_matches_independent_score_and_is_reproducible():
    p = problem()
    p.preferred_rooms[1] = {2}
    solver = Scheduler(p, GenerationIn(alternatives=1, time_limit=3))
    solver.build_model()
    from ortools.sat.python import cp_model

    cp = cp_model.CpSolver()
    cp.parameters.num_search_workers = 1
    assert cp.solve(solver.model) == cp_model.OPTIMAL
    result = solver.extract_solution(cp)
    assert cp.objective_value == sum(v.penalty for v in score_solution(p, result))
    a = Scheduler(p, GenerationIn(alternatives=2, time_limit=3)).solve()
    b = Scheduler(p, GenerationIn(alternatives=2, time_limit=3)).solve()
    assert [r["sessions"] for r in a] == [r["sessions"] for r in b]
