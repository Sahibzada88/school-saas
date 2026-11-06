"use client";

import { useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { DownloadButton } from "@/components/common/DownloadButton";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField } from "@/components/common/SelectField";
import { StatCard } from "@/components/common/StatCard";
import { useExamAnalysis, useOutstanding, useStudentsSummary } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { formatDate, formatMoney } from "@/lib/format";
import { sectionLabel, toOptions, today } from "@/lib/options";
import { whatsappLink } from "@/lib/whatsapp";
import { useAllOptions } from "@/lib/resource";
import type { Exam, Section } from "@/types/school";

function Card({ title, description, actions, children }: { title: string; description: string; actions?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="font-medium">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div><div className="flex flex-wrap gap-2">{actions}</div></div>
      {children}
    </section>
  );
}

export default function ReportsPage() {
  const { can } = useAuth();
  const sections = useAllOptions<Section>("/school/sections");
  const exams = useAllOptions<Exam>("/school/exams", {}, can("results.publish"));
  const [section, setSection] = useState("");
  const [month, setMonth] = useState(today().slice(0, 7));
  const [exam, setExam] = useState("");
  const summary = useStudentsSummary(can("students.view"));
  const outstanding = useOutstanding({}, can("fees.manage"));
  const analysis = useExamAnalysis(exam);

  return (
    <>
      <PageHeader title="Reports" description="Every report is generated on request from live data; nothing is stored." />

      {can("students.view") ? (
        <Card title="Students" description="Enrolment overview and downloads."
          actions={<>{can("exports.students") ? <DownloadButton path="/school/exports/students/csv/" filename="students.csv">CSV</DownloadButton> : null}<DownloadButton path="/school/reports/students/pdf/" filename="students.pdf">PDF</DownloadButton></>}>
          <div className="grid gap-3 sm:grid-cols-4">
            <StatCard label="Students" value={summary.data?.total} isLoading={summary.isLoading} />
            <StatCard label="Active" value={summary.data?.by_status.ACTIVE ?? 0} isLoading={summary.isLoading} />
            <StatCard label="Boys / Girls" value={`${summary.data?.by_gender.MALE ?? 0} / ${summary.data?.by_gender.FEMALE ?? 0}`} isLoading={summary.isLoading} />
            <StatCard label="Sections in use" value={summary.data?.by_class.length} isLoading={summary.isLoading} />
          </div>
          <DataTable isLoading={summary.isLoading} rows={summary.data?.by_class} rowKey={(r) => `${r.class_name}-${r.section_name}`} emptyTitle="No enrolments yet"
            columns={[{ key: "c", header: "Class", cell: (r) => r.class_name }, { key: "s", header: "Section", cell: (r) => r.section_name }, { key: "n", header: "Students", cell: (r) => r.count }]} />
        </Card>
      ) : null}

      {can("reports.view") ? (
        <Card title="Attendance" description="Monthly attendance per section (late counts as attended; leave is excused).">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-56"><SelectField label="Section" value={section} onChange={(e) => setSection(e.target.value)}><option value="">Choose a section…</option>{toOptions(sections.options, sectionLabel).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField></div>
            <div className="w-44"><FormField label="Month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></div>
            <DownloadButton path="/school/reports/attendance/pdf/" filename="attendance.pdf" query={{ section, month }} disabled={!section}>PDF</DownloadButton>
            {can("exports.attendance") ? <DownloadButton path="/school/exports/attendance/csv/" filename="attendance.csv" query={{ section }} disabled={!section}>CSV</DownloadButton> : null}
          </div>
        </Card>
      ) : null}

      {can("fees.manage") ? (
        <Card title="Outstanding fees" description="Unpaid and partly paid invoices, oldest due date first."
          actions={<>{can("exports.fees") ? <DownloadButton path="/school/exports/fees/csv/" filename="invoices.csv">CSV</DownloadButton> : null}<DownloadButton path="/school/reports/fees/outstanding/pdf/" filename="outstanding-fees.pdf">PDF</DownloadButton></>}>
          <div className="grid gap-3 sm:grid-cols-2"><StatCard label="Total outstanding" value={outstanding.data ? formatMoney(outstanding.data.total, "PKR") : undefined} isLoading={outstanding.isLoading} /><StatCard label="Open invoices" value={outstanding.data?.count} isLoading={outstanding.isLoading} /></div>
          <DataTable isLoading={outstanding.isLoading} error={outstanding.error} rows={outstanding.data?.rows} rowKey={(r) => r.invoice_id} emptyTitle="Nothing outstanding" emptyDescription="Every invoice is paid."
            columns={[
              { key: "i", header: "Invoice", cell: (r) => r.invoice_number }, { key: "s", header: "Student", cell: (r) => r.student_name }, { key: "c", header: "Class", cell: (r) => r.class_name },
              { key: "d", header: "Due", cell: (r) => formatDate(r.due_date) }, { key: "l", header: "Days late", cell: (r) => (r.days_overdue ? <span className="text-red-600">{r.days_overdue}</span> : "—") },
              { key: "b", header: "Balance", className: "tabular-nums", cell: (r) => formatMoney(r.balance, "PKR") },
              {
                key: "w", header: "", className: "text-right",
                cell: (r) => {
                  const link = r.guardian_phone ? whatsappLink(r.guardian_phone, `Assalam o Alaikum ${r.guardian_name}, ${r.student_name} ki fee (invoice ${r.invoice_number}) ka balance ${formatMoney(r.balance, "PKR")} hai, last date ${formatDate(r.due_date)}. Shukriya.`) : null;
                  return link ? <a href={link} target="_blank" rel="noopener noreferrer" className="text-sm font-medium underline underline-offset-4">WhatsApp</a> : <span className="text-xs text-muted-foreground">No number</span>;
                },
              },
            ]} />
          {outstanding.data?.truncated ? <p className="text-sm text-muted-foreground">Showing the first 500 invoices. Download the CSV for the full list.</p> : null}
        </Card>
      ) : null}

      {can("results.publish") ? (
        <Card title="Exam analysis" description="Averages and pass rates per subject for a published exam.">
          <div className="max-w-sm"><SelectField label="Exam" value={exam} onChange={(e) => setExam(e.target.value)}><option value="">Choose an exam…</option>{toOptions(exams.options, (e) => `${e.name} (${e.status.toLowerCase()})`).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField></div>
          {exam && analysis.data ? (
            <>
              <p className="text-sm">{analysis.data.passed}/{analysis.data.students} students passed ({analysis.data.pass_rate ?? "—"}%)</p>
              <DataTable isLoading={false} rows={analysis.data.subjects} rowKey={(s) => `${s.class_name}-${s.subject}`} emptyTitle="No marks entered yet"
                columns={[{ key: "s", header: "Subject", cell: (s) => `${s.subject} (class ${s.class_name})` }, { key: "a", header: "Average", cell: (s) => s.average ?? "—" }, { key: "h", header: "Highest", cell: (s) => s.highest ?? "—" },
                  { key: "l", header: "Lowest", cell: (s) => s.lowest ?? "—" }, { key: "p", header: "Pass rate", cell: (s) => (s.pass_rate === null ? "—" : `${s.pass_rate}%`) }]} />
            </>
          ) : null}
        </Card>
      ) : null}
    </>
  );
}
