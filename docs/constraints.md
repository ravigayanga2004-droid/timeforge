# Constraint catalog

Hard constraints cannot be disabled. Each code has independent validation, a
solver representation, human-readable explanations and a parameterized test.

| Code | Invariant | Solver representation |
|---|---|---|
| HC001 | Lecturer cannot overlap | Optional intervals / NoOverlap |
| HC002 | Room cannot overlap | Optional intervals / NoOverlap |
| HC003 | Every enrolled group cannot overlap | Optional intervals / NoOverlap |
| HC004 | Room is active | Candidate pruning |
| HC005 | Capacity meets enrollment and summed group size | Candidate pruning |
| HC006 | Required room type | Candidate pruning |
| HC007 | Required equipment | Candidate pruning |
| HC008 | Lecturer availability | Candidate pruning |
| HC009 | Group availability | Candidate pruning |
| HC010 | Room availability | Candidate pruning |
| HC011 | Correct weekly meeting count | ExactlyOne per required meeting |
| HC012 | Duration and contiguous active periods | Candidate pruning |
| HC013 | Valid assigned lecturer | Candidate construction/pruning |
| HC014 | Valid enrolled groups | Candidate pruning |
| HC015 | Valid scoped room | Candidate construction/pruning |
| HC016 | Term occurrence and fixed weekday | Candidate pruning |
| HC017 | Locked placement preserved | Candidate domain restriction |
| HC018 | Unique section/session identifier | Variables and database uniqueness |
| HC019 | Daily/group and daily/weekly lecturer hours | Linear bounds |
| HC020 | Section availability/spacing/non-adjacency | Pruning and day/time constraints |

Submission, approval, publication and generated-session persistence invoke the
validator. Conflict drafts are explicit and cannot be submitted or published.
Locked-placement violations cannot be persisted as conflict drafts.

Soft costs are configurable per department and term:

| Code | Units before weighting |
|---|---|
| preferred_time | Missed course/resource preferred times; discouraged resource times |
| preferred_room / preferred_day | Assignments outside the preferred set |
| early / late | Starts before 09:00 / ends after 17:00 |
| weekend | Weekend assignments |
| compact | Idle minutes per lecturer/group/day |
| spread | Squared daily meeting count per lecturer/group |
| room_changes / consistent_time | Same-section pairs differing in room/start minute |
| room_balance | Highest minus lowest room session count |

Total penalty is the sum of weighted units; lower is better. Counts measure
explanation entries, not distinct constraint types. Spread penalties can remain
nonzero in an otherwise balanced schedule. Zero weight disables a preference.
Difficulty sequencing, building distance and priority tiers are not implemented.
