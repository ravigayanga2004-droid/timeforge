"""CP-SAT scheduling service; API routes never build solver constraints."""

import threading
import time
from collections import defaultdict
from dataclasses import replace
from itertools import combinations
from math import ceil

from ortools.sat.python import cp_model

from app.domain import (
    Problem,
    candidate_penalties,
    occurs_in_term,
    score_solution,
    validate_solution,
)
from app.schemas import Assignment, GenerationIn


class SchedulingError(Exception):
    pass


class Cancelled(SchedulingError):
    pass


class Scheduler:
    def __init__(self, problem: Problem, configuration: GenerationIn):
        self.p = problem
        self.config = configuration
        self.model = cp_model.CpModel()
        self.candidates: dict[tuple[int, int], list[Assignment]] = {}
        self.variables: dict[tuple[int, int], list] = {}
        self.selected: dict[tuple[int, int], dict] = {}
        self.objective: list = []

    def build_model(self):
        if not self.p.sections:
            raise SchedulingError("No active course sections match the selected term and scope.")
        count = sum(s.sessions_per_week for s in self.p.sections.values())
        if count > 5000:
            raise SchedulingError(
                "This generation exceeds the 5,000-session safety limit; split by department or term."
            )
        check_problem = replace(self.p, locks=[])
        total_candidates = 0
        for section in self.p.sections.values():
            base = []
            for slot in self.p.slots.values():
                if not occurs_in_term(self.p, slot.day):
                    continue
                for room in self.p.rooms.values():
                    if slot.start + section.minutes_per_session > 1440:
                        continue
                    a = Assignment(
                        section_id=section.id,
                        session_number=1,
                        day=slot.day,
                        start=slot.start,
                        end=slot.start + section.minutes_per_session,
                        room_id=room.id,
                        lecturer_id=section.lecturer_id,
                    )
                    if a.end <= 1440 and not validate_solution(
                        check_problem, [a], check_counts=False
                    ):
                        base.append(a)
            for number in range(1, section.sessions_per_week + 1):
                session_key = (section.id, number)
                candidates = [a.model_copy(update={"session_number": number}) for a in base]
                locked = next(
                    (
                        x
                        for x in self.p.locks
                        if x.section_id == section.id and x.session_number == number
                    ),
                    None,
                )
                if locked:
                    candidates = [
                        a.model_copy(update={"is_locked": True, "notes": locked.notes})
                        for a in candidates
                        if all(
                            getattr(a, k) == getattr(locked, k)
                            for k in ["day", "start", "end", "room_id", "lecturer_id"]
                        )
                    ]
                if not candidates:
                    raise SchedulingError(
                        f"No valid assignment for {section.code}, session {number}. Check room capacity/type/equipment, availability, duration, groups and locked times."
                    )
                total_candidates += len(candidates)
                if total_candidates > 150000:
                    raise SchedulingError(
                        "More than 150,000 candidate assignments; narrow rooms or time slots before generating."
                    )
                self.candidates[session_key] = candidates
                variables = [
                    self.model.new_bool_var(f"s{section.id}_{number}_{i}")
                    for i in range(len(candidates))
                ]
                self.variables[session_key] = variables
                self.model.add_exactly_one(variables)
                selected = {}
                for field, bound in [
                    ("day", 6),
                    ("start", 1440),
                    ("end", 1440),
                    ("room_id", max(self.p.rooms)),
                    ("ordinal", 10080),
                ]:
                    v = self.model.new_int_var(0, bound, f"{session_key}_{field}")
                    self.model.add(
                        v
                        == sum(
                            x
                            * (a.day * 1440 + a.start if field == "ordinal" else getattr(a, field))
                            for a, x in zip(candidates, variables, strict=True)
                        )
                    )
                    selected[field] = v
                self.selected[session_key] = selected
        self.add_hard_constraints()
        self.add_soft_constraints()
        if self.config.optimize:
            self.model.minimize(sum(self.objective))
        return self.model

    def add_hard_constraints(self):
        resources = defaultdict(list)
        daily = defaultdict(list)
        weekly = defaultdict(list)
        for session_key, candidates in self.candidates.items():
            for a, x in zip(candidates, self.variables[session_key], strict=True):
                interval = self.model.new_optional_fixed_size_interval_var(
                    a.day * 1440 + a.start,
                    a.end - a.start,
                    x,
                    f"i{session_key}_{a.day}_{a.start}_{a.room_id}",
                )
                resource_keys = [("room", a.room_id), ("lecturer", a.lecturer_id)] + [
                    ("group", g) for g in self.p.enrollment[a.section_id]
                ]
                for resource in resource_keys:
                    resources[resource].append(interval)
                    if resource[0] != "room":
                        daily[(*resource, a.day)].append((a.end - a.start) * x)
                        weekly[resource].append((a.end - a.start) * x)
        for intervals in resources.values():
            self.model.add_no_overlap(intervals)
        for (entity, owner, _), terms in daily.items():
            record = self.p.lecturers[owner] if entity == "lecturer" else self.p.groups[owner]
            self.model.add(sum(terms) <= record.max_daily_hours * 60)
        for (entity, owner), terms in weekly.items():
            if entity == "lecturer":
                self.model.add(sum(terms) <= self.p.lecturers[owner].max_weekly_hours * 60)
        for section in self.p.sections.values():
            keys = [(section.id, n) for n in range(1, section.sessions_per_week + 1)]
            for ka, kb in combinations(keys, 2):
                sa, sb = self.selected[ka], self.selected[kb]
                # Canonical ordering prevents alternatives differing only by session labels.
                self.model.add(sa["ordinal"] < sb["ordinal"])
                if section.min_day_spacing:
                    self.model.add(sb["day"] - sa["day"] >= section.min_day_spacing)
                if section.no_back_to_back:
                    same = self.model.new_bool_var(f"same_day{ka}{kb}")
                    self.model.add(sa["day"] == sb["day"]).only_enforce_if(same)
                    self.model.add(sa["day"] != sb["day"]).only_enforce_if(same.Not())
                    self.model.add(sb["start"] != sa["end"]).only_enforce_if(same)

    def add_soft_constraints(self):
        for session_key, candidates in self.candidates.items():
            for a, x in zip(candidates, self.variables[session_key], strict=True):
                self.objective.append(sum(v for _, v, _ in candidate_penalties(self.p, a)) * x)
        for entity, owners in [("lecturer", self.p.lecturers), ("group", self.p.groups)]:
            for owner in owners:
                keys = [
                    k
                    for k in self.candidates
                    if (
                        self.p.sections[k[0]].lecturer_id == owner
                        if entity == "lecturer"
                        else owner in self.p.enrollment[k[0]]
                    )
                ]
                for day in range(7):
                    present, start_terms, end_terms, duration_terms = [], [], [], []
                    for k in keys:
                        xs = [
                            x
                            for a, x in zip(self.candidates[k], self.variables[k], strict=True)
                            if a.day == day
                        ]
                        if not xs:
                            continue
                        here = self.model.new_bool_var(f"here{entity}{owner}{day}{k}")
                        self.model.add(here == sum(xs))
                        present.append(here)
                        start = self.model.new_int_var(0, 1440, "day_start")
                        end = self.model.new_int_var(0, 1440, "day_end")
                        self.model.add(start == self.selected[k]["start"]).only_enforce_if(here)
                        self.model.add(start == 1440).only_enforce_if(here.Not())
                        self.model.add(end == self.selected[k]["end"]).only_enforce_if(here)
                        self.model.add(end == 0).only_enforce_if(here.Not())
                        start_terms.append(start)
                        end_terms.append(end)
                        duration_terms.append(self.p.sections[k[0]].minutes_per_session * here)
                    if not present:
                        continue
                    count = self.model.new_int_var(0, len(keys), "day_count")
                    self.model.add(count == sum(present))
                    square = self.model.new_int_var(0, len(keys) ** 2, "day_square")
                    self.model.add_multiplication_equality(square, [count, count])
                    self.objective.append(self.p.weights["spread"] * square)
                    earliest = self.model.new_int_var(0, 1440, "earliest")
                    latest = self.model.new_int_var(0, 1440, "latest")
                    idle = self.model.new_int_var(0, 1440, "idle")
                    self.model.add_min_equality(earliest, start_terms)
                    self.model.add_max_equality(latest, end_terms)
                    self.model.add_max_equality(idle, [0, latest - earliest - sum(duration_terms)])
                    self.objective.append(self.p.weights["compact"] * idle)
        for ka, kb in combinations(self.selected, 2):
            if ka[0] == kb[0]:
                for field, code in [("room_id", "room_changes"), ("start", "consistent_time")]:
                    different = self.model.new_bool_var(f"different{ka}{kb}{field}")
                    self.model.add(
                        self.selected[ka][field] != self.selected[kb][field]
                    ).only_enforce_if(different)
                    self.model.add(
                        self.selected[ka][field] == self.selected[kb][field]
                    ).only_enforce_if(different.Not())
                    self.objective.append(self.p.weights[code] * different)
        loads = []
        for room_id in self.p.rooms:
            load = self.model.new_int_var(0, len(self.candidates), "room_load")
            self.model.add(
                load
                == sum(
                    x
                    for k in self.candidates
                    for a, x in zip(self.candidates[k], self.variables[k], strict=True)
                    if a.room_id == room_id
                )
            )
            loads.append(load)
        high = self.model.new_int_var(0, len(self.candidates), "high_room_load")
        low = self.model.new_int_var(0, len(self.candidates), "low_room_load")
        self.model.add_max_equality(high, loads)
        self.model.add_min_equality(low, loads)
        self.objective.append(self.p.weights["room_balance"] * (high - low))

    def extract_solution(self, solver):
        return [
            next(a for a, x in zip(candidates, self.variables[k], strict=True) if solver.value(x))
            for k, candidates in self.candidates.items()
        ]

    def solve(self, cancelled=lambda: False, progress=lambda stage, amount: None):
        started = time.monotonic()
        progress("Model building", 15)
        self.build_model()
        progress("Solver", 30)
        results: list[dict] = []
        for index in range(self.config.alternatives):
            if cancelled():
                raise Cancelled("Generation cancelled")
            remaining = self.config.time_limit - (time.monotonic() - started)
            if remaining <= 0:
                break
            solver = cp_model.CpSolver()
            # Finding a first feasible schedule takes priority over returning more options.
            solver.parameters.max_time_in_seconds = max(0.1, remaining)
            solver.parameters.random_seed = self.config.random_seed
            solver.parameters.num_search_workers = 1  # Deterministic given input and seed.
            done = threading.Event()

            def monitor(done=done, solver=solver):
                while not done.wait(0.5):
                    if cancelled():
                        solver.stop_search()
                        break

            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            try:
                status = solver.solve(self.model)
            finally:
                done.set()
                watcher.join(timeout=2)
            if cancelled():
                raise Cancelled("Generation cancelled")
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                if not results:
                    raise SchedulingError(
                        "No feasible timetable was found within the time limit. Check competing resource demands, workload limits and availability; increase the time limit if the model is large."
                    )
                break
            solution = self.extract_solution(solver)
            violations = validate_solution(self.p, solution)
            if violations:
                raise SchedulingError(
                    "Independent validation rejected the solver output: "
                    + violations[0].description
                )
            penalties = score_solution(self.p, solution)
            results.append(
                {
                    "sessions": solution,
                    "violations": penalties,
                    "score": sum(x.penalty for x in penalties),
                    "solver_status": solver.status_name(status),
                    "duration_seconds": time.monotonic() - started,
                    "random_seed": self.config.random_seed,
                }
            )
            chosen = [x for k in self.candidates for x in self.variables[k] if solver.value(x)]
            movable = sum(len(v) > 1 for v in self.variables.values())
            if not movable:
                break
            self.model.add(sum(chosen) <= len(chosen) - max(1, ceil(movable * 0.1)))
            progress(
                "Alternative generation", 35 + int(45 * (index + 1) / self.config.alternatives)
            )
        return results
