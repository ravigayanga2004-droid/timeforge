export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  department_id: number | null;
  group_id: number | null;
  is_active: boolean;
}
export type Row = Record<string, unknown> & { id: number };
export interface Page<T> {
  items: T[];
  total: number;
}
export interface Assignment {
  section_id: number;
  session_number: number;
  day: number;
  start: number;
  end: number;
  room_id: number;
  lecturer_id: number;
  is_locked: boolean;
  notes: string;
}
export interface Violation {
  code: string;
  severity: "hard" | "soft";
  description: string;
  related_sessions: string[];
  penalty: number;
  suggestion: string;
}
export interface Job {
  id: number;
  status: string;
  stage: string;
  progress: number;
  error_message: string | null;
}
export interface Metrics {
  session_count: number;
  teaching_minutes: number;
  room_utilization: number;
  total_penalty: number;
  penalties: Record<string, number>;
  sessions_per_day: Record<string, number>;
  lecturer_minutes: Record<string, number>;
  group_minutes: Record<string, number>;
  room_minutes: Record<string, number>;
  room_capacity_utilization: number;
}
export interface Version {
  id: number;
  version_number: number;
  score: number;
  hard_violations: number;
  soft_violations: number;
  status: string;
  metrics: Metrics;
  sessions?: Assignment[];
  violations?: Violation[];
}
export interface Timetable {
  id: number;
  name: string;
  status: string;
  term_id: number;
  department_id: number;
  current_version_id: number | null;
  published_version_id: number | null;
  versions: Version[];
  jobs: Job[];
  approvals: Row[];
}
export interface SchemaField {
  type?: string;
  title?: string;
  default?: unknown;
  enum?: unknown[];
  anyOf?: SchemaField[];
  items?: SchemaField;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  format?: string;
  const?: unknown;
}
export interface Schema {
  properties: Record<string, SchemaField>;
  required?: string[];
}
export type SchemaMap = Record<string, { schema: Schema; writable: boolean }>;
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const csrf =
    document.cookie
      .split("; ")
      .find((c) => c.startsWith("tf_csrf="))
      ?.split("=")[1] ?? "";
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      "X-CSRF-Token": decodeURIComponent(csrf),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "The service could not complete this request" }));
    throw new ApiError(response.status, data.detail);
  }
  return response.json() as Promise<T>;
}
export function post<T>(path: string, body: unknown = {}) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export const text = (row: Row | undefined, key: string) =>
  String(row?.[key] ?? "");
export const num = (row: Row | undefined, key: string) =>
  Number(row?.[key] ?? 0);
export const title = (value: string) =>
  value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
export const clock = (value: number) =>
  `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
export const days = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];
export const manager = (u: User) => ["admin", "coordinator"].includes(u.role);
export async function download(path: string, name: string) {
  const response = await fetch(`/api${path}`, { credentials: "include" });
  if (!response.ok) {
    const data = await response.json();
    throw new ApiError(response.status, data.detail);
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
