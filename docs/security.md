# Security model

| Capability | Admin | Coordinator | Lecturer | Student | Viewer |
|---|---|---|---|---|---|
| Institution/global resource writes | Yes | No | No | No | No |
| Department academic/course writes | Yes | Own department | No | No | No |
| Availability writes | Yes | Own department | Own lecturer only | No | No |
| Generate/edit/submit | Yes | Own department | No | No | No |
| Approve/reject/publish | Yes | No | No | No | No |
| Users/audit | Yes | No | No | No | No |
| Published views/exports | All scope | Own department | Assigned sessions | Enrolled group | Own department |

Built-in permissions are enforced by reusable require_auth, require_role,
require_permission and require_department_access helpers. Role/Permission tables
describe the built-in vocabulary; arbitrary custom permission editing is not
implemented. Every resource lookup checks scope. Reader listings filter unpublished
academic data and redact other lecturers' contact/account fields.

Passwords use Argon2id. High-entropy session/reset tokens are stored only as SHA256
digests. Cookies use HttpOnly for the session, SameSite=Lax, configured Secure and
fixed expiry. Authenticated mutations require a matching CSRF header. Login/reset
origin checks supplement CORS and host restrictions. Logout, password reset and
role/status changes invalidate sessions. Reset tokens expire after 30 minutes and
are consumed once. Password changes revoke all sessions.

Database-backed login throttling tracks hashed IP/account keys and imposes
progressive retry delays; no blocking sleep holds an API worker. Unknown accounts
perform a dummy hash verification. Reset requests return a generic response and
have a per-IP cooldown. SQL parameters, strict inputs, React escaping, upload bounds
and formula-safe CSV output reduce common injection risks. Error responses never
include database exceptions, stack traces or credentials. Sensitive input values
are omitted from validation-error responses.

Audit events contain explicitly selected non-secret fields and before/after
summaries. There is no audit mutation API. Protect audit storage against privileged
database tampering with separate operational controls and backups. Authentication
tokens and passwords are never audit metadata.

Production requirements: TLS, COOKIE_SECURE=true, correct ALLOWED_ORIGIN/PUBLIC_URL
and TRUSTED_HOSTS, protected database/Redis, encrypted backups, least-privilege DB
users, SMTP or trusted mail-spool delivery, dependency review and external security
testing. Password recovery currently uses a protected file mail adapter; do not
expose its directory through the web server. Files require operational retention.

No MFA/SSO, external penetration test, fine-grained custom permission editor or
trusted-proxy IP configuration is claimed. IP throttling uses the direct peer;
deploy behind a correctly configured reverse proxy. Additional gateway controls
are appropriate for a public institutional installation.
