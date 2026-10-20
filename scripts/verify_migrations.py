"""Check clean and populated SQLite upgrades in isolated temporary databases."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="timeforge-migration-") as directory:
    path = Path(directory) / "verification.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{path.as_posix()}"}

    def alembic(*args):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=root / "backend",
            env=env,
            check=True,
        )

    alembic("upgrade", "7b4d0c3e623b")
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO departments (name,code,description,head,is_active,created_at,updated_at) VALUES ('Preserved department','KEEP','','',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        db.execute(
            "INSERT INTO student_groups (name,code,department_id,academic_year,size,group_type,max_daily_hours,created_at,updated_at) VALUES ('Preserved group','G1',1,1,30,'cohort',7,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
    db.close()
    alembic("upgrade", "head")
    alembic("check")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM departments").fetchone()[0] == "Preserved department"
        assert db.execute("SELECT name FROM student_groups").fetchone()[0] == "Preserved group"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        db.execute("DELETE FROM student_groups")
        db.execute("DELETE FROM departments")
    db.close()
    alembic("downgrade", "base")
    alembic("upgrade", "head")
    alembic("check")
    print(
        "Clean migration, populated upgrade, preservation, foreign-key check and round-trip passed."
    )
