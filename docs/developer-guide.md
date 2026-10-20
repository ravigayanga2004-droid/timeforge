# Developer guide

Install the editable backend with dev extras and constraints, and run npm ci in
frontend/. See README for platform-specific invocations. Configure .env in the
backend working directory for direct Python commands, or set environment variables
in the shell. Compose reads the root .env and supplies its service environment.

Backend modules:

- models/db/config: relational schema, sessions and deployment configuration.
- schemas/reference: strict contracts, scoped CRUD, relationship validation.
- security/auth: password/session/CSRF/department/role checks and recovery.
- domain/solver: independent validation/scoring and CP-SAT modeling.
- jobs: durable generation task lifecycle and authentication cleanup.
- timetable_service/timetables: versions, editing, workflow, comparison and reports.
- imports/exports/administration/availability: exchange and governance.

To add a hard constraint, assign a stable code, explain it in HARD_CONSTRAINTS,
implement independent detection, add candidate/model representation, and add both
negative-detection and generated-solution tests. Never implement an invariant only
in a UI or only in CP-SAT. Revalidate persistence and publication after changes.

To add a soft constraint, define its units/weight, independent explanation/scoring,
model objective terms, allowed schema code and tests comparing objective/scorer.
Define enabled-state and term/department scope. Arbitrary JSON configuration is not
an execution mechanism.

To add a collection/import format, define a Pydantic schema, relational model and
migration; register the collection and permissions; validate all foreign keys and
scope; provide bounded parser, preview, rollback and audit tests. Frontend forms
read registry JSON schemas. Do not bypass save_record in a new import parser.

To run the solver directly, construct/load a Problem, create GenerationIn and call
`Scheduler(problem, config).solve()`. Results contain typed assignments, violations,
score, status, timing and seed. The production persistence path reloads reference
data and validates again. Use a disposable database for solver experiments.

Use focused feature branches from develop, meaningful commits and non-fast-forward
integration merges. Keep main stable. Run the backend/frontend quality commands
and appropriate tests before integration. Release through release/v1.0.0 and tag
after validation. Never push secrets, generated databases, .mail, node_modules,
test traces or temporary reports. Git history is local until explicitly pushed.
