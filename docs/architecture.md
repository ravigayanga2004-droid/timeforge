# Architecture

React calls cookie-authenticated FastAPI APIs through Vite/Nginx. TanStack Query
caches responses and polls active jobs every 1.5 seconds. React Hook Form manages
typed form values; Zod validates login. Native forms, dialogs and tables provide
accessible interaction. Frontend visibility never grants backend authorization.

Routers delegate to reference-data, security, timetable-workflow and solver
services. Pydantic rejects extra fields and bounds inputs. SQLAlchemy parameterizes
queries. PostgreSQL is the deployment database; SQLite supports local development
and isolated tests. JSONB holds flexible configuration and metrics; relationships
and frequently filtered fields are relational columns.

Generation requests commit before enqueueing Celery tasks in Redis. Workers claim
QUEUED jobs, report progress, solve a loaded input snapshot, reload inputs, validate
again, then persist alternatives atomically. Completed results survive duplicate
task delivery. Failures and cancellations retain durable status. Explicit retry
creates a new job; stale RUNNING jobs may be retried after ten minutes. PostgreSQL
row locks coordinate production workers.

The editor validates complete candidate assignments with the server. Undo/redo is
local until saving. Saves create immutable versions and check the expected active
base version. Published pointers are separate from draft pointers. Publication
requires revalidation and approval. A published timetable remains visible while a
new draft is prepared.

Compose separates API, web, worker, PostgreSQL and Redis. Reference responses have
a ten-second browser cache; there is no cross-process server cache with stale
invalidation. Reports/imports are bounded synchronous operations; generation and
authentication retention cleanup use background workers.
