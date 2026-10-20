"""Cross-platform root command runner. Run with the repository virtualenv Python."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    "dev": [sys.executable, "-m", "uvicorn", "app.main:app", "--reload"],
    "start": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0"],
    "worker": [sys.executable, "-m", "celery", "-A", "app.jobs.celery", "worker", "--loglevel=info", "--pool=solo"],
    "test": [sys.executable, "-m", "pytest", "-q"],
    "test:watch": [sys.executable, "-m", "pytest", "-x", "--lf"],
    "lint": [sys.executable, "-m", "ruff", "check", "."],
    "format": [sys.executable, "-m", "black", "."],
    "typecheck": [sys.executable, "-m", "mypy", "app"],
    "db:migrate": [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m"],
    "db:upgrade": [sys.executable, "-m", "alembic", "upgrade", "head"],
    "db:seed": [sys.executable, "-m", "app.seed"],
}
if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
    raise SystemExit("Usage: python scripts/manage.py " + " | ".join(COMMANDS))
os.chdir(ROOT / "backend")
raise SystemExit(subprocess.call(COMMANDS[sys.argv[1]] + sys.argv[2:]))
