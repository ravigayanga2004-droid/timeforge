import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  ChevronDown,
  Download,
  GitBranch,
  GripVertical,
  LockKeyhole,
  Play,
  Plus,
  RotateCcw,
  RotateCw,
  Save,
  SlidersHorizontal,
  Unlock,
  XCircle,
} from "lucide-react";
import { api, clock, days, download, manager, num, post, text } from "./api";
import type {
  Assignment,
  Job,
  Page,
  Row,
  Timetable,
  User,
  Version,
  Violation,
} from "./api";
import { Badge, Empty, Heading, Loading, Modal, Notice } from "./components";
import { label } from "./DataPage";
import {calendarLanes} from './calendar-layout';

const sessionKey = (a: Assignment) => `${a.section_id}:${a.session_number}`;
export default function Planner({ user }: { user: User }) {
  const client = useQueryClient();
  const [selected, setSelected] = useState(0);
  const [versionId, setVersionId] = useState(0);
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [compare, setCompare] = useState(false);
  const [notes, setNotes] = useState<string | null>(null);
  const [decision, setDecision] = useState("");
  const [busy, setBusy] = useState(false);
  const list = useQuery({
    queryKey: ["timetables"],
    queryFn: () => api<Page<Timetable>>("/timetables"),
  });
  const timetableId = selected || list.data?.items[0]?.id || 0;
  const timetable = useQuery({
    queryKey: ["timetable", timetableId],
    queryFn: () => api<Timetable>(`/timetables/${timetableId}`),
    enabled: !!timetableId,
    refetchInterval: (q) =>
      q.state.data?.jobs?.some((j) => ["QUEUED", "RUNNING"].includes(j.status))
        ? 1500
        : false,
  });
  const current = timetable.data;
  const activeVersion = versionId || current?.current_version_id || 0;
  const version = useQuery({
    queryKey: ["version", activeVersion],
    queryFn: () => api<Version>(`/versions/${activeVersion}`),
    enabled: !!activeVersion,
  });
  const refs = useQuery({
    queryKey: ["planner-refs"],
    queryFn: async () =>
      Object.fromEntries(
        await Promise.all(
          [
            "sections",
            "courses",
            "lecturers",
            "rooms",
            "student-groups",
            "time-slots",
            "terms",
            "departments",
          ].map(async (key) => [
            key,
            (await api<Page<Row>>(`/data/${key}?limit=500`)).items,
          ]),
        ),
      ),
  });
  const job = current?.jobs?.find((j) =>
    ["RUNNING", "QUEUED"].includes(j.status),
  );
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ["timetables"] });
    await client.invalidateQueries({ queryKey: ["timetable", timetableId] });
    await client.invalidateQueries({ queryKey: ["version"] });
    await client.invalidateQueries({ queryKey: ["notifications"] });
  };
  async function action(verb: string) {
    setBusy(true);
    setError("");
    try {
      await post(`/timetables/${timetableId}/workflow`, {
        action: verb,
        notes: notes ?? "",
      });
      setMessage(
        `Timetable ${verb === "publish" ? "published" : verb === "submit" ? "submitted for review" : verb === "approve" ? "approved" : verb === "reject" ? "rejected" : verb === "archive" ? "archived" : "reopened"}.`,
      );
      setNotes(null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function choose(id: number) {
    setError("");
    try {
      await post(`/timetables/${timetableId}/select`, { version_id: id });
      setVersionId(id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function jobAction(j: Job, verb: string) {
    try {
      await post(`/jobs/${j.id}/${verb}`);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    if (!job && current?.versions?.length)
      void client.invalidateQueries({ queryKey: ["version"] });
  }, [job, current?.versions?.length, client]);
  return (
    <>
      <Heading
        eyebrow="Scheduling workspace"
        title="Timetable studio"
        description="Turn academic requirements into a week that works for everyone."
        actions={
          manager(user) && (
            <>
              <button onClick={() => setCreating(true)}>
                <Plus size={16} />
                New timetable
              </button>
              <button
                className="primary"
                disabled={
                  !current ||
                  !!job ||
                  ["UNDER_REVIEW", "APPROVED", "ARCHIVED"].includes(
                    current.status,
                  )
                }
                onClick={() => setGenerating(true)}
              >
                <Play size={16} />
                Generate alternatives
              </button>
            </>
          )
        }
      />
      {error && <Notice error>{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      {list.isPending ? (
        <Loading />
      ) : list.error ? (
        <Notice error>{list.error.message}</Notice>
      ) : !list.data?.items.length ? (
        <Empty
          title={
            manager(user)
              ? "Your first timetable starts here"
              : "No published timetable yet"
          }
        >
          {manager(user)
            ? "Create a timetable after adding your academic term, resources and course sections."
            : "Your department will publish approved schedules here."}
        </Empty>
      ) : (
        <>
          <div className="planner-top">
            <label className="inline-field">
              Timetable
              <select
                value={timetableId}
                onChange={(e) => {
                  setSelected(Number(e.target.value));
                  setVersionId(0);
                  setMessage("");
                }}
              >
                {list.data.items.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
            {current && <Badge value={current.status} />}
            <span className="spacer" />
            {current?.versions && (
              <label className="inline-field">
                Version
                <select
                  value={activeVersion}
                  onChange={(e) => setVersionId(Number(e.target.value))}
                >
                  {current.versions.map((v) => (
                    <option value={v.id} key={v.id}>
                      v{v.version_number} · {v.score} penalty
                      {v.id === current.current_version_id ? " · Active" : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {manager(user) && !!current?.versions?.length && (
              <button onClick={() => setCompare(!compare)}>
                <GitBranch size={16} />
                {compare ? "Hide comparison" : "Compare"}
              </button>
            )}
          </div>
          {job && (
            <div className="job-card">
              <div>
                <span className="eyebrow">Generation #{job.id}</span>
                <h3>{job.stage}</h3>
                <p className="muted">
                  CP-SAT is checking your academic requirements.
                </p>
              </div>
              <progress
                value={job.progress}
                max={100}
                aria-label="Generation progress"
              />
              <strong>{job.progress}%</strong>
              <button onClick={() => void jobAction(job, "cancel")}>
                <XCircle size={15} />
                Cancel
              </button>
            </div>
          )}
          {current?.jobs?.[0] &&
            ["FAILED", "CANCELLED"].includes(current.jobs[0].status) && (
              <Notice error>
                {current.jobs[0].error_message || "Generation was cancelled."}{" "}
                <button
                  onClick={() => void jobAction(current.jobs[0], "retry")}
                >
                  Retry generation
                </button>
              </Notice>
            )}
          {compare && current && (
            <div className="alternatives">
              {current.versions.map((v) => (
                <article
                  className={`panel alternative ${v.id === current.current_version_id ? "selected" : ""}`}
                  key={v.id}
                >
                  <div className="between">
                    <span className="eyebrow">
                      Alternative · v{v.version_number}
                    </span>
                    <Badge
                      value={
                        v.id === current.current_version_id
                          ? "active"
                          : v.status
                      }
                    />
                  </div>
                  <strong className="score">
                    {v.score}
                    <small>total penalty · lower is better</small>
                  </strong>
                  <dl>
                    <div>
                      <dt>Hard conflicts</dt>
                      <dd>{v.hard_violations}</dd>
                    </div>
                    <div>
                      <dt>Soft penalties</dt>
                      <dd>{v.soft_violations}</dd>
                    </div>
                    <div>
                      <dt>Room utilization</dt>
                      <dd>{v.metrics.room_utilization}%</dd>
                    </div>
                    <div>
                      <dt>Sessions</dt>
                      <dd>{v.metrics.session_count}</dd>
                    </div>
                  </dl>
                  <div className="row-actions">
                    <button onClick={() => setVersionId(v.id)}>Inspect</button>
                    <button
                      className="primary"
                      disabled={
                        v.id === current.current_version_id ||
                        !!job ||
                        ["UNDER_REVIEW", "APPROVED", "ARCHIVED"].includes(
                          current.status,
                        )
                      }
                      onClick={() => void choose(v.id)}
                    >
                      Make active
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
          {version.isPending && activeVersion ? (
            <Loading />
          ) : version.error ? (
            <Notice error>{version.error.message}</Notice>
          ) : version.data && current && refs.data ? (
            <CalendarEditor
              key={`${timetableId}:${activeVersion}`}
              user={user}
              timetable={current}
              version={version.data}
              refs={refs.data}
              onSaved={async (id) => {
                setVersionId(id);
                await refresh();
              }}
            />
          ) : (
            !job && (
              <Empty title="Ready when you are">
                Generate timetable alternatives using your department's course
                requirements and availability.
              </Empty>
            )
          )}
          {manager(user) && current?.current_version_id && (
            <section className="panel workflow">
              <div>
                <span className="eyebrow">Approval workflow</span>
                <h3>Ready for the next step?</h3>
                <p className="muted">
                  Submission, approval and publication always recheck hard
                  constraints.
                </p>
              </div>
              <div className="row-actions">
                {["DRAFT", "GENERATED", "REJECTED"].includes(
                  current.status,
                ) && (
                  <button
                    className="primary"
                    onClick={() => {
                      setDecision("submit");
                      setNotes("");
                    }}
                  >
                    Submit for review
                  </button>
                )}
                {user.role === "admin" && current.status === "UNDER_REVIEW" && (
                  <>
                    <button
                      className="primary"
                      onClick={() => {
                        setDecision("approve");
                        setNotes("");
                      }}
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => {
                        setDecision("reject");
                        setNotes("");
                      }}
                    >
                      Reject
                    </button>
                  </>
                )}
                {user.role === "admin" && current.status === "APPROVED" && (
                  <button
                    className="primary"
                    onClick={() => {
                      setDecision("publish");
                      setNotes("");
                    }}
                  >
                    Publish timetable
                  </button>
                )}
                {!["GENERATING", "UNDER_REVIEW", "ARCHIVED"].includes(
                  current.status,
                ) && (
                  <button
                    onClick={() => {
                      setDecision("archive");
                      setNotes("");
                    }}
                  >
                    Archive
                  </button>
                )}
                {user.role === "admin" && current.status === "ARCHIVED" && (
                  <button
                    onClick={() => {
                      setDecision("reopen");
                      setNotes("");
                    }}
                  >
                    Reopen
                  </button>
                )}
              </div>
            </section>
          )}
          {!!current?.approvals?.length && (
            <details className="panel history">
              <summary>
                Decision history · {current.approvals.length} events
              </summary>
              {current.approvals.map((a) => (
                <p key={a.id}>
                  <Badge value={text(a, "decision")} />{" "}
                  {text(a, "notes") || "No notes"}{" "}
                  <small className="muted">{text(a, "created_at")}</small>
                </p>
              ))}
            </details>
          )}
        </>
      )}
      {creating && refs.data && (
        <CreateTimetable
          refs={refs.data}
          onClose={() => setCreating(false)}
          onCreated={async (id) => {
            setSelected(id);
            setCreating(false);
            setVersionId(0);
            await refresh();
          }}
        />
      )}
      {generating && current && refs.data && (
        <GenerateDialog
          timetable={current}
          refs={refs.data}
          onClose={() => setGenerating(false)}
          onStarted={async () => {
            setGenerating(false);
            setVersionId(0);
            await refresh();
          }}
        />
      )}
      {notes !== null && (
        <Modal
          title={`${decision.charAt(0).toUpperCase() + decision.slice(1)} timetable`}
          onClose={() => setNotes(null)}
        >
          <p>
            Decision notes are recorded in the audit trail. Rejection,
            reopening, and publication with soft violations require notes.
          </p>
          {error && <Notice error>{error}</Notice>}
          <label className="form-field">
            Decision notes
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              maxLength={2000}
            />
          </label>
          <div className="form-footer">
            <button onClick={() => setNotes(null)}>Cancel</button>
            <button
              className="primary"
              disabled={busy}
              onClick={() => void action(decision)}
            >
              Confirm {decision}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
function CreateTimetable({
  refs,
  onClose,
  onCreated,
}: {
  refs: Record<string, Row[]>;
  onClose: () => void;
  onCreated: (id: number) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [termId, setTermId] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function create() {
    setBusy(true);
    try {
      const term = refs.terms.find((t) => t.id === termId);
      const result = await post<Timetable>("/timetables", {
        name,
        term_id: termId,
        department_id: num(term, "department_id"),
      });
      await onCreated(result.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Create a timetable" onClose={onClose}>
      {error && <Notice error>{error}</Notice>}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void create();
        }}
      >
        <label className="form-field">
          Timetable name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={160}
          />
        </label>
        <label className="form-field">
          Academic term
          <select
            value={termId}
            aria-label="Academic term"
            onChange={(e) => setTermId(Number(e.target.value))}
            required
          >
            <option value="">Choose a term</option>
            {refs.terms
              .filter((t) => t.status !== "archived")
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {label(t)}
                </option>
              ))}
          </select>
        </label>
        <div className="form-footer">
          <button className="primary" disabled={busy}>
            Create timetable
          </button>
        </div>
      </form>
    </Modal>
  );
}
function GenerateDialog({
  timetable,
  refs,
  onClose,
  onStarted,
}: {
  timetable: Timetable;
  refs: Record<string, Row[]>;
  onClose: () => void;
  onStarted: () => Promise<void>;
}) {
  const [config, setConfig] = useState({
    alternatives: 3,
    time_limit: 30,
    random_seed: 42,
    optimize: true,
    respect_locked: true,
    section_ids: [] as number[],
    room_ids: [] as number[],
    slot_ids: [] as number[],
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const count = refs.sections.filter(
    (s) => num(s, "term_id") === timetable.term_id && s.status === "active",
  ).length;
  async function start() {
    setBusy(true);
    try {
      await post(`/timetables/${timetable.id}/generate`, config);
      await onStarted();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Generate timetable alternatives" onClose={onClose}>
      <div className="generation-summary">
        <CalendarDays size={24} />
        <div>
          <strong>{count} active sections</strong>
          <p>
            {refs.rooms.filter((r) => r.is_active).length} rooms ·{" "}
            {refs["time-slots"].filter((s) => s.is_active).length} periods
          </p>
        </div>
      </div>
      <p>
        Hard constraints are always enforced. Lower soft-constraint penalties
        indicate a better fit. The solver returns fewer alternatives if the
        scope has limited feasible choices.
      </p>
      {error && <Notice error>{error}</Notice>}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void start();
        }}
      >
        <div className="form-grid">
          {(["alternatives", "time_limit", "random_seed"] as const).map(
            (key) => (
              <label className="form-field" key={key}>
                {key === "time_limit"
                  ? "Total search budget (seconds)"
                  : key === "random_seed"
                    ? "Random seed"
                    : "Alternatives"}
                <input
                  type="number"
                  value={config[key]}
                  min={key === "random_seed" ? 0 : 1}
                  max={
                    key === "alternatives"
                      ? 8
                      : key === "time_limit"
                        ? 120
                        : 2147483647
                  }
                  onChange={(e) =>
                    setConfig({ ...config, [key]: Number(e.target.value) })
                  }
                />
              </label>
            ),
          )}
        </div>
        <label className="check-field">
          <input
            type="checkbox"
            checked={config.optimize}
            onChange={(e) =>
              setConfig({ ...config, optimize: e.target.checked })
            }
          />
          Optimize soft constraints
        </label>
        <label className="check-field">
          <input
            type="checkbox"
            checked={config.respect_locked}
            onChange={(e) =>
              setConfig({ ...config, respect_locked: e.target.checked })
            }
          />
          Preserve locked sessions
        </label>
        <details>
          <summary>Limit generation scope</summary>
          <p className="muted">
            Leave selections empty to include all eligible records.
          </p>
          {(
            [
              { field: "section_ids", entity: "sections" },
              { field: "room_ids", entity: "rooms" },
              { field: "slot_ids", entity: "time-slots" },
            ] as const
          ).map(({ field, entity }) => (
            <label className="form-field" key={field}>
              {entity}
              <select
                multiple
                value={config[field].map(String)}
                aria-label={entity}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    [field]: Array.from(e.target.selectedOptions, (o) =>
                      Number(o.value),
                    ),
                  })
                }
              >
                {refs[entity]
                  .filter(
                    (r) =>
                      entity !== "sections" ||
                      num(r, "term_id") === timetable.term_id,
                  )
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {label(r)}
                    </option>
                  ))}
              </select>
            </label>
          ))}
        </details>
        <div className="form-footer">
          <span className="muted">CP-SAT · reproducible seed</span>
          <button className="primary" disabled={busy || !count}>
            <Play size={16} />
            {busy ? "Starting…" : "Start generation"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function CalendarEditor({
  user,
  timetable,
  version,
  refs,
  onSaved,
}: {
  user: User;
  timetable: Timetable;
  version: Version;
  refs: Record<string, Row[]>;
  onSaved: (id: number) => Promise<void>;
}) {
  const original = version.sessions ?? [];
  const [history, setHistory] = useState<Assignment[][]>([original]);
  const [position, setPosition] = useState(0);
  const [editing, setEditing] = useState<Assignment | null>(null);
  const [view, setView] = useState("week");
  const [filterType, setFilterType] = useState("");
  const [filterId, setFilterId] = useState(0);
  const [day, setDay] = useState(-1);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState(false);
  const [dragging, setDragging] = useState("");
  const [reporting, setReporting] = useState(false);
  const [issue, setIssue] = useState("");
  const sessions = history[position];
  const dirty = JSON.stringify(sessions) !== JSON.stringify(original);
  const editable =
    manager(user) &&
    version.id === timetable.current_version_id &&
    !["GENERATING", "UNDER_REVIEW", "APPROVED", "ARCHIVED"].includes(
      timetable.status,
    );
  const [preview, setPreview] = useState<{
    valid: boolean;
    violations: Violation[];
    suggestions: Assignment[];
  } | null>(null);
  useEffect(() => {
    if (!manager(user)) return;
    let alive = true;
    const timer = setTimeout(() => {
      void post<{
        valid: boolean;
        violations: Violation[];
        suggestions: Assignment[];
      }>(`/timetables/${timetable.id}/preview`, {
        base_version_id: version.id,
        sessions,
        allow_draft_conflicts: false,
      })
        .then((result) => {
          if (alive) setPreview(result);
        })
        .catch((e) => {
          if (alive) setError((e as Error).message);
        });
    }, 350);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [sessions, timetable.id, version.id, user]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function change(next: Assignment[]) {
    setHistory([...history.slice(0, position + 1), next]);
    setPosition(position + 1);
    setPreview(null);
  }
  function update(a: Assignment) {
    change(sessions.map((x) => (sessionKey(x) === sessionKey(a) ? a : x)));
    setEditing(null);
  }
  async function save() {
    setSaving(true);
    setError("");
    try {
      const v = await post<Version>(`/timetables/${timetable.id}/edit`, {
        base_version_id: version.id,
        sessions,
        allow_draft_conflicts: draft,
      });
      await onSaved(v.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  async function exportFile(format: string, report = "schedule") {
    try {
      const filters = new URLSearchParams({ report });
      if (filterType && filterId) filters.set(filterType, String(filterId));
      await download(
        `/versions/${version.id}/export/${format}?${filters}`,
        `timeforge-v${version.version_number}-${report}.${format}`,
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function drop(slot: Row) {
    if (!editable) return;
    const a = sessions.find((x) => sessionKey(x) === dragging);
    if (a && !a.is_locked)
      update({
        ...a,
        day: num(slot, "day"),
        start: num(slot, "start"),
        end: num(slot, "start") + (a.end - a.start),
      });
    setDragging("");
  }
  const section = (id: number) => refs.sections.find((s) => s.id === id);
  const course = (a: Assignment) =>
    refs.courses.find((c) => c.id === num(section(a.section_id), "course_id"));
  const room = (id: number) => refs.rooms.find((r) => r.id === id);
  const lecturer = (id: number) => refs.lecturers.find((l) => l.id === id);
  const filtered = sessions.filter(
    (a) =>
      (day === -1 || a.day === day) &&
      (!filterId ||
        (filterType === "room_id" && a.room_id === filterId) ||
        (filterType === "lecturer_id" && a.lecturer_id === filterId) ||
        (filterType === "section_id" && a.section_id === filterId) ||
        (filterType === "group_id" &&
          (section(a.section_id)?.group_ids as number[] | undefined)?.includes(
            filterId,
          ))),
  );
  const lanes=calendarLanes(filtered);
  const violations = preview?.violations ?? version.violations ?? [];
  const hard = violations.filter((v) => v.severity === "hard");
  const soft = violations.filter((v) => v.severity === "soft");
  const badKeys = new Set(hard.flatMap((v) => v.related_sessions));
  const slots = refs["time-slots"].filter((s) => s.is_active);
  const start = Math.min(
    480,
    ...slots.map((s) => num(s, "start")),
    ...filtered.map((a) => a.start),
  );
  const end = Math.max(
    1020,
    ...slots.map((s) => num(s, "end")),
    ...filtered.map((a) => a.end),
  );
  const visibleDays =
    day >= 0
      ? [day]
      : [
          0,
          1,
          2,
          3,
          4,
          ...(slots.some((s) => num(s, "day") === 5) ||
          sessions.some((a) => a.day === 5)
            ? [5]
            : []),
          ...(slots.some((s) => num(s, "day") === 6) ||
          sessions.some((a) => a.day === 6)
            ? [6]
            : []),
        ];
  return (
    <>
      <div className="studio-status">
        <div>
          <Badge
            value={hard.length ? "conflicts found" : "no hard conflicts"}
          />
          <span>{soft.length} soft constraint penalties</span>
          <span className="muted">
            Version {version.version_number} · {sessions.length} sessions
            {dirty ? " · Unsaved changes" : ""}
          </span>
        </div>
        {manager(user) && (
          <strong>
            {soft.reduce((sum, v) => sum + v.penalty, 0)} <small>penalty</small>
          </strong>
        )}
      </div>
      <section className="panel calendar-panel">
        <div className="calendar-toolbar">
          <div className="segmented">
            {["week", "day", "list", "conflicts"].map((v) => (
              <button
                className={view === v ? "active" : ""}
                key={v}
                onClick={() => {
                  setView(v);
                  if (v === "day" && day < 0) setDay(0);
                  if (v === "week") setDay(-1);
                }}
              >
                {v[0].toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>
          <div className="row-actions">
            {editable && (
              <>
                <button
                  aria-label="Undo change"
                  disabled={position === 0}
                  onClick={() => setPosition(position - 1)}
                >
                  <RotateCcw size={15} />
                </button>
                <button
                  aria-label="Redo change"
                  disabled={position === history.length - 1}
                  onClick={() => setPosition(position + 1)}
                >
                  <RotateCw size={15} />
                </button>
                <button
                  className="primary"
                  disabled={
                    !dirty || saving || !preview || (!preview.valid && !draft)
                  }
                  onClick={() => void save()}
                >
                  <Save size={15} />
                  Save version
                </button>
              </>
            )}
            <details className="export-menu">
              <summary>
                <Download size={15} />
                Export
                <ChevronDown size={14} />
              </summary>
              <div>
                {["pdf", "ics", "csv"].map((f) => (
                  <button
                    key={f}
                    disabled={dirty}
                    onClick={() => void exportFile(f)}
                  >
                    Download {f.toUpperCase()}
                  </button>
                ))}
                {manager(user) && (
                  <>
                    <button
                      disabled={dirty}
                      onClick={() => void exportFile("pdf", "conflicts")}
                    >
                      Conflict report PDF
                    </button>
                    <button
                      disabled={dirty}
                      onClick={() => void exportFile("pdf", "generation")}
                    >
                      Generation report PDF
                    </button>
                  </>
                )}
              </div>
            </details>
            <button onClick={() => window.print()}>Print</button>
          </div>
        </div>
        <div className="filter-bar">
          <SlidersHorizontal size={16} />
          <span className="muted">Filter by</span>
          <select
            aria-label="Filter resource type"
            value={filterType}
            onChange={(e) => {
              setFilterType(e.target.value);
              setFilterId(0);
            }}
          >
            <option value="">All resources</option>
            <option value="lecturer_id">Lecturer</option>
            <option value="room_id">Room</option>
            <option value="group_id">Student group</option>
            <option value="section_id">Course section</option>
          </select>
          {filterType && (
            <select
              aria-label="Filter resource"
              value={filterId}
              onChange={(e) => setFilterId(Number(e.target.value))}
            >
              <option value="0">All</option>
              {refs[
                (
                  {
                    lecturer_id: "lecturers",
                    room_id: "rooms",
                    group_id: "student-groups",
                    section_id: "sections",
                  } as Record<string, string>
                )[filterType]
              ].map((r) => (
                <option value={r.id} key={r.id}>
                  {label(r)}
                </option>
              ))}
            </select>
          )}
          <select
            aria-label="Filter day"
            value={day}
            onChange={(e) => setDay(Number(e.target.value))}
          >
            <option value="-1">All days</option>
            {days.map((d, i) => (
              <option value={i} key={d}>
                {d}
              </option>
            ))}
          </select>
          <span className="spacer" />
          <span className="muted">{filtered.length} sessions</span>
        </div>
        {error && <Notice error>{error}</Notice>}
        {view === "conflicts" ? (
          <ConflictPanel
            violations={violations}
            suggestions={preview?.suggestions ?? []}
            apply={editable ? update : undefined}
          />
        ) : view === "list" ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {["Course", "Day & time", "Room", "Lecturer", "State"].map(
                    (h) => (
                      <th key={h}>{h}</th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr key={sessionKey(a)}>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => setEditing(a)}
                      >
                        {text(course(a), "code")} · {text(course(a), "name")}
                      </button>
                    </td>
                    <td>
                      {days[a.day]} {clock(a.start)}–{clock(a.end)}
                    </td>
                    <td>{label(room(a.room_id) ?? { id: a.room_id })}</td>
                    <td>
                      {label(lecturer(a.lecturer_id) ?? { id: a.lecturer_id })}
                    </td>
                    <td>
                      {a.is_locked
                        ? "Locked"
                        : badKeys.has(sessionKey(a))
                          ? "Conflict"
                          : "Scheduled"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="calendar-scroll">
            <div
              className="calendar"
              style={{
                gridTemplateColumns: `56px repeat(${visibleDays.length}, minmax(150px,1fr))`,
              }}
            >
              <div className="calendar-corner">Local time</div>
              {visibleDays.map((d) => (
                <div className="calendar-day" key={d}>
                  {days[d]}
                  <small>
                    {text(
                      refs.terms.find((t) => t.id === timetable.term_id),
                      "name",
                    )}
                  </small>
                </div>
              ))}
              <div className="time-axis" style={{ height: end - start }}>
                {Array.from(
                  { length: Math.ceil((end - start) / 60) + 1 },
                  (_, i) => (
                    <span style={{ top: i * 60 }} key={i}>
                      {clock(start + i * 60)}
                    </span>
                  ),
                )}
              </div>
              {visibleDays.map((d) => (
                <div
                  className="day-column"
                  style={{ height: end - start }}
                  key={d}
                >
                  {slots
                    .filter((s) => num(s, "day") === d)
                    .map((slot) => (
                      <div
                        className={`drop-slot ${dragging ? "can-drop" : ""}`}
                        style={{
                          top: num(slot, "start") - start,
                          height: num(slot, "end") - num(slot, "start"),
                        }}
                        key={slot.id}
                        onDragOver={(e) => {
                          if (editable) e.preventDefault();
                        }}
                        onDrop={(e) => {
                          e.preventDefault();
                          drop(slot);
                        }}
                        aria-label={`Drop on ${days[d]} ${clock(num(slot, "start"))}`}
                      />
                    ))}
                  {filtered
                    .filter((a) => a.day === d)
                    .map((a) => (
                      <button
                        className={`session color-${a.section_id % 6} ${badKeys.has(sessionKey(a)) ? "has-conflict" : ""}`}
                        style={{
                          top: a.start - start + 2,
                          minHeight: Math.max(42, a.end - a.start - 4),
                          left:`calc(${100*lanes[sessionKey(a)].lane/lanes[sessionKey(a)].count}% + 4px)`,
                          width:`calc(${100/lanes[sessionKey(a)].count}% - 8px)`,
                          right:'auto',
                        }}
                        key={sessionKey(a)}
                        draggable={editable && !a.is_locked}
                        onDragStart={() => setDragging(sessionKey(a))}
                        onDragEnd={() => setDragging("")}
                        onClick={() => setEditing(a)}
                        title={`${text(course(a), "name")} · ${label(lecturer(a.lecturer_id) ?? { id: a.lecturer_id })} · ${clock(a.start)}–${clock(a.end)}`}
                      >
                        <span className="session-title">
                          {text(course(a), "code") ||
                            text(section(a.section_id), "code")}
                          {a.is_locked ? (
                            <LockKeyhole size={12} />
                          ) : editable ? (
                            <GripVertical size={12} />
                          ) : null}
                        </span>
                        <span className="session-name">
                          {text(course(a), "name")}
                        </span>
                        <span>
                          {clock(a.start)}–{clock(a.end)} ·{" "}
                          {text(room(a.room_id), "code")}
                        </span>
                        <span className="session-lecturer">
                          {text(lecturer(a.lecturer_id), "name")}
                        </span>
                        {badKeys.has(sessionKey(a)) && (
                          <strong>⚠ Conflict</strong>
                        )}
                      </button>
                    ))}
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="calendar-footer">
          <span>
            <span className="legend-dot" />
            Sessions follow local campus time
          </span>
          {editable ? (
            <span>Drag to move · click for room, time and lock controls</span>
          ) : (
            <span>Published timetable · read only</span>
          )}
        </div>
      </section>
      {editable && hard.length > 0 && (
        <>
          <Notice error>
            {hard.length} hard conflicts found. Resolve them before publication.
          </Notice>
          <label className="check-field">
            <input
              type="checkbox"
              checked={draft}
              onChange={(e) => setDraft(e.target.checked)}
            />
            Allow saving these changes as a draft with conflicts
          </label>
        </>
      )}
      {manager(user) && view !== "conflicts" && (
        <details className="panel conflict-details">
          <summary>
            {hard.length
              ? "Review hard conflicts"
              : `${soft.length} soft penalties · inspect explanations`}
          </summary>
          <ConflictPanel
            violations={violations}
            suggestions={preview?.suggestions ?? []}
            apply={editable ? update : undefined}
          />
        </details>
      )}
      <div className="planner-bottom">
        <p className="muted">
          Weekly recurring schedule ·{" "}
          {text(
            refs.terms.find((t) => t.id === timetable.term_id),
            "start_date",
          )}{" "}
          –{" "}
          {text(
            refs.terms.find((t) => t.id === timetable.term_id),
            "end_date",
          )}
        </p>
        <button onClick={() => setReporting(true)}>Report an issue</button>
      </div>
      {editing && (
        <SessionDialog
          assignment={editing}
          refs={refs}
          editable={editable}
          onClose={() => setEditing(null)}
          onSave={update}
          onDelete={() => {
            change(
              sessions.filter((x) => sessionKey(x) !== sessionKey(editing)),
            );
            setEditing(null);
          }}
          onDuplicate={() => {
            const number =
              Math.max(
                ...sessions
                  .filter((x) => x.section_id === editing.section_id)
                  .map((x) => x.session_number),
              ) + 1;
            change([
              ...sessions,
              { ...editing, session_number: number, is_locked: false },
            ]);
            setEditing(null);
          }}
        />
      )}
      {reporting && (
        <Modal
          title="Report a schedule issue"
          onClose={() => setReporting(false)}
        >
          <label className="form-field">
            Describe the problem
            <textarea
              value={issue}
              onChange={(e) => setIssue(e.target.value)}
              rows={4}
              maxLength={2000}
            />
          </label>
          <button
            className="primary"
            disabled={!issue.trim()}
            onClick={() =>
              void post(`/timetables/${timetable.id}/issues`, {
                message: issue,
              })
                .then(() => {
                  setReporting(false);
                  setIssue("");
                })
                .catch((e) => setError((e as Error).message))
            }
          >
            Send to coordinator
          </button>
        </Modal>
      )}
    </>
  );
}
function ConflictPanel({
  violations,
  suggestions,
  apply,
}: {
  violations: Violation[];
  suggestions: Assignment[];
  apply?: (a: Assignment) => void;
}) {
  return (
    <div className="conflict-panel">
      {!violations.length ? (
        <Notice>
          No hard conflicts detected. All configured preferences are satisfied.
        </Notice>
      ) : (
        violations.map((v, i) => (
          <div className={`violation ${v.severity}`} key={`${v.code}-${i}`}>
            <div className="between">
              <strong>
                {v.code} ·{" "}
                {v.severity === "hard" ? "Hard constraint" : "Soft preference"}
              </strong>
              <span>{v.penalty ? `${v.penalty} penalty` : "Must resolve"}</span>
            </div>
            <p>{v.description}</p>
            <small>{v.suggestion}</small>
            {v.related_sessions.length > 0 && (
              <small>Related sessions: {v.related_sessions.join(", ")}</small>
            )}
          </div>
        ))
      )}
      {apply && suggestions.length > 0 && (
        <>
          <h4>Validated placement suggestions</h4>
          {suggestions.map((a) => (
            <button
              key={`${sessionKey(a)}-${a.day}-${a.start}-${a.room_id}`}
              onClick={() => apply(a)}
            >
              Move {sessionKey(a)} → {days[a.day]} {clock(a.start)} · room #
              {a.room_id}
            </button>
          ))}
        </>
      )}
    </div>
  );
}
function SessionDialog({
  assignment,
  refs,
  editable,
  onClose,
  onSave,
  onDelete,
  onDuplicate,
}: {
  assignment: Assignment;
  refs: Record<string, Row[]>;
  editable: boolean;
  onClose: () => void;
  onSave: (a: Assignment) => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
  const [a, setA] = useState(assignment);
  const [error, setError] = useState("");
  const slot = refs["time-slots"].find(
    (s) => num(s, "day") === a.day && num(s, "start") === a.start,
  );
  return (
    <Modal title={`Session ${sessionKey(a)}`} onClose={onClose}>
      <p className="muted">
        Changing a locked session's placement requires saving an unlocked
        version first.
      </p>
      {error && <Notice error>{error}</Notice>}
      <div className="form-grid">
        <label className="form-field">
          Time period
          <select
            value={slot?.id ?? ""}
            disabled={!editable || assignment.is_locked}
            onChange={(e) => {
              const s = refs["time-slots"].find(
                (x) => x.id === Number(e.target.value),
              );
              if (s)
                setA({
                  ...a,
                  day: num(s, "day"),
                  start: num(s, "start"),
                  end: num(s, "start") + (a.end - a.start),
                });
            }}
          >
            {refs["time-slots"]
              .filter((s) => s.is_active)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {days[num(s, "day")]} {clock(num(s, "start"))}
                </option>
              ))}
          </select>
        </label>
        <label className="form-field">
          Room
          <select
            value={a.room_id}
            disabled={!editable || assignment.is_locked}
            onChange={(e) => setA({ ...a, room_id: Number(e.target.value) })}
          >
            {refs.rooms.map((r) => (
              <option key={r.id} value={r.id}>
                {label(r)} · {num(r, "capacity")} seats
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          Lecturer
          <select
            value={a.lecturer_id}
            disabled={!editable || assignment.is_locked}
            onChange={(e) =>
              setA({ ...a, lecturer_id: Number(e.target.value) })
            }
          >
            {refs.lecturers.map((r) => (
              <option value={r.id} key={r.id}>
                {label(r)}
              </option>
            ))}
          </select>
        </label>
        <label className="check-field">
          <input
            type="checkbox"
            disabled={!editable}
            checked={a.is_locked}
            onChange={(e) => setA({ ...a, is_locked: e.target.checked })}
          />
          {a.is_locked ? <LockKeyhole size={15} /> : <Unlock size={15} />}Lock
          this session
        </label>
      </div>
      <label className="form-field">
        Notes
        <textarea
          maxLength={1000}
          disabled={!editable}
          value={a.notes}
          onChange={(e) => setA({ ...a, notes: e.target.value })}
        />
      </label>
      {editable && (
        <div className="form-footer">
          <div className="row-actions">
            <button disabled={assignment.is_locked} onClick={onDelete}>
              Delete
            </button>
            <button disabled={a.session_number >= 20} onClick={onDuplicate}>
              Duplicate
            </button>
          </div>
          <button
            className="primary"
            onClick={() => {
              if (a.end > 1440) {
                setError("Session must finish before midnight");
                return;
              }
              onSave(a);
            }}
          >
            Apply & validate
          </button>
        </div>
      )}
    </Modal>
  );
}
