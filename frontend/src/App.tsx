import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowRight,
  Bell,
  BookOpen,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronDown,
  Clock3,
  DoorOpen,
  GraduationCap,
  HelpCircle,
  Layers3,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { api, manager, post, title } from "./api";
import type { User } from "./api";
import Dashboard from "./Dashboard";
import DataPage from "./DataPage";
import Planner from "./Planner";
import Availability from "./Availability";
import {
  Analytics,
  Audit,
  Guide,
  Notifications,
  Users as UsersPage,
} from "./Reports";
import { Loading, Modal, Notice } from "./components";
import "./styles.css";

function useRoute() {
  const [route, setRoute] = useState(location.hash.slice(1) || "dashboard");
  useEffect(() => {
    const update = () => setRoute(location.hash.slice(1) || "dashboard");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
export default function App() {
  const client = useQueryClient();
  const route = useRoute();
  const [mobile, setMobile] = useState(false);
  const [error, setError] = useState("");
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("/auth/me"),
    retry: false,
  });
  useEffect(() => {
    setMobile(false);
    window.scrollTo(0, 0);
  }, [route]);
  if (me.isPending)
    return (
      <div className="startup">
        <div className="brand">
          <span className="brand-mark">
            <Layers3 />
          </span>
          TimeForge
        </div>
        <Loading />
      </div>
    );
  if (!me.data)
    return (
      <Auth
        onLogin={async () => {
          await client.invalidateQueries({ queryKey: ["me"] });
        }}
      />
    );
  const user = me.data;
  const isManager = manager(user);
  const links = [
    {
      group: "WORKSPACE",
      items: [
        { id: "dashboard", label: "Overview", icon: LayoutDashboard },
        {
          id: "planner",
          label: isManager ? "Timetable studio" : "My timetable",
          icon: CalendarDays,
        },
        { id: "analytics", label: "Analytics", icon: ChartNoAxesCombined },
        ...(isManager || user.role === "lecturer"
          ? [{ id: "availability", label: "Availability", icon: Clock3 }]
          : []),
      ],
    },
    {
      group: "ACADEMIC RESOURCES",
      items: [
        { id: "data/courses", label: "Courses", icon: BookOpen },
        { id: "data/sections", label: "Course sections", icon: Layers3 },
        { id: "data/lecturers", label: "Lecturers", icon: Users },
        {
          id: "data/student-groups",
          label: "Student groups",
          icon: GraduationCap,
        },
        { id: "data/rooms", label: "Rooms & spaces", icon: DoorOpen },
        ...(isManager
          ? [{ id: "data/constraints", label: "Constraints", icon: Settings2 }]
          : []),
      ],
    },
    ...(user.role === "admin"
      ? [
          {
            group: "ADMINISTRATION",
            items: [
              {
                id: "data/universities",
                label: "Universities",
                icon: GraduationCap,
              },
              { id: "users", label: "Users & access", icon: ShieldCheck },
              { id: "data/departments", label: "Departments", icon: Layers3 },
              {
                id: "data/academic-years",
                label: "Academic years",
                icon: CalendarDays,
              },
              { id: "data/terms", label: "Academic terms", icon: CalendarDays },
              { id: "data/buildings", label: "Buildings", icon: DoorOpen },
              {
                id: "data/room-features",
                label: "Room features",
                icon: Settings2,
              },
              { id: "data/time-slots", label: "Time periods", icon: Clock3 },
              { id: "audit", label: "Audit trail", icon: ShieldCheck },
            ],
          },
        ]
      : []),
  ];
  const currentLabel =
    links.flatMap((g) => g.items).find((l) => l.id === route)?.label ??
    title(route);
  function content() {
    if (route === "dashboard") return <Dashboard user={user} />;
    if (route === "planner") return <Planner user={user} />;
    if (route === "analytics") return <Analytics user={user} />;
    if (route === "availability" && (isManager || user.role === "lecturer"))
      return <Availability user={user} />;
    if (route === "notifications") return <Notifications />;
    if (route === "guide") return <Guide />;
    if (route === "users" && user.role === "admin") return <UsersPage />;
    if (route === "audit" && user.role === "admin") return <Audit />;
    if (route.startsWith("data/"))
      return <DataPage key={route} entity={route.slice(5)} />;
    return (
      <Notice error>
        This page is unavailable for your role.{" "}
        <a href="#dashboard">Return to overview</a>
      </Notice>
    );
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <a className="brand" href="#dashboard">
          <span className="brand-mark">
            <Layers3 size={23} />
          </span>
          TimeForge<span className="brand-period">.</span>
        </a>
        <div className="workspace-picker">
          <span className="campus-icon">
            <GraduationCap size={19} />
          </span>
          <div>
            <strong>University workspace</strong>
            <small>Academic planning</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <nav aria-label="Main navigation">
          {links.map((group) => (
            <div className="nav-group" key={group.group}>
              <p>{group.group}</p>
              {group.items.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  aria-current={route === item.id ? "page" : undefined}
                  className={route === item.id ? "active" : ""}
                >
                  <item.icon size={18} />
                  {item.label}
                  {item.id === "planner" && <span className="nav-dot" />}
                </a>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <a className="help-card" href="#guide">
            <span className="help-icon">
              <Sparkles size={18} />
            </span>
            <strong>A smoother semester</strong>
            <p>
              Everything you need to get
              <br />
              your timetable ready.
            </p>
            <span>
              Explore the planning guide <ArrowRight size={13} />
            </span>
          </a>
          <a className="help-link" href="#guide">
            <HelpCircle size={17} />
            Help & privacy
          </a>
          <div className="user-card">
            <span className="avatar">
              {user.name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </span>
            <div>
              <strong>{user.name}</strong>
              <small>{title(user.role)}</small>
            </div>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={() =>
                void post("/auth/logout")
                  .then(() => {
                    client.clear();
                    location.hash = "dashboard";
                    void me.refetch();
                  })
                  .catch((e) => setError((e as Error).message))
              }
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMobile(true)}
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span>/</span>
            <strong>{currentLabel}</strong>
          </div>
          <span className="spacer" />
          <a className="global-search" href="#data/courses">
            <Search size={16} />
            <span>Find a course…</span>
            <kbd>↗</kbd>
          </a>
          <a
            className="notification-button"
            href="#notifications"
            aria-label="Notifications"
          >
            <Bell size={20} />
          </a>
          <span className="avatar small">{user.name[0]}</span>
        </header>
        <main id="main-content" className="page-content">
          {error && <Notice error>{error}</Notice>}
          {content()}
          <footer className="page-footer">
            <span>TimeForge · Thoughtfully scheduled.</span>
            <a href="#guide">Planning guide & privacy</a>
          </footer>
        </main>
      </div>
    </div>
  );
}
const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});
function Auth({ onLogin }: { onLogin: () => Promise<void> }) {
  const resetToken = new URLSearchParams(location.search).get("reset");
  const [mode, setMode] = useState(resetToken ? "reset" : "login");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [privacy, setPrivacy] = useState(false);
  const [busy, setBusy] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
  });
  async function login(data: z.infer<typeof loginSchema>) {
    setBusy(true);
    setError("");
    try {
      await post("/auth/login", data);
      await onLogin();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function recover(form: HTMLFormElement) {
    setBusy(true);
    setError("");
    try {
      const data = new FormData(form);
      const result = await post<{ message: string }>(
        mode === "forgot" ? "/auth/forgot-password" : "/auth/reset-password",
        mode === "forgot"
          ? { email: data.get("email") }
          : { token: resetToken, password: data.get("password") },
      );
      setMessage(result.message);
      if (mode === "reset") {
        history.replaceState(null, "", location.pathname);
        setMode("login");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <section className="auth-story">
        <a className="brand" href="/">
          <span className="brand-mark">
            <Layers3 size={24} />
          </span>
          TimeForge.
        </a>
        <div>
          <span className="eyebrow">The art of a well-planned week</span>
          <h1>
            More possibility.
            <br />
            Fewer conflicts.
          </h1>
          <p>
            Bring courses, people and spaces together.
            <br />
            Create university timetables that just work.
          </p>
          <div className="auth-proof">
            <span>
              <ShieldCheck size={19} />
              Constraints respected
            </span>
            <span>
              <CalendarDays size={19} />
              Every week, in sync
            </span>
          </div>
        </div>
        <span className="auth-foot">
          Built for the rhythm of university life.
        </span>
      </section>
      <section className="auth-form-section">
        <div className="auth-form">
          <span className="login-icon">
            <GraduationCap size={28} />
          </span>
          <p className="eyebrow">YOUR ACADEMIC WORKSPACE</p>
          <h2>
            {mode === "login"
              ? "A better week starts here."
              : mode === "forgot"
                ? "Let’s get you back in."
                : "Choose a new password."}
          </h2>
          <p className="muted">
            {mode === "login"
              ? "Sign in with your university account to continue."
              : mode === "forgot"
                ? "Enter your account email for reset instructions."
                : "Use at least 12 characters for your new password."}
          </p>
          {error && <Notice error>{error}</Notice>}
          {message && <Notice>{message}</Notice>}
          {mode === "login" ? (
            <form onSubmit={handleSubmit(login)}>
              <label className="form-field">
                University email
                <input
                  type="email"
                  autoComplete="username"
                  placeholder="you@university.edu"
                  {...register("email")}
                />
                {errors.email && (
                  <small className="field-error">{errors.email.message}</small>
                )}
              </label>
              <label className="form-field">
                Password
                <input
                  type="password"
                  autoComplete="current-password"
                  {...register("password")}
                />
                {errors.password && (
                  <small className="field-error">
                    {errors.password.message}
                  </small>
                )}
              </label>
              <div className="auth-options">
                <span>Secure university access</span>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    setMode("forgot");
                    setError("");
                  }}
                >
                  Forgot password?
                </button>
              </div>
              <button className="primary auth-submit" disabled={busy}>
                {busy ? "Signing in…" : "Sign in to TimeForge"}
                <ArrowRight size={17} />
              </button>
            </form>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void recover(e.currentTarget);
              }}
            >
              <label className="form-field">
                {mode === "forgot" ? "Email address" : "New password"}
                <input
                  name={mode === "forgot" ? "email" : "password"}
                  type={mode === "forgot" ? "email" : "password"}
                  required
                  minLength={mode === "reset" ? 12 : undefined}
                  maxLength={128}
                  autoComplete={mode === "reset" ? "new-password" : "email"}
                />
              </label>
              <button className="primary auth-submit" disabled={busy}>
                {busy
                  ? "Please wait…"
                  : mode === "forgot"
                    ? "Send reset instructions"
                    : "Reset password"}
              </button>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setMode("login");
                  setError("");
                }}
              >
                Back to sign in
              </button>
            </form>
          )}
          <p className="account-note">
            Need an account? Contact your university administrator.
          </p>
          <div className="auth-secure">
            <ShieldCheck size={15} />
            Your academic data stays in your workspace.
          </div>
          <button
            className="text-button privacy-link"
            onClick={() => setPrivacy(true)}
          >
            Privacy notice
          </button>
        </div>
      </section>
      {privacy && (
        <Modal title="Privacy notice" onClose={() => setPrivacy(false)}>
          <p>
            TimeForge stores university accounts, academic scheduling
            information, availability and audit records. Access is limited by
            role and department. Passwords use Argon2id hashing. Sessions expire
            and are invalidated after password changes.
          </p>
          <p>
            Contact your university administrator for retention policies, access
            requests and corrections. Password recovery uses your deployment's
            configured mail adapter.
          </p>
          <button onClick={() => setPrivacy(false)}>Close</button>
        </Modal>
      )}
    </div>
  );
}
