# CP-SAT scheduling

`load_problem()` loads scoped sections, enrollments, rooms, lecturers, groups,
periods, availability, preferences and locks. Each weekly meeting becomes a
distinct assignment variable.

`build_model()` enumerates room/start-period candidates, pruning incompatible
assignments with the independent validator. Durations may span adjacent active
periods but cannot bridge a gap. ExactlyOne selects a candidate per required
meeting. Optional intervals and NoOverlap enforce room/lecturer/group collisions.
Linear bounds enforce workload. Additional constraints enforce spacing, fixed
weekdays and locked domains. Chronological numbering removes cosmetic swaps.

`add_soft_constraints()` minimizes weighted preference, early/late/weekend,
idle-minute, daily concentration, room consistency, time consistency and room
imbalance costs. Independent scoring explains each contribution. Tests compare
the model objective with independent scoring.

`solve()` shares a bounded budget among alternatives and uses a configured seed
and one search worker. A remaining-budget feasibility fallback is used if initial
optimization finds no assignment. Extracted solutions must independently validate.
Timeouts never manufacture results. Reproducibility assumes identical inputs,
solver version and sufficient search time; wall-clock exhaustion can change how
many alternatives are returned.

Each solution adds a no-good constraint requiring at least ceil(10% of movable
assignments) to change, minimum one. Fewer options are returned when the feasible
space or budget is exhausted. Scoring and status distinguish FEASIBLE from proven
OPTIMAL results. No genetic algorithm replaces CP-SAT.

A watchdog polls cancellation every half second during solver search. Model
construction observes cancellation at the next solver boundary, so cancellation
latency can exceed half a second. Progress includes validation, model building,
solving, alternatives, revalidation, persistence and completion.

Safety bounds are 5,000 sessions and 150,000 candidates. These are limits, not
performance promises. Python candidate validation and pairwise conflict analysis
need benchmarking and decomposition for dense institutional-scale workloads.
