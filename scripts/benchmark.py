"""Bounded, disposable solver smoke benchmark; not an institutional load claim."""

from pathlib import Path
import secrets
import tempfile
import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models as m
from app.db import Base
from app.domain import load_problem, validate_solution
from app.schemas import GenerationIn
from app.seed import seed
from app.solver import Scheduler

with tempfile.TemporaryDirectory(prefix="timeforge-benchmark-") as directory:
    engine = create_engine(f"sqlite:///{(Path(directory)/'benchmark.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db, secrets.token_urlsafe(24))
        t = db.scalar(select(m.Timetable))
        assert t
        p = load_problem(db, t)
        scheduler = Scheduler(p, GenerationIn(alternatives=1, time_limit=30, optimize=False))
        started = time.perf_counter()
        results = scheduler.solve()
        elapsed = time.perf_counter() - started
        assert results and not validate_solution(p, results[0]["sessions"])
        print(
            {
                "sections": len(p.sections),
                "sessions": len(results[0]["sessions"]),
                "rooms": len(p.rooms),
                "slots": len(p.slots),
                "candidates": sum(map(len, scheduler.candidates.values())),
                "seconds": round(elapsed, 3),
                "status": results[0]["solver_status"],
            }
        )
    engine.dispose()
