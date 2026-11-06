"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { DownloadButton } from "@/components/common/DownloadButton";
import { ErrorState } from "@/components/common/ErrorState";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField } from "@/components/common/SelectField";
import { Skeleton } from "@/components/common/Skeleton";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { useAttendanceRoster, useMarkAttendance, useMarkTeachers, useMonthlyAttendance, useTeacherAttendanceHistory, useTeacherRoster } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { serverMessage } from "@/lib/forms";
import { sectionLabel, toOptions, today } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import { cn } from "@/lib/utils";
import type { AttendanceRosterRow, AttendanceStatus, MonthlyAttendance, Section, TeacherAttendanceRow } from "@/types/school";

const STATUSES: { value: AttendanceStatus; short: string; label: string; active: string }[] = [
  { value: "PRESENT", short: "P", label: "Present", active: "bg-green-600 text-white" },
  { value: "ABSENT", short: "A", label: "Absent", active: "bg-red-600 text-white" },
  { value: "LATE", short: "L", label: "Late", active: "bg-amber-500 text-white" },
  { value: "LEAVE", short: "Lv", label: "Leave", active: "bg-blue-600 text-white" },
];

function StatusButtons({ value, onChange, name }: { value: AttendanceStatus | undefined; onChange: (v: AttendanceStatus) => void; name: string }) {
  return (
    <div role="group" aria-label={`Attendance for ${name}`} className="inline-flex overflow-hidden rounded-md border">
      {STATUSES.map((s) => (
        <button key={s.value} type="button" title={s.label} aria-pressed={value === s.value} onClick={() => onChange(s.value)}
          className={cn("px-3 py-1.5 text-xs font-medium transition-colors", value === s.value ? s.active : "bg-background text-muted-foreground hover:bg-muted")}>{s.short}</button>
      ))}
    </div>
  );
}

function RosterEditor({ rows, section, date }: { rows: AttendanceRosterRow[]; section: string; date: string }) {
  const mark = useMarkAttendance();
  const [marks, setMarks] = useState<Record<string, AttendanceStatus | undefined>>(() => Object.fromEntries(rows.map((r) => [r.student, r.status ?? undefined])));
  const [saved, setSaved] = useState(false);
  const pending = rows.filter((r) => !marks[r.student]).length;
  const set = (id: string, v: AttendanceStatus) => { setSaved(false); setMarks((m) => ({ ...m, [id]: v })); };
  if (rows.length === 0) return <p className="rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">No students are enrolled in this section yet.</p>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{rows.length} students · {pending} not marked</p>
        <Button variant="outline" size="sm" onClick={() => { setSaved(false); setMarks(Object.fromEntries(rows.map((r) => [r.student, "PRESENT" as const]))); }}>Mark all present</Button>
      </div>
      <ul className="divide-y rounded-lg border bg-card shadow-sm">
        {rows.map((r) => (
          <li key={r.student} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
            <div className="leading-tight"><span className="font-medium">{r.roll_number ? `${r.roll_number}. ` : ""}{r.student_name}</span><div className="text-xs text-muted-foreground">{r.student_number}</div></div>
            <StatusButtons name={r.student_name} value={marks[r.student]} onChange={(v) => set(r.student, v)} />
          </li>
        ))}
      </ul>
      {mark.error ? <FormAlert>{serverMessage(mark.error)}</FormAlert> : null}
      {saved ? <FormAlert variant="success">Attendance saved.</FormAlert> : null}
      <Button disabled={mark.isPending || pending === rows.length} onClick={() => mark.mutate({ section, date, records: rows.filter((r) => marks[r.student]).map((r) => ({ student: r.student, status: marks[r.student] as string })) }, { onSuccess: () => setSaved(true) })}>
        {mark.isPending ? "Saving…" : "Save attendance"}
      </Button>
    </div>
  );
}

function MarkTab({ sections }: { sections: Section[] }) {
  const [section, setSection] = useState("");
  const [date, setDate] = useState(today());
  const roster = useAttendanceRoster(section, date);
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField label="Section" value={section} onChange={(e) => setSection(e.target.value)}>
          <option value="">Choose a section…</option>
          {toOptions(sections, sectionLabel).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </SelectField>
        <FormField label="Date" type="date" max={today()} value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      {!section ? null : roster.error ? <div className="rounded-lg border bg-card"><ErrorState error={roster.error} onRetry={() => void roster.refetch()} /></div> : roster.isLoading || !roster.data ? <Skeleton className="h-48 w-full" /> : (
        <RosterEditor key={`${section}-${date}-${roster.dataUpdatedAt}`} rows={roster.data} section={section} date={date} />
      )}
    </div>
  );
}

