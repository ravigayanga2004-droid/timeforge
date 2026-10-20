# Deployment and operations

Use PostgreSQL 16 and Redis 7 with the included Compose services. API and worker
images use Python 3.12 and unprivileged application users. The frontend uses a
multi-stage Node build and unprivileged Nginx. Runtime dependency versions are
constrained by backend/constraints.txt; frontend npm dependencies are locked.

1. Create an untracked .env from .env.example; set a unique PostgreSQL password.
2. Start db/redis, build images, and run `docker compose run --rm backend alembic upgrade head`.
3. Bootstrap an administrator with ADMIN_EMAIL/ADMIN_PASSWORD, or explicitly seed a demo.
4. Start all services. Check `docker compose ps`, `/api/health`, and `/api/ready`.
5. Check worker logs, run a small generation and verify publication and exports.

Readiness checks database connectivity, migration tracking and Redis availability
(Redis omitted only in explicitly configured eager mode). A health check alone
does not guarantee the schema is at the latest revision; apply migrations first.
Run migrations once before rolling out API/worker changes. Back up before schema
changes. For production serve the frontend through HTTPS and proxy `/api` to
FastAPI; configure exact origin, public URL, trusted hosts and secure cookies.
Keep Redis/database off public interfaces. Do not enable eager jobs in production.

The Windows development runner uses Celery's solo pool. Linux production can use
normal prefork concurrency. Compose defaults to two worker processes. Allow at
least 2 CPUs and 4 GB for a small installation, then measure representative models;
these are starting recommendations, not verified capacity guarantees. Dense models
can require substantially more RAM/CPU. A solver time budget excludes network and
some persistence overhead. Observe queue depth, failed/stale jobs and database size.

Hourly authentication cleanup requires a Celery beat process:
`celery -A app.jobs.celery beat --loglevel=info`. Run only one beat scheduler. Its
task removes expired auth records; audit/import/export retention needs an explicit
institutional policy. Password-reset messages use a persisted protected mail volume.
Replace the local mail adapter or connect a trusted spool consumer before public use.

Back up PostgreSQL without exposing credentials:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/timeforge.dump'
docker compose cp db:/tmp/timeforge.dump ./timeforge.dump
```

Encrypt/offsite the dump. Restore into a **separate empty test database** before
changing production: copy the dump into the DB container, then run pg_restore
with the configured user and target database. Test recovery and permissions.
Never run `docker compose down -v` on a database whose data must be preserved.

Manual retry creates a new GenerationJob. A worker crash can leave RUNNING state;
after ten minutes the retry endpoint permits recovery. Completed-task redelivery
does not create duplicate versions. There is no unbounded automatic retry loop.

Local Docker startup was attempted but the available engine was unusable; consult
the final report before treating these container instructions as runtime-verified.
