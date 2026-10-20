# Testing

Run from the repository root using the installed virtualenv:

```text
python scripts/manage.py lint
python -m black --check backend scripts
python scripts/manage.py typecheck
python scripts/manage.py test
python scripts/verify_migrations.py
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Backend tests build a single demonstration database template and copy it to an
isolated database for each test. Foreign keys stay enabled. HTTP tests exercise
real routers, auth, transactions, solver calls, persistence and exports; Celery
uses the explicitly enabled eager adapter. No external production data is used.

Constraint tests cover all twenty hard codes, interval boundaries, duration gaps,
capacity infeasibility, locks, preference weights, objective/scorer equality and
reproducibility. Hypothesis generates capacities/seeds and validates every returned
assignment repeatedly, including alternative diversity.

Integration/security tests cover all roles, unauthorized writes, department IDOR,
unpublished access, CSRF, logout, progressive throttling, reset-token reuse, session
invalidation, password redaction, reference validation, import rollback, malformed
uploads, export format signatures, ICS folding/term dates, PDF pagination, editing,
stale-version rejection, review/publication, notifications, audit, retry/cancel and
task redelivery idempotency.

React Testing Library checks login validation, recovery access and form value
types. Calendar layout tests verify independent concurrent sessions remain visible.
Playwright covers academic navigation, keyboard dialog closure, mobile navigation,
generation of two alternatives, locking, saved versions, submission, approval,
publication and an ICS download. Browser tests use disposable seeded APIs by default.

Migration verification starts at the original revision, inserts a department and a
referencing group, upgrades, confirms preservation and foreign keys, then exercises
an empty downgrade/upgrade and metadata drift check. PostgreSQL SQL compilation is
an additional check, not a substitute for a live PostgreSQL run.

See final-verification.md for actual counts and commands. The GitHub workflow
defines Python 3.12/3.14 and Chromium checks but has not been claimed as executed
remotely. Unit/integration checks are not a load test, formal accessibility audit,
penetration test or evidence of performance with thousands of sessions.