function ReportTab({ sections }: { sections: Section[] }) {
  const { can } = useAuth();
  const [section, setSection] = useState("");
  const [month, setMonth] = useState(today().slice(0, 7));
  const report = useMonthlyAttendance({ section, month }, Boolean(section));
  const columns: Column<MonthlyAttendance["students"][number]>[] = [
    { key: "n", header: "Student", cell: (r) => <div className="leading-tight"><span className="font-medium">{r.student_name}</span><div className="text-xs text-muted-foreground">{r.student_number}</div></div> },
    { key: "p", header: "Present", cell: (r) => r.present }, { key: "a", header: "Absent", cell: (r) => r.absent }, { key: "l", header: "Late", cell: (r) => r.late }, { key: "v", header: "Leave", cell: (r) => r.leave },
    { key: "pc", header: "%", cell: (r) => <strong className={r.percentage !== null && r.percentage < 75 ? "text-red-600" : ""}>{r.percentage === null ? "—" : `${r.percentage}%`}</strong> },
  ];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-56"><SelectField label="Section" value={section} onChange={(e) => setSection(e.target.value)}><option value="">Choose a section…</option>{toOptions(sections, sectionLabel).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField></div>
        <div className="w-44"><FormField label="Month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></div>
        {section && can("reports.view") ? <DownloadButton path="/school/reports/attendance/pdf/" filename="attendance.pdf" query={{ section, month }}>PDF</DownloadButton> : null}
        {section && can("exports.attendance") ? <DownloadButton path="/school/exports/attendance/csv/" filename="attendance.csv" query={{ section }}>CSV</DownloadButton> : null}
      </div>
      {section ? <DataTable columns={columns} rows={report.data?.students} rowKey={(r) => r.student} isLoading={report.isLoading} error={report.error} emptyTitle="No attendance recorded this month" /> : null}
    </div>
  );
}

function TeacherEditor({ rows, date }: { rows: TeacherAttendanceRow[]; date: string }) {
  const mark = useMarkTeachers();
  const [marks, setMarks] = useState<Record<string, AttendanceStatus | undefined>>(() => Object.fromEntries(rows.map((r) => [r.teacher, r.status ?? undefined])));
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-3">
      <ul className="divide-y rounded-lg border bg-card shadow-sm">
        {rows.map((r) => (
          <li key={r.teacher} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
            <div className="leading-tight"><span className="font-medium">{r.teacher_name}</span><div className="text-xs text-muted-foreground">{r.employee_id}</div></div>
            <StatusButtons name={r.teacher_name} value={marks[r.teacher]} onChange={(v) => { setSaved(false); setMarks((m) => ({ ...m, [r.teacher]: v })); }} />
          </li>
        ))}
      </ul>
      {mark.error ? <FormAlert>{serverMessage(mark.error)}</FormAlert> : null}
      {saved ? <FormAlert variant="success">Attendance saved.</FormAlert> : null}
      <Button disabled={mark.isPending} onClick={() => mark.mutate({ date, records: rows.filter((r) => marks[r.teacher]).map((r) => ({ teacher: r.teacher, status: marks[r.teacher] })) }, { onSuccess: () => setSaved(true) })}>Save attendance</Button>
    </div>
  );
}

function TeachersTab() {
  const [date, setDate] = useState(today());
  const roster = useTeacherRoster(date);
  return (
    <div className="space-y-4">
      <div className="w-44"><FormField label="Date" type="date" max={today()} value={date} onChange={(e) => setDate(e.target.value)} /></div>
      {roster.error ? <div className="rounded-lg border bg-card"><ErrorState error={roster.error} onRetry={() => void roster.refetch()} /></div> : roster.isLoading || !roster.data ? <Skeleton className="h-40 w-full" /> : roster.data.length === 0 ? <p className="rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">No active teachers.</p> : <TeacherEditor key={`${date}-${roster.dataUpdatedAt}`} rows={roster.data} date={date} />}
    </div>
  );
}

function TeacherHistoryTab() {
  const [from, setFrom] = useState(today().slice(0, 8) + "01");
  const [to, setTo] = useState(today());
  const history = useTeacherAttendanceHistory({ date_from: from, date_to: to, page_size: 100 });
  return (
    <div className="space-y-4">
      <div className="grid max-w-md gap-3 sm:grid-cols-2">
        <FormField label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <FormField label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      <DataTable isLoading={history.isLoading} error={history.error} rows={history.data?.results} rowKey={(r) => r.id} emptyTitle="No teacher attendance in this period"
        columns={[
          { key: "d", header: "Date", cell: (r) => r.date }, { key: "t", header: "Teacher", cell: (r) => <span className="font-medium">{r.teacher_name}</span> },
          { key: "s", header: "Status", cell: (r) => r.status.charAt(0) + r.status.slice(1).toLowerCase() }, { key: "c", header: "Check-in", cell: (r) => r.check_in ?? "—" },
          { key: "n", header: "Remarks", cell: (r) => r.remarks || "—" },
        ]} />
    </div>
  );
}

export default function AttendancePage() {
  const { can } = useAuth();
  const sections = useAllOptions<Section>("/school/sections");
  const tabs = [
    ...(can("attendance.students.mark") ? [{ value: "mark" as const, label: "Mark attendance" }] : []),
    { value: "report" as const, label: "Monthly report" },
    ...(can("attendance.teachers.manage") ? [{ value: "teachers" as const, label: "Teachers" }] : []),
    ...(can("attendance.teachers.view") ? [{ value: "history" as const, label: "Teacher history" }] : []),
  ];
  const [tab, setTab] = useState<"mark" | "report" | "teachers" | "history">(tabs[0].value);
  return (
    <>
      <PageHeader title="Attendance" description="Daily marking and monthly summaries. Late counts as attended; leave is excused." />
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "mark" ? <MarkTab sections={sections.options} /> : null}
      {tab === "report" ? <ReportTab sections={sections.options} /> : null}
      {tab === "teachers" ? <TeachersTab /> : null}
      {tab === "history" ? <TeacherHistoryTab /> : null}
    </>
  );
}
