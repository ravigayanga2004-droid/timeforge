# Data exchange

Academic CSV import supports every registry collection, including courses,
lecturers, rooms, student groups, sections and availability. Download its template
before importing. The encoding is UTF-8, optionally with BOM. Header names must
match schema fields; all required fields must be present. Arrays/objects use JSON,
such as `[1,2]` for group_ids and `["Projector"]` for required_features. IDs refer
to existing records; no name-based guessing occurs.

Each file is limited to 2 MB and 500 rows. Duplicate headers, mismatched row widths,
binary/NUL content, unknown headers and invalid references are rejected. Validation
runs in nested transactions. Dry runs roll back all record writes, preserve an
import-history entry and show the first 20 valid rows with row errors. Any invalid
row blocks committing the entire import. Explicit partial import is not offered.
These bounded files run synchronously; there is no advertised unbounded bulk job.

Reference exports use schema columns and escape spreadsheet formula prefixes.
Files above 500 records are rejected; use the paginated authorized API for bulk
extraction. Reimport creates records, not upserts, so existing unique codes must be
handled deliberately. CSV templates show nullable/optional fields through the UI
schema; leaving an optional column blank uses its default.

Timetable exports include term, version, timezone and export timestamp. PDF uses
repeatable table headers, wrapped cells and page numbers. ICS includes stable UIDs,
UTC timestamps and explicit recurrence dates restricted to the academic term.
Each occurrence converts campus local time through IANA timezone rules; explicit
RDATE values preserve local wall time across daylight-saving changes. University
timezone overrides the deployment default. CSV contains readable schedule rows.

Exports honor personal lecturer/group scope and department/version access. Report
types are schedule, conflicts and generation; conflict/generation reports require
coordinator/admin access. Filters support lecturer_id, group_id and room_id. Every
export creates an audit event and ExportJob record.

Existing timetable assignments can be loaded through the validated `/edit` JSON
API, with complete new-version validation. A dedicated timetable-assignment CSV
parser/preview UI is deferred; readable schedule CSV is not a round-trip assignment
format. This avoids silently mapping course/room names to potentially wrong IDs.
Large imports and exports should be moved to durable jobs before increasing limits.
For non-Latin scripts, configure and test an appropriate PDF font before deployment;
the bundled PDF styles currently rely on standard ReportLab fonts.
