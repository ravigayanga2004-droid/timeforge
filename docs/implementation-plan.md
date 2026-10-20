# TimeForge implementation plan

## Repository inspection (20 October 2026)

The repository has one commit (`a5ef330`), branch `main`, remote
`https://github.com/ravigayanga2004-droid/timeforge.git`, and a descriptive README.
There is no application, package manager, database, script, or established code
convention. The README's project intent is retained. No existing feature is removed.
The host provides Python 3.14, Node 24, npm 11, Git, and Docker CLI.

## Architecture and phases

1. Foundation: Python FastAPI service, React/TypeScript Vite client, development
   scripts, PostgreSQL/Redis/Celery Compose stack, quality tools and configuration.
2. Data and security: normalized relational entities, migrations, explicit seed
   command, server-side sessions, CSRF, department and role enforcement, audit.
3. Academic data: validated CRUD, availability, constraints, atomic CSV imports.
4. Scheduling: independent validator, CP-SAT candidate model, weighted preferences,
   locked assignments, distinct alternatives, persisted and cancellable jobs.
5. Workflow: immutable versions, validated edits, approvals, publication,
   notifications, scoped analytics and PDF/ICS/CSV exports.
6. Interface: accessible administration shell, data forms, availability grid,
   generation controls, calendar/editor, comparison, workflow and reports.
7. Verification/release: unit, integration, property, browser and security checks,
   production build, clean migration/seed verification, operations documentation.

Each phase receives focused commits on a feature branch merged into `develop`.
Checks run at integration boundaries; observed failures are corrected before
release. Only locally verified work is described as verified. Unsupported optional
behaviors and infrastructure limitations are recorded in final-verification.md.

## Design decisions

- PostgreSQL is the deployment database; SQLite is supported for isolated tests
  and a lightweight developer preview, never as a replacement for PostgreSQL QA.
- Timetables belong to a department and term. Every API lookup enforces scope.
- A session can serve several student groups through section enrollments.
- Recurring weekly schedules use integer local minutes and weekdays. The academic
  term controls occurrence dates; ICS uses the configured IANA timezone.
- CP-SAT is authoritative. Candidate pruning and the independent validator share
  domain types but not collision-detection implementation.
- Session edits create new versions; published snapshots remain immutable.
- Realistic seed records are explicitly labelled demonstration data and opt-in.
- No remote push or hosted deployment is required by this repository task.

## Acceptance evidence

Document commands, counts, constraints, permission matrix, migration results,
browser results and outstanding limitations in docs/final-verification.md. Never
claim that a test or Docker run passed without executing it.
