# API

OpenAPI at `/openapi.json` and Swagger at `/docs` are authoritative for methods and
typed workflow requests. All application endpoints start with `/api`. List APIs
return `{items,total}` (notifications only return items). Errors use `{detail}`;
validation errors contain field locations and messages without echoing passwords.

| Area | Endpoints |
|---|---|
| Auth | POST `/auth/login`, `/logout`, `/forgot-password`, `/reset-password`; GET `/auth/me` |
| Users | GET/POST `/users`; PUT `/users/{id}` |
| Academic data | GET/POST `/data/{entity}`; PUT/DELETE `/data/{entity}/{id}`; GET `/data/schema` |
| Availability | POST `/availability/bulk` replaces selected owner/period rules atomically |
| Timetables | GET/POST `/timetables`; GET `/timetables/{id}` |
| Generation | POST `/timetables/{id}/generate`; GET `/jobs/{id}`; POST `/jobs/{id}/cancel`, `/retry` |
| Versions | GET `/versions/{id}`; POST `/versions/{id}/validate`; GET `/timetables/{id}/compare` |
| Editing | POST `/timetables/{id}/preview`, `/edit`, `/select`, `/duplicate` |
| Alternatives | POST `/versions/{id}/reject` with action=reject and notes |
| Workflow | POST `/timetables/{id}/workflow` with action and notes |
| Reports | GET `/versions/{id}/analytics`, `/export/{csv|ics|pdf}` |
| Exchange | POST `/imports/{entity}` multipart; GET `/imports/{entity}/template`, `/export` |
| Governance | GET `/audit`, `/notifications`; POST `/notifications/{id}/read`, `/timetables/{id}/issues` |
| Health | GET `/health`, `/ready` |

Collections: universities, departments, academic-years, terms, buildings,
room-features, rooms, time-slots, lecturers, student-groups, courses, sections,
availability and constraints. Writes require complete validated records; extra
keys are rejected. PATCH is intentionally absent. DELETE archives resources with
active/status fields and otherwise deletes only when foreign keys allow it.

Lists support bounded offset/limit; academic lists also accept q, sort (prefix `-`
for descending), department_id and term_id when applicable. Maximum page size is
500. Academic forms obtain schemas from `/data/schema`; generic collection bodies
are validated against that registry even though their OpenAPI body type is dict.

Login sets HTTP-only `tf_session` and readable `tf_csrf` cookies. Authenticated
mutations require the `X-CSRF-Token` header matching the issued CSRF cookie. Supply
cookies on every call. Cross-department and unpublished-version access are checked
on the server, including exports. Reader academic listings contain published
records; lecturers can additionally access their own availability inputs.

Examples: generation accepts alternatives, time_limit, random_seed, optimize,
respect_locked and optional section_ids/room_ids/slot_ids. Edits contain
base_version_id, sessions and allow_draft_conflicts. Session fields are section_id,
session_number, day, start, end, room_id, lecturer_id, is_locked and notes.

Workflow actions: submit, approve, reject, publish, archive, reopen. Conflicts block
submission/approval/publication. Rejection/reopening require notes; publication
with soft penalties also requires notes. Duplicate/reject-alternative operations
are API capabilities; the interface supports selecting and inspecting alternatives.
