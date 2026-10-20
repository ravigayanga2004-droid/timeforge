import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Save } from "lucide-react";
import { api, clock, days, num, post, text } from "./api";
import type { Page, Row, User } from "./api";
import { Heading, Loading, Notice } from "./components";
import { label } from "./DataPage";
export default function Availability({ user }: { user: User }) {
  const client = useQueryClient();
  const [term, setTerm] = useState(0);
  const [entity, setEntity] = useState(
    user.role === "lecturer" ? "lecturer_id" : "room_id",
  );
  const [owner, setOwner] = useState(0);
  const [kind, setKind] = useState("unavailable");
  const [reason, setReason] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [sourceDay, setSourceDay] = useState(0);
  const [targetDay, setTargetDay] = useState(1);
  const refs = useQuery<Record<string, Row[]>>({
    queryKey: ["availability-refs"],
    queryFn: async () =>
      Object.fromEntries(
        await Promise.all(
          [
            "terms",
            "lecturers",
            "rooms",
            "student-groups",
            "sections",
            "time-slots",
            "availability",
          ].map(async (key) => [
            key,
            (await api<Page<Row>>(`/data/${key}?limit=500`)).items,
          ]),
        ),
      ),
  });
  const targetEntity = (
    {
      lecturer_id: "lecturers",
      room_id: "rooms",
      group_id: "student-groups",
      section_id: "sections",
    } as Record<string, string>
  )[entity];
  const owners =
    refs.data?.[targetEntity]?.filter(
      (r) => user.role !== "lecturer" || num(r, "user_id") === user.id,
    ) ?? [];
  const termId = term || refs.data?.terms[0]?.id || 0;
  const ownerId = owner || owners[0]?.id || 0;
  const activeTerm = refs.data?.terms.find((t) => t.id === termId);
  const existing =
    refs.data?.availability.filter(
      (a) => num(a, "term_id") === termId && num(a, entity) === ownerId,
    ) ?? [];
  const slots = refs.data?.["time-slots"].filter((s) => s.is_active) ?? [];
  const times = [...new Set(slots.map((s) => num(s, "start")))].sort(
    (a, b) => a - b,
  );
  function toggle(id: number) {
    setSelected((old) => {
      const next = new Set(old);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  async function save(copy = false) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      let rows = Array.from(selected, (id) => ({
        department_id: num(activeTerm, "department_id"),
        term_id: termId,
        [entity]: ownerId,
        slot_id: id,
        kind,
        reason,
      }));
      if (copy) {
        rows = existing
          .filter((r) => {
            const s = slots.find((s) => s.id === num(r, "slot_id"));
            return s && num(s, "day") === sourceDay;
          })
          .flatMap((r) => {
            const s = slots.find((s) => s.id === num(r, "slot_id"));
            const dest = slots.find(
              (d) =>
                num(d, "day") === targetDay &&
                num(d, "start") === num(s, "start") &&
                num(d, "end") === num(s, "end"),
            );
            return dest
              ? [
                  {
                    department_id: num(activeTerm, "department_id"),
                    term_id: termId,
                    [entity]: ownerId,
                    slot_id: dest.id,
                    kind: text(r, "kind"),
                    reason: text(r, "reason"),
                  },
                ]
              : [];
          });
      }
      if (!rows.length) {
        setError(
          "Select periods or choose a source day with existing availability.",
        );
        return;
      }
      await post("/availability/bulk", { records: rows });
      setSelected(new Set());
      setMessage(`${rows.length} availability rules saved.`);
      await client.invalidateQueries({ queryKey: ["availability-refs"] });
      await client.invalidateQueries({ queryKey: ["data"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="Resource planning"
        title="Availability"
        description="Give the scheduling engine a clear picture of when people and spaces are available."
        actions={
          <button
            className="primary"
            disabled={!selected.size || busy || !ownerId}
            onClick={() => void save()}
          >
            <Save size={16} />
            Apply to {selected.size} periods
          </button>
        }
      />
      {error && <Notice error>{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      {refs.isPending ? (
        <Loading />
      ) : refs.error ? (
        <Notice error>{refs.error.message}</Notice>
      ) : (
        <>
          <section className="panel availability-controls">
            <label className="form-field">
              Academic term
              <select
                value={termId}
                onChange={(e) => {
                  setTerm(Number(e.target.value));
                  setSelected(new Set());
                }}
              >
                {refs.data?.terms.map((t) => (
                  <option key={t.id} value={t.id}>
                    {label(t)}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Resource type
              <select
                value={entity}
                onChange={(e) => {
                  setEntity(e.target.value);
                  setOwner(0);
                  setSelected(new Set());
                }}
              >
                {(user.role === "lecturer"
                  ? ["lecturer_id"]
                  : ["lecturer_id", "room_id", "group_id", "section_id"]
                ).map((k) => (
                  <option value={k} key={k}>
                    {k.replace("_id", "").replace("group", "Student group")}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Resource
              <select
                value={ownerId}
                onChange={(e) => {
                  setOwner(Number(e.target.value));
                  setSelected(new Set());
                }}
              >
                {owners.map((r) => (
                  <option key={r.id} value={r.id}>
                    {label(r)}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Set selected periods to
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                {["unavailable", "preferred", "discouraged", "available"].map(
                  (k) => (
                    <option key={k}>{k}</option>
                  ),
                )}
              </select>
            </label>
            <label className="form-field">
              Reason
              <input
                value={reason}
                maxLength={500}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Research supervision"
              />
            </label>
          </section>
          <section className="panel availability-panel">
            <div className="table-toolbar">
              <strong>Select periods to edit</strong>
              <div className="legend">
                <span>⊘ Unavailable</span>
                <span>★ Preferred</span>
                <span>△ Discouraged</span>
                <span>○ Available</span>
              </div>
            </div>
            <div className="table-scroll">
              <table className="availability-grid">
                <thead>
                  <tr>
                    <th>Time</th>
                    {days.map((d, i) => (
                      <th key={d}>
                        <button
                          className="text-button"
                          onClick={() =>
                            setSelected(
                              new Set(
                                slots
                                  .filter((s) => num(s, "day") === i)
                                  .map((s) => s.id),
                              ),
                            )
                          }
                        >
                          {d.slice(0, 3)} · select
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {times.map((t) => (
                    <tr key={t}>
                      <th>{clock(t)}</th>
                      {days.map((d, i) => {
                        const slot = slots.find(
                          (s) => num(s, "day") === i && num(s, "start") === t,
                        );
                        const rule = existing.find(
                          (r) => num(r, "slot_id") === slot?.id,
                        );
                        const state = text(rule, "kind") || "available";
                        return (
                          <td key={d}>
                            {slot ? (
                              <button
                                aria-label={`${d} ${clock(t)} ${state}`}
                                aria-pressed={selected.has(slot.id)}
                                className={`availability-cell ${state} ${selected.has(slot.id) ? "chosen" : ""}`}
                                onClick={() => toggle(slot.id)}
                              >
                                <span>
                                  {
                                    (
                                      {
                                        unavailable: "⊘",
                                        preferred: "★",
                                        discouraged: "△",
                                        available: "○",
                                      } as Record<string, string>
                                    )[state]
                                  }
                                </span>
                                <small>
                                  {selected.has(slot.id) ? "Selected" : state}
                                </small>
                              </button>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="calendar-footer">
              <span>
                Unavailability is a hard constraint. Preferences affect
                optimization scores.
              </span>
              <button onClick={() => setSelected(new Set())}>
                Clear selection
              </button>
            </div>
          </section>
          <section className="panel copy-panel">
            <div>
              <h3>Copy availability between days</h3>
              <p className="muted">
                Copy existing rules to matching periods on another day for this
                resource.
              </p>
            </div>
            <label>
              From
              <select
                value={sourceDay}
                onChange={(e) => setSourceDay(Number(e.target.value))}
              >
                {days.map((d, i) => (
                  <option value={i} key={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <label>
              To
              <select
                value={targetDay}
                onChange={(e) => setTargetDay(Number(e.target.value))}
              >
                {days.map((d, i) => (
                  <option value={i} key={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={sourceDay === targetDay || busy}
              onClick={() => void save(true)}
            >
              <Copy size={16} />
              Copy rules
            </button>
          </section>
        </>
      )}
    </>
  );
}
