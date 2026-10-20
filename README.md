# TimeForge

A university timetable application with a real OR-Tools CP-SAT solver, FastAPI
API and React administration workspace. Academic records, generation jobs,
alternatives, versions, approvals, notifications and audit records are persisted.
Demonstration schedules come from the solver, never hardcoded assignments.

## Features

- Universities, departments, terms, buildings, rooms/equipment, periods,
  lecturers, groups, courses and enrolled course sections.
- Argon2id passwords, server-side sessions, CSRF, five roles, department scope,
  password recovery and login throttling.
- Availability matrix and atomic CSV imports with preview and row errors.
- Weighted CP-SAT optimization, distinct alternatives, locks, seeds, progress,
  cancellation and retry.
- Weekly/daily/list/conflict views, filters, drag/drop, undo/redo, validated edits,
  immutable versions, review, approval, publication and archival.
- PDF/CSV/ICS exports, utilization/workload analytics, notifications and audits.

This is a substantial runnable implementation. Read the explicit scope and
verification limits in [final verification](docs/final-verification.md) before
deployment; this checkout is not independently certified production-ready.

## Stack and architecture

```text
React + TanStack Query → FastAPI → PostgreSQL
                            ↓
                       Redis → Celery → CP-SAT
```

The backend uses SQLAlchemy 2, Alembic, Pydantic 2 and ReportLab. The frontend uses
Vite, strict TypeScript, React Hook Form/Zod, accessible native controls, Lucide,
Recharts and a custom calendar with keyboard editing through session dialogs.
SQLite is supported for isolated tests and lightweight development.

## Prerequisites

Python 3.12+ (locally verified on 3.14), Node 24+, npm and Git. Docker Engine or
Docker Desktop with Compose is needed for PostgreSQL/Redis/worker deployment.
Use `npm.cmd` in PowerShell if execution policy blocks `npm.ps1`.

## Local setup (PowerShell, repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c backend/constraints.txt -e 'backend[dev]'
npm.cmd --prefix frontend ci
$env:DATABASE_URL='sqlite:///timeforge-local.db'
$env:JOBS_EAGER='true'
.\.venv\Scripts\python.exe scripts/manage.py db:upgrade
$env:SEED_PASSWORD='<choose at least 12 characters>'
.\.venv\Scripts\python.exe scripts/manage.py db:seed --generate
.\.venv\Scripts\python.exe scripts/manage.py dev
```

In another terminal run `npm.cmd --prefix frontend run dev`. Open
**http://localhost:5173**, matching the default `ALLOWED_ORIGIN`. Keep the database
and eager-mode environment variables in every backend shell. SQLite paths are
relative to `backend/`. Linux/macOS use `.venv/bin/python` and `export NAME=value`.

### Demo accounts

Seed creates `admin@timeforge.example`, `coordinator@timeforge.example`,
`lecturer@timeforge.example`, `student@timeforge.example`, and
`viewer@timeforge.example`. The password is the **SEED_PASSWORD you supplied**.
No default password is committed. Seed does not alter an existing user database.

For production, run `python -m app.bootstrap` from `backend/` with `ADMIN_EMAIL`,
`ADMIN_PASSWORD` and optionally `ADMIN_NAME`. This creates an administrator and
roles without demonstration academic records.

## Docker setup

Copy `.env.example` to `.env`, replace the password, and keep it untracked.

```sh
docker compose up -d db redis
docker compose build
docker compose run --rm backend alembic upgrade head
# Explicit demonstration only; SEED_PASSWORD must already be set in your shell:
docker compose run --rm -e SEED_PASSWORD backend python -m app.seed --generate
docker compose up -d
docker compose ps
```

For production bootstrap, pass `-e ADMIN_EMAIL -e ADMIN_PASSWORD` and run
`python -m app.bootstrap` instead. Supply secrets via environment, not command
arguments. Web/API, database and development Redis ports bind loopback.
See [deployment](docs/deployment.md) for TLS, cookies and backup/restore.

## Commands and testing

Backend: `python scripts/manage.py <command>` using the virtualenv.

| Command | Purpose |
|---|---|
| `dev`, `start`, `worker` | Reload API, API server, Celery worker |
| `test`, `test:watch` | Pytest, continuously rerun after file changes |
| `lint`, `format`, `typecheck` | Ruff, Black, MyPy |
| `db:migrate "description"`, `db:upgrade` | Generate/apply migrations |
| `db:seed [--generate]` | Explicit demo seed, optional real solving |

Frontend: `npm --prefix frontend run <command>` supports `dev`, `build`, `preview`,
`test`, `test:e2e`, `lint`, `format`, `typecheck`.

```powershell
.\.venv\Scripts\python.exe scripts/manage.py test
.\.venv\Scripts\python.exe scripts/verify_migrations.py
npm.cmd --prefix frontend test
# Install Chromium once from frontend/: npx playwright install chromium
$env:E2E_PASSWORD='<choose a disposable password of at least 12 characters>'
npm.cmd --prefix frontend run test:e2e
```

Playwright launches a disposable seeded API and Vite server; ports 8000/5173 must
be free. `E2E_REUSE=1` explicitly targets existing test servers. Screenshots/traces
are in ignored `frontend/test-results/`. Capture Overview and Timetable Studio
after seeding and generation for representative application screenshots.

## Scheduling and workflow

Hard constraints are mandatory. Soft constraints contribute weighted penalties;
**lower scores are better**. Exactly one compatible assignment is selected for
each weekly meeting. Room, lecturer and group intervals cannot overlap. Each
alternative excludes previous assignments and changes at least 10% of movable
sessions (minimum one). Time-limited runs can return fewer alternatives.

Locks preserve placements during generation. Save an unlocked version before
moving a locked session manually. Every save creates a new version. Coordinators
submit; administrators approve and publish. Hard conflicts block review and
publication. Readers keep seeing the published snapshot while new drafts are
prepared. Publication with soft penalties requires notes.

## Documentation

API documentation: **http://localhost:8000/docs**; schema: `/openapi.json`.
Academic form schemas: `/api/data/schema`.

- [Architecture](docs/architecture.md), [database](docs/database-schema.md)
- [Scheduling](docs/scheduling-algorithm.md), [constraints](docs/constraints.md)
- [API](docs/api.md), [exchange](docs/import-export.md)
- [User guide](docs/user-guide.md), [developer guide](docs/developer-guide.md)
- [Testing](docs/testing.md), [security](docs/security.md)
- [Deployment](docs/deployment.md), [implementation plan](docs/implementation-plan.md)
- [Final verification and limitations](docs/final-verification.md)

Future work includes SMTP delivery, cross-term institutional coordination,
large-data benchmarks, further soft constraints, queued bulk imports/reports and
formal accessibility/security review. Precise outstanding work is documented in
the verification report.
