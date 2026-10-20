import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Plus, Search, Pencil, Archive, Download, Upload } from "lucide-react";
import { api, download, text, title, ApiError } from "./api";
import type { Page, Row, Schema, SchemaField, SchemaMap } from "./api";
import { Badge, Empty, Heading, Loading, Modal, Notice } from "./components";

const references: Record<string, string> = {
  department_id: "departments",
  academic_year_id: "academic-years",
  building_id: "buildings",
  lecturer_id: "lecturers",
  room_id: "rooms",
  course_id: "courses",
  term_id: "terms",
  slot_id: "time-slots",
  group_id: "student-groups",
  section_id: "sections",
  group_ids: "student-groups",
  feature_ids: "room-features",
  preferred_room_ids: "rooms",
  preferred_slot_ids: "time-slots",
};
export const label = (row: Row) =>
  text(row, "name") ||
  text(row, "code") ||
  (row.day !== undefined
    ? `${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][Number(row.day)]} ${Math.floor(Number(row.start) / 60)}:${String(Number(row.start) % 60).padStart(2, "0")}`
    : `#${row.id}`);
export function Field({
  name,
  field,
  required,
  register,
  rows,
}: {
  name: string;
  field: SchemaField;
  required: boolean;
  register: ReturnType<typeof useForm<Record<string, unknown>>>["register"];
  rows: Record<string, Row[]>;
}) {
  const actual = field.anyOf?.find((f) => f.type !== "null") ?? field;
  const relation = references[name];
  const options = relation ? rows[relation] : undefined;
  const props = register(name, {
    required: required ? "This field is required" : false,
    setValueAs: (v: unknown) => {
      if (v === "" || v === undefined)
        return field.anyOf?.some((f) => f.type === "null")
          ? null
          : actual.type === "array"
            ? []
            : actual.type === "object"
              ? {}
              : v;
      if (actual.type === "integer" || actual.type === "number")
        return Number(v);
      if (actual.type === "array" || actual.type === "object") {
        if (Array.isArray(v)) return v.map(Number);
        try {
          return JSON.parse(String(v));
        } catch {
          return v;
        }
      }
      return v;
    },
  });
  const caption =
    name === "start" || name === "end"
      ? `${title(name)} (minutes after midnight)`
      : title(name);
  return (
    <label className={actual.type === "boolean" ? "check-field" : "form-field"}>
      <span>
        {caption}
        {required && actual.type !== "boolean" ? " *" : ""}
      </span>
      {actual.type === "boolean" ? (
        <input type="checkbox" {...props} />
      ) : actual.enum ? (
        <select {...props}>
          {actual.enum.map((o) => (
            <option key={String(o)} value={String(o)}>
              {title(String(o))}
            </option>
          ))}
        </select>
      ) : options ? (
        <select {...props} multiple={actual.type === "array"}>
          {!required && actual.type !== "array" && (
            <option value="">None</option>
          )}
          {options.map((row) => (
            <option value={row.id} key={row.id}>
              {label(row)} · #{row.id}
            </option>
          ))}
        </select>
      ) : actual.type === "array" || actual.type === "object" ? (
        <textarea
          {...props}
          rows={2}
          placeholder={actual.type === "array" ? "[]" : "{}"}
          aria-describedby={`${name}-hint`}
        />
      ) : (
        <input
          {...props}
          type={
            actual.format === "date"
              ? "date"
              : actual.format === "email"
                ? "email"
                : name === "password"
                  ? "password"
                  : actual.type === "integer"
                    ? "number"
                    : "text"
          }
          min={actual.minimum}
          max={actual.maximum}
          minLength={actual.minLength}
          maxLength={actual.maxLength}
        />
      )}
      {(actual.type === "array" || actual.type === "object") && !options && (
        <small id={`${name}-hint`}>
          Use JSON, for example {actual.type === "array" ? "[0, 2, 4]" : "{}"}.
        </small>
      )}
    </label>
  );
}
export function RecordForm({
  schema,
  record,
  onSave,
  busy = false,
  rows = {},
}: {
  schema: Schema;
  record?: Row;
  onSave: (data: Record<string, unknown>) => void;
  busy?: boolean;
  rows?: Record<string, Row[]>;
}) {
  const defaults = Object.fromEntries(
    Object.entries(schema.properties).map(([k, f]) => [
      k,
      record?.[k] ??
        f.default ??
        (f.type === "array" ? [] : f.type === "boolean" ? false : ""),
    ]),
  );
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Record<string, unknown>>({ defaultValues: defaults });
  return (
    <form onSubmit={handleSubmit(onSave)}>
      <div className="form-grid">
        {Object.entries(schema.properties).map(([name, field]) => (
          <div key={name}>
            <Field
              name={name}
              field={field}
              required={schema.required?.includes(name) ?? false}
              register={register}
              rows={rows}
            />
            {errors[name] && (
              <small className="field-error">
                {String(errors[name]?.message)}
              </small>
            )}
          </div>
        ))}
      </div>
      <div className="form-footer">
        <span className="muted">* Required fields</span>
        <button className="primary" disabled={busy}>
          {busy ? "Saving…" : "Save record"}
        </button>
      </div>
    </form>
  );
}
export default function DataPage({ entity }: { entity: string }) {
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [editor, setEditor] = useState<Row | null | false>(false);
  const [removing, setRemoving] = useState<Row | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  useEffect(() => {
    setOffset(0);
    setSearch("");
    setEditor(false);
    setError("");
    setMessage("");
  }, [entity]);
  const schema = useQuery({
    queryKey: ["schemas"],
    queryFn: () => api<SchemaMap>("/data/schema"),
  });
  const records = useQuery({
    queryKey: ["data", entity, search, offset],
    queryFn: () =>
      api<Page<Row>>(
        `/data/${entity}?limit=30&offset=${offset}&q=${encodeURIComponent(search)}`,
      ),
  });
  const refs = useQuery<Record<string, Row[]>>({
    queryKey: ["references"],
    queryFn: async () =>
      Object.fromEntries(
        await Promise.all(
          [...new Set(Object.values(references))].map(async (key) => [
            key,
            (await api<Page<Row>>(`/data/${key}?limit=500`)).items,
          ]),
        ),
      ),
  });
  const definition = schema.data?.[entity];
  async function save(data: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      await api(`/data/${entity}${editor ? `/${editor.id}` : ""}`, {
        method: editor ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      setEditor(false);
      setMessage("Record saved.");
      await client.invalidateQueries({ queryKey: ["data"] });
      await client.invalidateQueries({ queryKey: ["references"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!removing) return;
    setBusy(true);
    try {
      await api(`/data/${entity}/${removing.id}`, { method: "DELETE" });
      setRemoving(null);
      setMessage("Record archived or removed.");
      await client.invalidateQueries({ queryKey: ["data"] });
      await client.invalidateQueries({ queryKey: ["references"] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function exportData() {
    try {
      await download(`/imports/${entity}/export`, `${entity}.csv`);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const fields = definition
    ? Object.keys(definition.schema.properties)
        .filter(
          (k) =>
            ![
              "description",
              "required_features",
              "preferred_days",
              "preferred_room_ids",
              "preferred_slot_ids",
              "configuration",
              "reason",
            ].includes(k),
        )
        .slice(0, 6)
    : [];
  return (
    <>
      <Heading
        eyebrow="Academic resources"
        title={title(entity)}
        description="Keep the scheduling engine connected to accurate academic data."
        actions={
          <>
            <button onClick={exportData}>
              <Download size={16} />
              Export CSV
            </button>
            {definition?.writable && (
              <>
                <button onClick={() => setImporting(true)}>
                  <Upload size={16} />
                  Import
                </button>
                <button
                  className="primary"
                  onClick={() => {
                    setError("");
                    setEditor(null);
                  }}
                >
                  <Plus size={16} />
                  Add {title(entity).replace(/s$/, "")}
                </button>
              </>
            )}
          </>
        }
      />
      {message && <Notice>{message}</Notice>}
      {error && editor === false && <Notice error>{error}</Notice>}
      <section className="panel">
        <div className="table-toolbar">
          <div className="search-input">
            <Search size={16} />
            <input
              aria-label={`Search ${title(entity)}`}
              value={search}
              placeholder={`Search ${title(entity).toLowerCase()}…`}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          </div>
          <span className="muted">{records.data?.total ?? 0} records</span>
        </div>
        {records.isPending ? (
          <Loading />
        ) : records.error ? (
          <Notice error>{records.error.message}</Notice>
        ) : !records.data?.items.length ? (
          <Empty title="No records found">
            Add a record or import a CSV file to start planning.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  {fields.map((k) => (
                    <th key={k}>{title(k)}</th>
                  ))}
                  {definition?.writable && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {records.data.items.map((row) => (
                  <tr key={row.id}>
                    <td className="muted">#{row.id}</td>
                    {fields.map((k) => (
                      <td key={k}>
                        {k === "is_active" ? (
                          <Badge value={row[k] ? "active" : "inactive"} />
                        ) : references[k] ? (
                          label(
                            refs.data?.[references[k]]?.find(
                              (r) => r.id === Number(row[k]),
                            ) ?? { id: Number(row[k]) },
                          )
                        ) : Array.isArray(row[k]) ? (
                          String(row[k])
                        ) : (
                          text(row, k)
                        )}
                      </td>
                    ))}
                    {definition?.writable && (
                      <td>
                        <div className="row-actions">
                          <button
                            className="icon-button"
                            aria-label={`Edit ${label(row)}`}
                            onClick={() => {
                              setError("");
                              setEditor(row);
                            }}
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            className="icon-button"
                            aria-label={`Archive ${label(row)}`}
                            onClick={() => setRemoving(row)}
                          >
                            <Archive size={15} />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 30))}
          >
            Previous
          </button>
          <span>
            {offset + 1}–{Math.min(offset + 30, records.data?.total ?? 0)} of{" "}
            {records.data?.total ?? 0}
          </span>
          <button
            disabled={offset + 30 >= (records.data?.total ?? 0)}
            onClick={() => setOffset(offset + 30)}
          >
            Next
          </button>
        </div>
      </section>
      {editor !== false && definition && (
        <Modal
          title={`${editor ? "Edit" : "Add"} ${title(entity)}`}
          onClose={() => setEditor(false)}
        >
          {error && <Notice error>{error}</Notice>}
          <RecordForm
            key={editor?.id ?? "new"}
            schema={definition.schema}
            record={editor ?? undefined}
            onSave={save}
            busy={busy}
            rows={refs.data}
          />
        </Modal>
      )}
      {removing && (
        <Modal title="Archive this record?" onClose={() => setRemoving(null)}>
          <p>
            {label(removing)} will be archived when supported. Referenced
            records are protected against deletion.
          </p>
          {error && <Notice error>{error}</Notice>}
          <div className="form-footer">
            <button onClick={() => setRemoving(null)}>Keep record</button>
            <button className="danger" onClick={remove} disabled={busy}>
              Archive or remove
            </button>
          </div>
        </Modal>
      )}
      {importing && (
        <ImportDialog
          entity={entity}
          onClose={() => {
            setImporting(false);
            void client.invalidateQueries({ queryKey: ["data"] });
            void client.invalidateQueries({ queryKey: ["references"] });
          }}
        />
      )}
    </>
  );
}
function ImportDialog({
  entity,
  onClose,
}: {
  entity: string;
  onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<{
    status: string;
    row_count: number;
    errors: { row: number; message: string }[];
    preview: Row[];
    committed: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(dry: boolean) {
    if (!file) return;
    setBusy(true);
    setError("");
    const data = new FormData();
    data.append("file", file);
    data.append("dry_run", String(dry));
    try {
      setResult(
        await api(`/imports/${entity}`, { method: "POST", body: data }),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={`Import ${title(entity)}`} onClose={onClose}>
      <p>
        UTF-8 CSV · up to 500 rows · maximum 2 MB. All rows must pass validation
        before anything is imported.
      </p>
      <button
        onClick={() =>
          void download(
            `/imports/${entity}/template`,
            `${entity}-template.csv`,
          ).catch((e) => setError((e as Error).message))
        }
      >
        Download template
      </button>
      <label className="upload-box">
        Choose CSV file
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setResult(null);
          }}
        />
      </label>
      {error && <Notice error>{error}</Notice>}
      {result && (
        <>
          <Notice error={!!result.errors.length}>
            {result.committed
              ? "Import complete"
              : `${result.row_count} rows · ${result.status.toLowerCase()}`}
          </Notice>
          {result.errors.map((e) => (
            <p className="field-error" key={e.row}>
              Row {e.row}: {e.message}
            </p>
          ))}
          {!!result.preview.length && (
            <details>
              <summary>Preview validated rows</summary>
              <pre>{JSON.stringify(result.preview, null, 2)}</pre>
            </details>
          )}
        </>
      )}
      <div className="form-footer">
        <button disabled={!file || busy} onClick={() => void run(true)}>
          Validate & preview
        </button>
        <button
          className="primary"
          disabled={
            !result || result.errors.length > 0 || result.committed || busy
          }
          onClick={() => void run(false)}
        >
          Import validated file
        </button>
      </div>
    </Modal>
  );
}
