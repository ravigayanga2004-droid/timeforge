"""Explicit, idempotent demonstration dataset. Never run automatically in production."""

import argparse
import os
from datetime import date

from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from app.schemas import GenerationIn
from app.security import hash_password


def seed(db, password: str):
    if db.scalar(select(m.User).limit(1)):
        return False
    for name in ["admin", "coordinator", "lecturer", "student", "viewer"]:
        db.add(m.Role(name=name))
    db.flush()
    for role in db.scalars(select(m.Role)):
        for code in (
            ["manage", "approve", "users", "audit"]
            if role.name == "admin"
            else ["manage"] if role.name == "coordinator" else ["view_published"]
        ):
            db.add(m.Permission(role_id=role.id, code=code))
    department = m.Department(
        name="School of Computing",
        code="SOC",
        description="Demonstration academic department",
        head="Prof. Amara Perera",
    )
    db.add(department)
    db.flush()
    year = m.AcademicYear(name="2026 / 2027")
    building = m.Building(name="Computing & Innovation Centre", code="CIC", location="North campus")
    projector = m.RoomFeature(name="Projector")
    computers = m.RoomFeature(name="Computers")
    db.add_all([year, building, projector, computers])
    db.flush()
    term = m.AcademicTerm(
        name="Semester 1 · 2026/27",
        department_id=department.id,
        academic_year_id=year.id,
        start_date=date(2026, 10, 19),
        end_date=date(2027, 2, 19),
        semester=1,
    )
    db.add(term)
    db.flush()
    groups = []
    for index in range(3):
        group = m.StudentGroup(
            name=f"Computing Year {index+1}",
            code=f"CS-Y{index+1}",
            department_id=department.id,
            academic_year=index + 1,
            size=35 + index * 5,
        )
        db.add(group)
        groups.append(group)
    db.flush()
    users = {}
    for role, name in [
        ("admin", "Amara Perera"),
        ("coordinator", "Nethmi Silva"),
        ("lecturer", "Dr. Kavindu Fernando"),
        ("student", "Sam Wijesinghe"),
        ("viewer", "Campus Visitor"),
    ]:
        user = m.User(
            name=name,
            email=f"{role}@timeforge.example",
            password_hash=hash_password(password),
            role=role,
            department_id=department.id,
            group_id=groups[0].id if role == "student" else None,
        )
        db.add(user)
        users[role] = user
    db.flush()
    lecturers = []
    for index, name in enumerate(
        [
            "Dr. Kavindu Fernando",
            "Dr. Maya Senanayake",
            "Prof. Dilan Jayawardena",
            "Dr. Anika Raman",
            "Dr. Ruwan de Silva",
            "Dr. Sara Hassan",
        ]
    ):
        lecturer = m.Lecturer(
            name=name,
            email=f"lecturer{index+1}@timeforge.example",
            employee_number=f"SOC-{index+1:03}",
            department_id=department.id,
            user_id=users["lecturer"].id if index == 0 else None,
            max_daily_hours=5,
            max_weekly_hours=20,
        )
        db.add(lecturer)
        lecturers.append(lecturer)
    rooms = []
    for index in range(6):
        room = m.Room(
            name=f"{'Computer Lab' if index>=4 else 'Lecture Hall'} {index+1}",
            code=f"CIC-{index+101}",
            building_id=building.id,
            department_id=department.id,
            capacity=60 if index >= 4 else 80,
            room_type="computer_lab" if index >= 4 else "lecture",
            floor=index // 3,
        )
        db.add(room)
        rooms.append(room)
    db.flush()
    for room in rooms:
        db.add(m.RoomFeatureLink(room_id=room.id, feature_id=projector.id))
        if room.room_type == "computer_lab":
            db.add(m.RoomFeatureLink(room_id=room.id, feature_id=computers.id))
    slots = []
    for day in range(5):
        for period in range(8):
            slot = m.TimeSlot(
                day=day, start=(8 + period) * 60, end=(9 + period) * 60, period=period + 1
            )
            db.add(slot)
            slots.append(slot)
    db.flush()
    for index, name in enumerate(
        [
            "Programming Fundamentals",
            "Discrete Mathematics",
            "Computer Systems",
            "Data Structures & Algorithms",
            "Database Systems",
            "Software Engineering",
            "Artificial Intelligence",
            "Distributed Systems",
            "Information Security",
        ]
    ):
        course = m.Course(
            name=name, code=f"CS{index//3+1}{index%3+1}01", department_id=department.id, credits=3
        )
        db.add(course)
        db.flush()
        section = m.CourseSection(
            code=course.code + "-A",
            course_id=course.id,
            term_id=term.id,
            department_id=department.id,
            lecturer_id=lecturers[index % 6].id,
            expected_enrollment=groups[index // 3].size,
            sessions_per_week=2,
            minutes_per_session=60,
            required_room_type="lecture",
            required_features=["Projector"],
            preferred_days=[0, 2, 4],
            min_day_spacing=1,
        )
        db.add(section)
        db.flush()
        db.add(m.CourseEnrollmentGroup(section_id=section.id, group_id=groups[index // 3].id))
        db.add(m.CoursePreferredRoom(section_id=section.id, room_id=rooms[index % 4].id))
    for slot in slots:
        if slot.day == 0 and slot.start < 10 * 60:
            db.add(
                m.Availability(
                    department_id=department.id,
                    term_id=term.id,
                    lecturer_id=lecturers[0].id,
                    slot_id=slot.id,
                    kind="unavailable",
                    reason="Research supervision",
                    created_by=users["admin"].id,
                )
            )
    db.add(
        m.Timetable(
            name="Computing · Semester 1",
            department_id=department.id,
            term_id=term.id,
            created_by=users["coordinator"].id,
        )
    )
    db.commit()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="Run the real solver after seeding")
    args = parser.parse_args()
    password = os.environ.get("SEED_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set SEED_PASSWORD to at least 12 characters before creating demo users")
    with SessionLocal() as db:
        created = seed(db, password)
        print(
            "Demonstration dataset created."
            if created
            else "Existing users found; seed left unchanged."
        )
        if args.generate and created:
            from app.jobs import run_generation

            timetable = db.scalar(select(m.Timetable))
            user = db.scalar(select(m.User).where(m.User.role == "coordinator"))
            assert timetable is not None and user is not None
            job = m.GenerationJob(
                timetable_id=timetable.id,
                created_by=user.id,
                configuration=GenerationIn(time_limit=30).model_dump(),
            )
            timetable.status = "GENERATING"
            db.add(job)
            db.commit()
            run_generation(job.id)
            db.refresh(job)
            print(f"Generation: {job.status}. {job.error_message or ''}")


if __name__ == "__main__":
    main()
