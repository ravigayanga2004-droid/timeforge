import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, post, text, title } from "./api";
import type { Page, Row, Schema, Timetable, User, Version } from "./api";
import { Badge, Empty, Heading, Loading, Modal, Notice } from "./components";
import { RecordForm } from "./DataPage";

export function Notifications() {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const q = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<{ items: Row[] }>("/notifications"),
    refetchInterval: 15000,
  });
  return (
    <>
      <Heading
        eyebrow="Your workspace"
        title="Notifications"
        description="Generation results, review decisions and schedule changes."
      />
      {error && <Notice error>{error}</Notice>}
      {q.isPending ? (
        <Loading />
      ) : q.error ? (
        <Notice error>{q.error.message}</Notice>
      ) : !q.data?.items.length ? (
        <Empty title="You're all caught up">
          New scheduling activity will appear here.
        </Empty>
      ) : (
        <section className="panel notifications-list">
          {q.data.items.map((n) => (
            <article key={n.id} className={n.is_read ? "read" : ""}>
              <span className="notification-dot" />
              <div>
                <p>{text(n, "message")}</p>
                <small className="muted">
                  {new Date(text(n, "created_at") + "Z").toLocaleString(
                    "en-GB",
                    { timeZone: "Asia/Colombo" },
                  )}
                </small>
              </div>
              {!n.is_read && (
                <button
                  onClick={() =>
                    void post(`/notifications/${n.id}/read`)
                      .then(() =>
                        client.invalidateQueries({
                          queryKey: ["notifications"],
                        }),
                      )
                      .catch((e) => setError((e as Error).message))
                  }
                >
                  Mark as read
                </button>
              )}
            </article>
          ))}
        </section>
      )}
    </>
  );
}
export function Audit() {
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState("");
  const q = useQuery({
    queryKey: ["audit", offset, action],
    queryFn: () =>
      api<Page<Row>>(
        `/audit?limit=50&offset=${offset}&action=${encodeURIComponent(action)}`,
      ),
  });
  return (
    <>
      <Heading
        eyebrow="Administration"
        title="Audit trail"
        description="Read-only records of changes, decisions and data access."
      />
      <section className="panel">
        <div className="table-toolbar">
          <label className="inline-field">
            Action filter
            <input
              value={action}
              placeholder="e.g. generation_requested"
              onChange={(e) => {
                setAction(e.target.value);
                setOffset(0);
              }}
            />
          </label>
          <span>{q.data?.total ?? 0} events</span>
        </div>
        {q.isPending ? (
          <Loading />
        ) : q.error ? (
          <Notice error>{q.error.message}</Notice>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {["Time (UTC)", "Actor", "Action", "Entity", "Details"].map(
                    (h) => (
                      <th key={h}>{h}</th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {q.data?.items.map((row) => (
                  <tr key={row.id}>
                    <td>{text(row, "created_at")}</td>
                    <td>#{text(row, "actor_id")}</td>
                    <td>{text(row, "action")}</td>
                    <td>
                      {text(row, "entity_type")} #{text(row, "entity_id")}
                    </td>
                    <td>
                      <details>
                        <summary>Inspect event</summary>
                        <pre>{JSON.stringify(row.details, null, 2)}</pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <button disabled={!offset} onClick={() => setOffset(offset - 50)}>
            Previous
          </button>
          <span>
            {offset + 1}–{Math.min(offset + 50, q.data?.total ?? 0)}
          </span>
          <button
            disabled={offset + 50 >= (q.data?.total ?? 0)}
            onClick={() => setOffset(offset + 50)}
          >
            Next
          </button>
        </div>
      </section>
    </>
  );
}
const userSchema: Schema = {
  properties: {
    name: { type: "string", minLength: 1, maxLength: 160 },
    email: { type: "string", format: "email" },
    password: { type: "string", minLength: 12, maxLength: 128 },
    role: {
      type: "string",
      enum: ["admin", "coordinator", "lecturer", "student", "viewer"],
      default: "viewer",
    },
    department_id: { anyOf: [{ type: "integer" }, { type: "null" }] },
    group_id: { anyOf: [{ type: "integer" }, { type: "null" }] },
    is_active: { type: "boolean", default: true },
  },
  required: ["name", "email", "password", "role"],
};
export function Users() {
  const client = useQueryClient();
  const [editor, setEditor] = useState<Row | null | false>(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ["users", offset],
    queryFn: () => api<Page<Row>>(`/users?offset=${offset}&limit=50`),
  });
  const refs = useQuery<Record<string, Row[]>>({
    queryKey: ["user-refs"],
    queryFn: async () =>
      Object.fromEntries(
        await Promise.all(
          ["departments", "student-groups"].map(async (k) => [
            k,
            (await api<Page<Row>>(`/data/${k}?limit=500`)).items,
          ]),
        ),
      ),
  });
  async function save(data: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      await api(`/users${editor ? `/${editor.id}` : ""}`, {
        method: editor ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      setEditor(false);
      await client.invalidateQueries({ queryKey: ["users"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const schema = editor
    ? {
        properties: Object.fromEntries(
          Object.entries(userSchema.properties).filter(
            ([k]) => !["email", "password"].includes(k),
          ),
        ),
        required: ["name", "role"],
      }
    : userSchema;
  return (
    <>
      <Heading
        eyebrow="Administration"
        title="Users & access"
        description="Assign the least access each person needs. Role changes invalidate existing sessions."
        actions={
          <button
            className="primary"
            onClick={() => {
              setError("");
              setEditor(null);
            }}
          >
            Add user
          </button>
        }
      />
      <section className="panel">
        {q.isPending ? (
          <Loading />
        ) : q.error ? (
          <Notice error>{q.error.message}</Notice>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "Name",
                    "Email",
                    "Role",
                    "Department",
                    "Status",
                    "Actions",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {q.data?.items.map((u) => (
                  <tr key={u.id}>
                    <td>{text(u, "name")}</td>
                    <td>{text(u, "email")}</td>
                    <td>
                      <Badge value={text(u, "role")} />
                    </td>
                    <td>
                      {String(
                        refs.data?.departments.find(
                          (d) => d.id === u.department_id,
                        )?.name || "All departments",
                      )}
                    </td>
                    <td>
                      <Badge value={u.is_active ? "active" : "disabled"} />
                    </td>
                    <td>
                      <button
                        onClick={() => {
                          setError("");
                          setEditor(u);
                        }}
                      >
                        Edit access
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <button disabled={!offset} onClick={() => setOffset(offset - 50)}>
            Previous
          </button>
          <span>{q.data?.total ?? 0} users</span>
          <button
            disabled={offset + 50 >= (q.data?.total ?? 0)}
            onClick={() => setOffset(offset + 50)}
          >
            Next
          </button>
        </div>
      </section>
      {editor !== false && (
        <Modal
          title={editor ? "Edit user access" : "Create user"}
          onClose={() => setEditor(false)}
        >
          {error && <Notice error>{error}</Notice>}
          <RecordForm
            schema={schema}
            record={editor ?? undefined}
            onSave={save}
            busy={busy}
            rows={refs.data}
          />
        </Modal>
      )}
    </>
  );
}
export function Analytics({ user }: { user: User }) {
  const [selected, setSelected] = useState(0);
  const q = useQuery({
    queryKey: ["analytics-timetables"],
    queryFn: () => api<Page<Timetable>>("/timetables"),
  });
  const id =
    selected || q.data?.items.find((t) => t.current_version_id)?.id || 0;
  const t = useQuery({
    queryKey: ["analytics-timetable", id],
    queryFn: () => api<Timetable>(`/timetables/${id}`),
    enabled: !!id,
  });
  const vid = t.data?.current_version_id || 0;
  const report = useQuery({
    queryKey: ["analytics", vid],
    queryFn: () => api<Version["metrics"]>(`/versions/${vid}/analytics`),
    enabled: !!vid,
  });
  const data = report.data;
  const charts = data
    ? [
        {
          title: "Room use",
          desc: "Minutes assigned to each room in this weekly version.",
          values: data.room_minutes,
        },
        {
          title: "Lecturer workload",
          desc: "Total teaching minutes per lecturer.",
          values: data.lecturer_minutes,
        },
        {
          title: "Student-group workload",
          desc: "Total class minutes per enrolled group.",
          values: data.group_minutes,
        },
        {
          title: "Soft penalty breakdown",
          desc: "Weighted penalty units. Lower totals indicate closer adherence to preferences.",
          values: data.penalties,
        },
      ]
    : [];
  return (
    <>
      <Heading
        eyebrow="Planning insights"
        title="Scheduling analytics"
        description={`Metrics for ${user.role === "student" || user.role === "lecturer" ? "your assigned sessions" : "the selected timetable version"}.`}
        actions={
          <label className="inline-field">
            Timetable
            <select
              value={id}
              onChange={(e) => setSelected(Number(e.target.value))}
            >
              {q.data?.items
                .filter((t) => t.current_version_id)
                .map((t) => (
                  <option value={t.id} key={t.id}>
                    {t.name}
                  </option>
                ))}
            </select>
          </label>
        }
      />
      {q.error || report.error ? (
        <Notice error>{q.error?.message || report.error?.message}</Notice>
      ) : q.isPending || report.isFetching ? (
        <Loading />
      ) : !data ? (
        <Empty title="No analytics yet">
          Generate or publish a timetable to see scheduling metrics.
        </Empty>
      ) : (
        <>
          <div className="stats-grid">
            {[
              { label: "Weekly sessions", value: data.session_count },
              {
                label: "Teaching hours",
                value: (data.teaching_minutes / 60).toFixed(1),
              },
              {
                label: "Room time utilization",
                value: `${data.room_utilization}%`,
              },
              {
                label: "Average capacity use",
                value: `${data.room_capacity_utilization}%`,
              },
            ].map((stat) => (
              <div className="panel stat-card" key={stat.label}>
                <span className="muted">{stat.label}</span>
                <strong>{stat.value}</strong>
              </div>
            ))}
          </div>
          <div className="analytics-grid">
            {charts.map((c) => (
              <section className="panel" key={c.title}>
                <div className="panel-heading">
                  <div>
                    <h3>{c.title}</h3>
                    <p className="muted">{c.desc}</p>
                  </div>
                </div>
                <div style={{ height: 250 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={Object.entries(c.values).map(([name, value]) => ({
                        name: title(name),
                        value,
                      }))}
                      margin={{ bottom: 25, left: 0, right: 25 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis />
                      <Tooltip />
                      <Bar
                        dataKey="value"
                        fill="#328b75"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            ))}
          </div>
          <section className="panel definitions">
            <h3>Metric definitions</h3>
            <p>
              Room time utilization is assigned session minutes divided by the
              active periods across active rooms. Capacity use is the average
              expected enrollment divided by assigned room capacity. These
              describe one weekly pattern, not total academic-term occupancy.
            </p>
            <p>
              Workload charts identify resources by their database ID. Academic
              resource pages show corresponding names. Empty rooms remain
              visible with zero assigned minutes.
            </p>
            <a href="#planner">
              Open the studio to compare versions and export the generation
              report →
            </a>
          </section>
        </>
      )}
    </>
  );
}
export function Guide() {
  return (
    <>
      <Heading
        eyebrow="TimeForge handbook"
        title="Plan a better academic week"
        description="A practical guide to the scheduling workflow."
      />
      <div className="panel definitions">
        {[
          [
            "1. Prepare the academic data",
            "Create departments, academic years, terms and buildings first. Add room features, rooms, time periods, lecturers, student groups and courses. Create sections connecting each course to a term, lecturer and enrolled groups. Time periods use minutes after midnight: 09:00 is 540.",
          ],
          [
            "2. Set constraints and availability",
            "Unavailable periods are hard constraints. Capacity, type, equipment, collisions, workload and session counts are always enforced. Preferences are soft constraints with configurable weights. Lower penalties are better. A feasible schedule can still have soft penalties.",
          ],
          [
            "3. Generate and compare",
            "Create a timetable, choose a seed, search budget and number of alternatives. Generation uses durable jobs with progress polling. Alternatives exclude previous assignments; limited feasible choices may yield fewer results. Select an alternative as the active version.",
          ],
          [
            "4. Refine the calendar",
            "Drag sessions or open them to change room, time and lock state. The server checks every change. Undo and redo work before saving. Saving creates a new version. Unlock and save a locked session before moving it. Drafts with hard conflicts cannot be submitted or published.",
          ],
          [
            "5. Review and publish",
            "Coordinators submit the active version. Administrators approve or reject it. Approval is required before publication. Publication notes explain accepted soft penalties. Students and lecturers see assigned published sessions. New drafts preserve the previous published snapshot.",
          ],
          [
            "6. Exchange data",
            "CSV templates show accepted columns. Use JSON arrays for group IDs and feature lists. Validate and preview before importing; an invalid row blocks the whole file. Exports respect permissions. ICS recurrence dates stay within the term and preserve campus local time.",
          ],
          [
            "Privacy",
            "TimeForge stores account details, academic records, resource availability and an audit trail. Access is limited by role and department. Passwords use Argon2id hashing. Session cookies are HTTP-only and expire. Contact your university administrator about corrections or retention.",
          ],
        ].map(([heading, body]) => (
          <section key={heading}>
            <h2>{heading}</h2>
            <p>{body}</p>
          </section>
        ))}
      </div>
    </>
  );
}
