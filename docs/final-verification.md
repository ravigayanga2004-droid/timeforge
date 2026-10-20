# Final verification - TimeForge v1.0.0

Verification date: 20 October 2026, Asia/Colombo. Original repository commit
`a5ef330` is preserved. All work and release history are local; no remote push or
hosted deployment was performed.

## Implemented and runnable

Institution/department/term/reference-data CRUD, normalized enrollments and room
features, secure account sessions and five roles, department authorization,
availability matrix/bulk writes, configurable supported soft preferences, CP-SAT
generation, independent hard validation, distinct alternatives, locks, durable
generation jobs, polling, cancellation/retry, immutable versions, visual editing,
undo/redo, validated suggestions, review/approval/publication, in-app notifications,
issue reporting, audit, atomic CSV imports, PDF/ICS/CSV exports and scoped analytics.

FastAPI/Pydantic/SQLAlchemy/Alembic form the API/data layer. PostgreSQL, Redis and
Celery are the deployment design; SQLite/eager execution are explicit local-test
adapters. React/TypeScript/Vite, TanStack Query, React Hook Form/Zod, Recharts and
native accessible controls form the web client. Plain CSS is the documented
alternative to Tailwind/shadcn. Dockerfiles, Compose, quality commands, dependency
constraints, migration checks and GitHub verification workflows are included.

## Executed checks

| Command/check | Observed result |
|---|---|
| `python scripts/manage.py test` | **61 passed**; final recorded run 24.59 seconds |
| `python -m black --check backend scripts` | Passed; 35 files unchanged |
| `python scripts/manage.py lint` / Ruff | Passed |
| `python scripts/manage.py typecheck` | Passed; 21 source files |
| `npm --prefix frontend run lint` | Passed |
| `npm --prefix frontend run typecheck` | Passed, strict TypeScript |
| `npm --prefix frontend test` | **4 passed**, 2 files |
| `npm --prefix frontend run build` | Passed; compiled application and vendor/chart chunks |
| `npm --prefix frontend audit` | **0 vulnerabilities**, including development dependencies |
| `python scripts/verify_migrations.py` | Clean migration, populated upgrade, preserved references, FK check, empty downgrade/upgrade and no schema drift passed |
| PostgreSQL offline Alembic compilation | Passed; circular version FKs emit explicit ALTER TABLE constraints |
| Explicit demo seed + actual generation | Passed; active sections produced persisted alternatives |
| `docker compose config --quiet` | Passed using an ignored local .env |
| Docker Engine / Compose runtime | **Not verified**; see infrastructure limitation below |
| Development Chromium workflow | **2 passed** against a disposable API/database |
| Production-asset Chromium workflow | **2 passed** in 59.4 seconds, including disposable API startup; E2E_PRODUCTION=1 exercised compiled assets |
| PDF rendering | Two exported report pages rendered with PDFium and visually inspected; wrapped rows, repeated headers and page numbers were readable |
| Solver smoke benchmark | 9 sections, 18 sessions, 6 rooms, 40 periods, 2,848 candidates; feasible solve and validation in **3.897 seconds** |

The benchmark used feasibility mode and is not an optimization or institutional
load guarantee. Timing varies with host load. Local Python was 3.14.7, Node
24.19.0, npm 11.17.0 and OR-Tools 9.15.6755. Python 3.12 container/CI definitions
were prepared but were not executed on a live container engine here.

One non-blocking Starlette warning advises migration from HTTPX to HTTPX2 in a
future test adapter. Vite removes two upstream Zod comment annotations during
build. Neither prevented checks from passing. Production JS is split into roughly
73 KB application, 182 KB shared vendor, 265 KB React/Query and 301 KB chart chunks
before gzip; the previous monolithic bundle warning is resolved.

## Constraint, solver and workflow evidence

- Negative detection covers all HC001-HC020 codes; generated assignments are
  independently revalidated and property tests vary capacity and seeds.
- Tests cover interval adjacency, contiguous durations, room type/equipment,
  availability, group collisions, workload, missing/duplicate meetings and locks.
- Locked manually reordered session labels remain fixed; conflict-draft saving
  cannot bypass a lock. Solver objective matches independent weighted scoring.
- Alternatives have different assignment fingerprints, not merely different IDs.
- Integration tests exercise job redelivery idempotency, queued cancellation,
  retry, persistence, comparison, stale-edit rejection and saved versions.
- Hard conflicts block review/publication. Coordinator approval is rejected.
  Published snapshots remain visible while later drafts are hidden from readers.
- Browser tests generate two alternatives, save a locked version, submit, approve,
  publish, and download ICS. They also visit academic/admin pages and verify mobile
  navigation and Escape dismissal of dialogs.

## Security and exchange evidence

Role/department/ownership restrictions, unpublished-resource isolation, CSRF,
logout/session invalidation, progressive login throttling, origin checks, reset
expiry/single use, token/password redaction, foreign-key validation and immutable
audit APIs have regression coverage. No .env, database, session token, password
hash, mail spool, test trace or dependency directory is tracked in Git.

