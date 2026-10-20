# Database schema

Models and Alembic revisions are the executable schema. Records include integer
IDs and UTC created/updated timestamps. Association tables use composite keys.
Unique codes/emails and indexes support scoped and calendar queries.

| Area | Tables/relationships |
|---|---|
| Institutions | universities → departments; academic_years → academic_terms → department |
| Identity | roles, permissions, users, auth_sessions, reset_tokens, login_attempts |
| Resources | buildings, rooms, room_features, room_feature_links, time_slots, lecturers, student_groups |
| Teaching | courses, course_sections, course_enrollment_groups, course_requirements, section_requirements, course_preferred_slots, course_preferred_rooms |
| Availability | availability → term/slot and exactly one lecturer, group, room or section |
| Planning | timetables, timetable_versions, scheduled_sessions, session_time_slots, session_rooms |
| Constraints | constraint_definitions, constraint_violations |
| Generation | generation_configurations, generation_jobs, generation_results |
| Governance | schedule_approvals, notifications, audit_logs |
| Exchange | import_jobs, export_jobs |

Timetable active/published pointers are circular foreign keys installed after both
tables exist on PostgreSQL. A revision column supports optimistic concurrency.
Version numbers are unique per timetable; session identifiers are unique per
section/version. Checks enforce capacity, group size, date order, valid periods
and exactly one availability owner.

Availability intentionally uses a single foreign-key-enforced table rather than
four duplicated tables. LecturerAvailability and StudentGroupAvailability are
domain aliases. Room features are normalized; required feature names live on
section inputs. Generic requirement/configuration tables are extension points;
scheduling currently uses the explicit section fields and supported constraint
codes. They do not execute arbitrary JSON-defined rules.

Foreign keys protect referenced data. Active/status fields archive supported
resources. Session/version-owned links cascade appropriately. There is no API
for deleting timetable history or modifying audit logs. Database operators remain
trusted. The populated SQLite migration check verifies preservation of departments
and their referenced groups when adding university links.
