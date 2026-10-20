"""Create the first administrator without inserting demonstration academic data."""

import os

from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from app.schemas import UserIn
from app.security import hash_password


def main():
    data = UserIn(
        name=os.environ.get("ADMIN_NAME", "University Administrator"),
        email=os.environ.get("ADMIN_EMAIL", ""),
        password=os.environ.get("ADMIN_PASSWORD", ""),
        role="admin",
    )
    with SessionLocal() as db:
        if db.scalar(select(m.User).where(m.User.role == "admin")):
            raise SystemExit(
                "An administrator already exists. Use the authenticated user management API."
            )
        for role in ["admin", "coordinator", "lecturer", "student", "viewer"]:
            if not db.scalar(select(m.Role).where(m.Role.name == role)):
                db.add(m.Role(name=role))
        db.flush()
        user = m.User(
            name=data.name,
            email=str(data.email).lower(),
            password_hash=hash_password(data.password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print("Initial administrator created. No demonstration data was inserted.")


if __name__ == "__main__":
    main()