CSV tests verify dry-run rollback, whole-file atomicity, row errors, duplicate
values, bad headers/extensions, size bounds and spreadsheet formula escaping.
ICS tests verify stable identifiers, escaped values, UTF-8 line folding, timezone
conversion and term-bounded recurrence dates. PDF tests cover escaped content and
multi-page tables; two actual export pages also received visual inspection.
Lecturer/student exports apply personal scope before rendering.

## Git release summary

Final release tag: **v1.0.0**. The finalized local history contains **70 commits
reachable from main (56 non-merge commits)** and **71 commits across all branches**
after synchronizing main back into develop. Counts include the preserved initial
commit. Every feature branch contains source, tests, configuration or documentation
changes; there are no empty or count-inflating whitespace-only feature commits.

Feature branches integrated into develop with non-fast-forward merges:

```text
feature/project-setup          feature/database-foundation
feature/authentication         feature/reference-data
feature/constraint-engine      feature/scheduling-solver
feature/generation-jobs        feature/approval-workflow
feature/import-export          feature/timetable-ui
feature/security-hardening     feature/testing
feature/documentation
```

Release uses release/v1.0.0 → main → develop. Main was left at the original stable
commit throughout implementation and receives the validated release merge. Some
foundational feature commits are intermediate assembly steps whose dependencies
land in subsequent feature branches; the released tree is integrated and tested.
Checks were run at integration boundaries and on the release tree; a separate
full-suite execution after every individual historical merge is not claimed.

Inspect the complete actual graph and branch membership with:

```sh
git branch -a
git log --graph --decorate --oneline --all
git rev-list --count main
git rev-list --all --count
git tag --list
```

## Explicit limitations and alternatives

| Requirement boundary | Current alternative / remaining work |
|---|---|
| Live PostgreSQL/Redis/Celery/Compose verification | Docker CLI was available, but the engine was absent and startup returned an internal API error. Local tests use SQLite/eager jobs; offline PostgreSQL SQL compilation and Compose configuration are not live-service evidence. Run Compose, clean PostgreSQL migrations, worker retries/cancellation and role checks before deployment. |
| Production readiness | No external penetration test, formal accessibility audit, live backup restore, production TLS deployment or large institutional load test was performed. Do not describe this checkout as fully production-certified. |
| All background-job categories | Generation and auth retention cleanup are worker tasks. Bounded CSV imports/reports, analytics and notification insertion run synchronously. Expand them into durable queued jobs before lifting limits. |
| Password reset delivery | Expiring one-time links go to a protected local mail spool. Configure SMTP/trusted spool delivery and retention for public use. No paid service or credentials were assumed. |
| Advanced soft constraints | Eleven supported codes have real scoring/modeling. Difficulty sequencing, building distance, priority tiers and arbitrary JSON-defined rules need additional implementation. |
| Institution-wide shared scheduling | Resources are department-scoped and one published timetable is permitted per department/term. Simultaneously overlapping terms and shared inter-department resources require broader institutional coordination; no global cross-term solver is claimed. |
| Large-data UI/solver scaling | Lists paginate; pickers/reference snapshots stop at 500 records. Solver is bounded at 5,000 sessions/150,000 candidates. Pairwise checks and Python candidate pruning are not benchmarked for thousands of meetings. |
| Existing timetable CSV ingestion | Full assignments can enter through the validated version-edit JSON API. Readable timetable CSV is not a round-trip parser. Academic/resource CSV imports and exports are implemented. |
| Alternative duplication/rejection UI | Duplicate-timetable and reject-alternative APIs exist. The interface supports comparison, inspection, selection and version reversion, but does not expose every auxiliary API action. |
| Availability copying | Multi-select, whole-day selection and day-to-day copy are implemented. Cross-resource copying uses academic CSV/API operations rather than a dedicated UI action. |
| Elective enrollment choices | Sections and elective groups are modeled. Enrollment choices must be configured before solving; the solver does not decide which elective section a student chooses. |
| Custom permissions/system settings | Built-in roles are enforced. Universities/timezones and scheduling preferences are editable; infrastructure settings are environment configuration. There is no arbitrary permission editor or secrets UI. |
| Infeasibility explanation | Empty candidate domains identify likely incompatible resources/requirements. General infeasibility is explained safely but does not compute a minimal unsatisfiable core. |
| Cancellation and worker crashes | Search is cooperatively cancellable; model building may delay cancellation. Stale running jobs need explicit retry after ten minutes. No automatic unbounded retries are claimed. |
| Unicode PDF typography | Current ReportLab fonts are suitable for the demonstrated Latin course names. Configure/verify appropriate fonts and shaping before using scripts outside that repertoire. |
| Deployment verification | Nginx security headers, protected mail volume and container recipes are configured; running them and inspecting browser security headers still requires a working engine. GitHub workflows have not been run remotely. |

Recommended next engineering work: perform the live PostgreSQL/Redis/container
acceptance run, configure real mail delivery, test representative institutional
data and cross-term publication policy, then extend queued exchange jobs and
perform formal accessibility/security review. No unsupported feature is presented
as a functioning placeholder or a precomputed timetable.
