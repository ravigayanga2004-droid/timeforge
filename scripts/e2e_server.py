"""Run a disposable API for Playwright; never reuse the working application database."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
password = os.environ.get("E2E_PASSWORD", "")
if len(password) < 12:
    raise SystemExit(
        "Set E2E_PASSWORD (at least 12 characters) for the disposable browser accounts"
    )
with tempfile.TemporaryDirectory(prefix="timeforge-browser-") as directory:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{Path(directory).as_posix()}/browser.db",
        "JOBS_EAGER": "true",
        "SEED_PASSWORD": password,
    }
    for command in [
        ["alembic", "upgrade", "head"],
        ["app.seed", "--generate"],
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
    ]:
        subprocess.run([sys.executable, "-m", *command], cwd=ROOT / "backend", env=env, check=True)
