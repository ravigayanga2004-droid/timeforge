import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowRight,
  BookOpen,
  CalendarDays,
  Check,
  DoorOpen,
  GraduationCap,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, days, manager } from "./api";
import type { Metrics, Page, Row, Timetable, User, Version } from "./api";
import { Badge, Empty, Heading, Loading, Notice } from "./components";
export default function Dashboard({ user }: { user: User }) {
  const query = useQuery({
    queryKey: ["overview", user.id],
    queryFn: async () => {
      const [courses, lecturers, groups, rooms, timetables] = await Promise.all(
        [
          api<Page<Row>>("/data/courses?limit=1"),
          api<Page<Row>>("/data/lecturers?limit=1"),
          api<Page<Row>>("/data/student-groups?limit=1"),
          api<Page<Row>>("/data/rooms?limit=1"),
          api<Page<Timetable>>("/timetables"),
        ],
      );
      const active = timetables.items.find((t) => t.current_version_id);
      let version: Version | null = null;
      let metrics: Metrics | null = null;
      if (active?.current_version_id) {
        const id = manager(user)
          ? active.current_version_id
          : active.published_version_id;
        if (id)
          [version, metrics] = await Promise.all([
            api<Version>(`/versions/${id}`),
            api<Metrics>(`/versions/${id}/analytics`),
          ]);
      }
      return {
        courses,
        lecturers,
        groups,
        rooms,
        timetables,
        active,
        version,
        metrics,
      };
    },
  });
  const date = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Colombo",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());
  const data = query.data;
  const chart = days.slice(0, 5).map((d, i) => ({
    name: d.slice(0, 3),
    sessions: data?.metrics?.sessions_per_day[String(i)] ?? 0,
  }));
  return (
    <>
      <Heading
        eyebrow={date}
        title={`Welcome back, ${user.name.split(" ")[0]}.`}
        description="A clear view of your academic week. A little less coordination."
        actions={
          <a className="button primary" href="#planner">
            <CalendarDays size={17} />
            {manager(user) ? "Open timetable studio" : "View my schedule"}
          </a>
        }
      />
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <Notice error>{query.error.message}</Notice>
      ) : (
        data && (
          <>
            <div className="welcome-banner">
              <div>
                <span className="eyebrow">Make time for better learning</span>
                <h2>
                  Every class.
                  <br />
                  In the right place.
                </h2>
                <p>
                  Build a balanced timetable around the people
                  <br className="desktop-only" /> and spaces that make your
                  university work.
                </p>
                <a href={manager(user) ? "#planner" : "#planner"}>
                  Explore your schedules <ArrowRight size={16} />
                </a>
              </div>
              <div className="banner-art" aria-hidden="true">
                <div className="mini-calendar">
                  <div className="mini-head">
                    <span />
                    <span />
                    <strong>YOUR WEEK, IN SYNC</strong>
                  </div>
                  <div className="mini-days">
                    <span>M</span>
                    <span>T</span>
                    <span>W</span>
                    <span>T</span>
                    <span>F</span>
                  </div>
                  <div className="mini-block one">
                    <Check size={16} />
                  </div>
                  <div className="mini-block two" />
                  <div className="mini-block three" />
                  <div className="mini-block four" />
                  <div className="mini-line l1" />
                  <div className="mini-line l2" />
                  <div className="mini-line l3" />
                  <div className="mini-line l4" />
                </div>
                <div className="sync-pill">
                  <span>✓</span>Designed around your constraints
                </div>
              </div>
            </div>
            <div className="stats-grid">
              {[
                {
                  label: "Courses",
                  value: data.courses.total,
                  icon: BookOpen,
                  color: "green",
                  href: "#data/courses",
                },
                {
                  label: "Lecturers",
                  value: data.lecturers.total,
                  icon: Users,
                  color: "blue",
                  href: "#data/lecturers",
                },
                {
                  label: "Student groups",
                  value: data.groups.total,
                  icon: GraduationCap,
                  color: "orange",
                  href: "#data/student-groups",
                },
                {
                  label: "Teaching spaces",
                  value: data.rooms.total,
                  icon: DoorOpen,
                  color: "purple",
                  href: "#data/rooms",
                },
              ].map((stat) => (
                <a
                  className="stat-card panel"
                  key={stat.label}
                  href={stat.href}
                >
                  <div className="between">
                    <span className={`stat-icon ${stat.color}`}>
                      <stat.icon size={20} />
                    </span>
                    <ArrowDownRight size={17} className="muted" />
                  </div>
                  <strong>{stat.value}</strong>
                  <span>{stat.label}</span>
                  <small>
                    View academic resources <ArrowRight size={12} />
                  </small>
                </a>
              ))}
            </div>
            <div className="dashboard-columns">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="eyebrow">Academic planning</span>
                    <h3>Your timetables</h3>
                  </div>
                  <a className="text-link" href="#planner">
                    View all <ArrowRight size={14} />
                  </a>
                </div>
                {!data.timetables.items.length ? (
                  <Empty title="A fresh start">
                    {manager(user)
                      ? "Create your first timetable in the studio."
                      : "Approved schedules will appear here after publication."}
                  </Empty>
                ) : (
                  <div className="schedule-list">
                    {data.timetables.items.slice(0, 4).map((t) => (
                      <a href="#planner" key={t.id} className="schedule-row">
                        <span className="schedule-icon">
                          <CalendarDays size={21} />
                        </span>
                        <div>
                          <strong>{t.name}</strong>
                          <small>
                            {t.current_version_id
                              ? "Timetable version available"
                              : "Awaiting generation"}
                          </small>
                        </div>
                        <Badge value={t.status} />
                        <ArrowRight size={16} />
                      </a>
                    ))}
                  </div>
                )}
                <div className="panel-note">
                  <span className="tiny-dot" /> All schedule changes are
                  versioned and auditable.
                </div>
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="eyebrow">Week at a glance</span>
                    <h3>Session distribution</h3>
                  </div>
                  <span className="muted">
                    {data.metrics?.session_count ?? 0} sessions
                  </span>
                </div>
                {data.metrics ? (
                  <div
                    className="dashboard-chart"
                    aria-label="Sessions per weekday"
                  >
                    <ResponsiveContainer width="100%" height={210}>
                      <BarChart data={chart} margin={{ left: -20, right: 12 }}>
                        <CartesianGrid vertical={false} strokeDasharray="3 3" />
                        <XAxis
                          dataKey="name"
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          allowDecimals={false}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip />
                        <Bar
                          dataKey="sessions"
                          fill="#328b75"
                          radius={[5, 5, 0, 0]}
                          maxBarSize={32}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <Empty title="No schedule data yet">
                    Generate a timetable to see how sessions are distributed.
                  </Empty>
                )}
                <div className="panel-note">
                  Counts use the latest available timetable in your scope.
                </div>
              </section>
            </div>
            <section className="panel planning-steps">
              <div>
                <span className="eyebrow">Your planning toolkit</span>
                <h3>From requirements to a ready week</h3>
              </div>
              <div className="step-links">
                {[
                  {
                    n: "01",
                    name: "Prepare your data",
                    desc: "Courses, people & teaching spaces",
                    href: manager(user) ? "#data/sections" : "#planner",
                  },
                  {
                    n: "02",
                    name: "Set availability",
                    desc: "Protect time and honor preferences",
                    href:
                      manager(user) || user.role === "lecturer"
                        ? "#availability"
                        : "#planner",
                  },
                  {
                    n: "03",
                    name: "Generate & refine",
                    desc: "Compare, review and publish",
                    href: "#planner",
                  },
                ].map((s) => (
                  <a href={s.href} key={s.n}>
                    <span>{s.n}</span>
                    <div>
                      <strong>{s.name}</strong>
                      <small>{s.desc}</small>
                    </div>
                    <ArrowRight size={15} />
                  </a>
                ))}
              </div>
            </section>
          </>
        )
      )}
    </>
  );
}
