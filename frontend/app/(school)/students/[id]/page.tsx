"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Avatar } from "@/components/common/Avatar";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { DownloadButton } from "@/components/common/DownloadButton";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Skeleton } from "@/components/common/Skeleton";
import { SpecFormDialog } from "@/components/common/SpecForm";
import { Badge } from "@/components/common/StatusBadge";
import { ResourceManager } from "@/components/common/ResourceManager";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import {
  documentHooks, invoiceHooks, resultHooks, studentHooks, useAttendanceRecords, useChangeStudentStatus, useEnrollStudent, useLinkGuardian,
  useMonthlyAttendance, useMoveEnrollment, useStudentDetail, useUnlinkGuardian,
} from "@/features/school/resources";
import { GUARDIAN_FIELDS, RELATIONSHIP_OPTIONS, studentFields } from "@/features/students/fields";
import { useAuth } from "@/hooks/useAuth";
import { formatDate, formatMoney } from "@/lib/format";
import { serverMessage } from "@/lib/forms";
import { STUDENT_STATUS_OPTIONS, sectionLabel, toOptions, today } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { SchoolUser } from "@/features/school/types";
import type { Guardian, Invoice, ReportCardSummary, Section, StudentDocument, StudentGuardianLink } from "@/types/school";

type Tab = "overview" | "guardians" | "documents" | "attendance" | "fees" | "results";

function Detail({ label, value }: { label: string; value?: string | number | null }) {
  return <div><dt className="text-sm text-muted-foreground">{label}</dt><dd className="font-medium">{value === null || value === undefined || value === "" ? "—" : value}</dd></div>;
}

function GuardiansTab({ studentId, links, canManage }: { studentId: string; links: StudentGuardianLink[]; canManage: boolean }) {
  const link = useLinkGuardian();
  const unlink = useUnlinkGuardian();
  const [mode, setMode] = useState<"existing" | "new" | null>(null);
  const [removing, setRemoving] = useState<StudentGuardianLink | null>(null);
  const guardians = useAllOptions<Guardian>("/school/guardians", {}, mode === "existing");
  const columns: Column<StudentGuardianLink>[] = [
    { key: "name", header: "Guardian", cell: (l) => <span className="font-medium">{l.guardian.full_name}</span> },
    { key: "rel", header: "Relationship", cell: (l) => l.relationship.charAt(0) + l.relationship.slice(1).toLowerCase() },
    { key: "phone", header: "Phone", cell: (l) => l.guardian.phone },
    { key: "flags", header: "", cell: (l) => <div className="flex gap-1">{l.is_primary ? <Badge tone="green">Primary</Badge> : null}{l.is_emergency_contact ? <Badge tone="amber">Emergency</Badge> : null}</div> },
    { key: "act", header: "", className: "text-right", cell: (l) => (canManage ? <Button variant="outline" size="sm" onClick={() => setRemoving(l)}>Unlink</Button> : null) },
  ];
  const relFields = [
    { name: "relationship", label: "Relationship", type: "select" as const, required: true, options: RELATIONSHIP_OPTIONS },
    { name: "is_primary", label: "Primary contact", type: "checkbox" as const },
    { name: "is_emergency_contact", label: "Emergency contact", type: "checkbox" as const },
  ];
  return (
    <div className="space-y-3">
      {canManage ? <div className="flex gap-2"><Button onClick={() => setMode("existing")}>Link existing guardian</Button><Button variant="outline" onClick={() => setMode("new")}>Add new guardian</Button></div> : null}
      <DataTable columns={columns} rows={links} rowKey={(l) => l.id} isLoading={false} emptyTitle="No guardians linked" emptyDescription="Link a parent or guardian so they can follow this student." />
      <SpecFormDialog open={mode === "existing"} title="Link an existing guardian" onClose={() => setMode(null)} submitLabel="Link"
        fields={[{ name: "guardian", label: "Guardian", type: "select", required: true, options: toOptions(guardians.options, (g) => `${g.full_name} (${g.phone})`) }, ...relFields]}
        onSubmit={(v) => link.mutateAsync({ id: studentId, body: v })} />
      <SpecFormDialog wide open={mode === "new"} title="Add a new guardian" onClose={() => setMode(null)} submitLabel="Add and link"
        fields={[...GUARDIAN_FIELDS, ...relFields]}
        onSubmit={({ relationship, is_primary, is_emergency_contact, ...guardian }) => link.mutateAsync({ id: studentId, body: { new_guardian: guardian, relationship, is_primary, is_emergency_contact } })} />
      <ConfirmDialog open={removing !== null} title="Unlink guardian" description={`${removing?.guardian.full_name ?? ""} will no longer see this student. The guardian record is kept.`}
        confirmLabel="Unlink" destructive isPending={unlink.isPending} error={unlink.error ? serverMessage(unlink.error) : null}
        onCancel={() => { setRemoving(null); unlink.reset(); }} onConfirm={() => removing && unlink.mutate({ id: studentId, linkId: removing.id }, { onSuccess: () => setRemoving(null) })} />
    </div>
  );
}

function DocumentsTab({ studentId, canManage }: { studentId: string; canManage: boolean }) {
  return (
    <ResourceManager<StudentDocument>
      noun="document" hooks={documentHooks} canManage={canManage} params={{ student: studentId, page_size: 100 }} extraBody={{ student: studentId }} rowLabel={(d) => d.title}
      emptyDescription="Record which papers the school has received (B-Form, previous result, etc.). Only the record is kept, not the file."
      fields={[
        { name: "doc_type", label: "Type", type: "text", required: true, placeholder: "B-Form" }, { name: "title", label: "Title", type: "text", required: true },
        { name: "received_on", label: "Received on", type: "date", nullable: true }, { name: "notes", label: "Notes", type: "text" },
      ]}
      columns={[
        { key: "t", header: "Document", cell: (d) => <span className="font-medium">{d.title}</span> }, { key: "ty", header: "Type", cell: (d) => d.doc_type },
        { key: "r", header: "Received", cell: (d) => (d.received_on ? formatDate(d.received_on) : "—") }, { key: "n", header: "Notes", cell: (d) => d.notes || "—" },
      ]}
    />
  );
}

function AttendanceTab({ studentId }: { studentId: string }) {
  const [month, setMonth] = useState(today().slice(0, 7));
  const monthly = useMonthlyAttendance({ student: studentId, month }, true);
  const records = useAttendanceRecords({ student: studentId, page_size: 15 });
  const row = monthly.data?.students[0];
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-4">
        <div className="space-y-1.5"><label htmlFor="att-month" className="text-sm font-medium">Month</label>
          <input id="att-month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="flex h-9 rounded-md border border-input bg-background px-3 text-sm" /></div>
        {row ? <p className="pb-2 text-sm">Present {row.present} · Late {row.late} · Absent {row.absent} · Leave {row.leave} · <strong>{row.percentage ?? "—"}%</strong></p> : <p className="pb-2 text-sm text-muted-foreground">No attendance recorded this month.</p>}
      </div>
      <DataTable rows={records.data?.results} rowKey={(r) => r.id} isLoading={records.isLoading} error={records.error} emptyTitle="No attendance yet"
        columns={[{ key: "d", header: "Date", cell: (r) => formatDate(r.date) }, { key: "s", header: "Status", cell: (r) => r.status.charAt(0) + r.status.slice(1).toLowerCase() }, { key: "r", header: "Remarks", cell: (r) => r.remarks || "—" }]} />
    </div>
  );
}

export default function StudentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAuth();
  const { data: student, isLoading, error, refetch } = useStudentDetail(id);
  const update = studentHooks.useUpdate();
  const remove = studentHooks.useRemove();
  const changeStatus = useChangeStudentStatus();
  const enroll = useEnrollStudent();
  const move = useMoveEnrollment();
  const invoices = invoiceHooks.useList({ student: id }, can("fees.view"));
  const results = resultHooks.useList({ student: id }, can("results.view"));
  const sections = useAllOptions<Section>("/school/sections");
  const studentAccounts = useAllOptions<SchoolUser>("/school/users", { role: "STUDENT" }, can("school.users.manage"));
  const [tab, setTab] = useState<Tab>("overview");
  const [dialog, setDialog] = useState<"edit" | "status" | "class" | "delete" | null>(null);

  const tabs: { value: Tab; label: string }[] = [
    { value: "overview", label: "Overview" }, { value: "guardians", label: "Guardians" }, { value: "documents", label: "Documents" },
    ...(can("attendance.students.view") ? [{ value: "attendance" as const, label: "Attendance" }] : []),
    ...(can("fees.view") ? [{ value: "fees" as const, label: "Fees" }] : []),
    ...(can("results.view") ? [{ value: "results" as const, label: "Results" }] : []),
  ];

  if (error) return <div className="rounded-lg border bg-card"><ErrorState error={error} onRetry={() => void refetch()} /></div>;
  if (isLoading || !student) return <div className="space-y-3"><Skeleton className="h-10 w-72" /><Skeleton className="h-40 w-full" /></div>;

  const invoiceColumns: Column<Invoice>[] = [
    { key: "n", header: "Invoice", cell: (i) => <Link href={`/fees/invoices/${i.id}`} className="font-medium underline-offset-4 hover:underline">{i.invoice_number}</Link> },
    { key: "p", header: "Period", cell: (i) => i.period_label }, { key: "d", header: "Due", cell: (i) => formatDate(i.due_date) },
    { key: "t", header: "Total", cell: (i) => formatMoney(i.total, "PKR") }, { key: "b", header: "Balance", cell: (i) => formatMoney(i.balance, "PKR") },
    { key: "s", header: "Status", cell: (i) => <Badge tone={i.status === "PAID" ? "green" : i.is_overdue ? "red" : "amber"}>{i.is_overdue ? "Overdue" : i.status.replace("_", " ").toLowerCase()}</Badge> },
  ];
  const resultColumns: Column<ReportCardSummary>[] = [
    { key: "e", header: "Exam", cell: (r) => <Link href={`/results/${r.id}`} className="font-medium underline-offset-4 hover:underline">{r.exam_name}</Link> },
    { key: "m", header: "Marks", cell: (r) => `${r.obtained_marks}/${r.total_marks}` }, { key: "p", header: "%", cell: (r) => `${r.percentage}%` },
    { key: "g", header: "Grade", cell: (r) => r.grade }, { key: "r", header: "Result", cell: (r) => <Badge tone={r.result_status === "PASS" ? "green" : "red"}>{r.result_status}</Badge> },
  ];
  const current = student.current_class;

  return (
    <>
      <Link href="/students" className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:underline"><ArrowLeft className="size-4" /> All students</Link>
      <PageHeader
        title={<span className="flex items-center gap-3"><Avatar name={student.full_name} url={student.photo_url} className="size-12" />{student.full_name}</span>}
        description={`${student.student_number} · ${current ? `${current.class_name}-${current.section_name}` : "Not enrolled"}`}
        actions={
          <>
            {can("students.manage") ? <Button variant="outline" onClick={() => setDialog("edit")}>Edit</Button> : null}
            {can("students.manage") ? <Button variant="outline" onClick={() => setDialog("class")}>{current ? "Change section" : "Enroll"}</Button> : null}
            {can("students.lifecycle") ? <Button variant="outline" onClick={() => setDialog("status")}>Change status</Button> : null}
            {current ? <DownloadButton path={`/school/students/${id}/id-card/pdf/`} filename="id-card.pdf">ID card</DownloadButton> : null}
            {can("students.lifecycle") ? <DownloadButton path={`/school/students/${id}/certificate/pdf/`} filename="certificate.pdf">Certificate</DownloadButton> : null}
            {can("students.lifecycle") ? <Button variant="outline" onClick={() => setDialog("delete")}>Delete</Button> : null}
          </>
        }
      />
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "overview" ? (
        <dl className="grid gap-4 rounded-lg border bg-card p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-3">
          <Detail label="Status" value={student.status} /><Detail label="Gender" value={student.gender} /><Detail label="Date of birth" value={formatDate(student.date_of_birth)} />
          <Detail label="Admission date" value={formatDate(student.admission_date)} /><Detail label="Phone" value={student.phone} /><Detail label="Email" value={student.email} />
          <Detail label="Blood group" value={student.blood_group} /><Detail label="Roll number" value={current?.roll_number} /><Detail label="Address" value={student.address} /><Detail label="Notes" value={student.notes} />
        </dl>
      ) : null}
      {tab === "guardians" ? <GuardiansTab studentId={id} links={student.guardians ?? []} canManage={can("guardians.manage")} /> : null}
      {tab === "documents" ? <DocumentsTab studentId={id} canManage={can("students.manage")} /> : null}
      {tab === "attendance" ? <AttendanceTab studentId={id} /> : null}
      {tab === "fees" ? <DataTable columns={invoiceColumns} rows={invoices.data?.results} rowKey={(i) => i.id} isLoading={invoices.isLoading} error={invoices.error} emptyTitle="No invoices" /> : null}
      {tab === "results" ? <DataTable columns={resultColumns} rows={results.data?.results} rowKey={(r) => r.id} isLoading={results.isLoading} error={results.error} emptyTitle="No published results" /> : null}

      <SpecFormDialog wide open={dialog === "edit"} title="Edit student" fields={studentFields(can("school.users.manage") ? toOptions(studentAccounts.options, (u) => `${u.first_name} ${u.last_name} (${u.email})`) : undefined)} initial={student as never} imageUrls={{ photo: student.photo_url }} onClose={() => setDialog(null)} onSubmit={(v) => update.mutateAsync({ id, body: v })} />
      <SpecFormDialog open={dialog === "status"} title="Change status" submitLabel="Update" onClose={() => setDialog(null)} initial={{ status: student.status }}
        fields={[{ name: "status", label: "New status", type: "select", required: true, options: STUDENT_STATUS_OPTIONS }, { name: "reason", label: "Reason", type: "textarea" }]}
        onSubmit={(v) => changeStatus.mutateAsync({ id, status: String(v.status), reason: String(v.reason ?? "") })} />
      <SpecFormDialog open={dialog === "class"} title={current ? "Change section" : "Enroll in the current session"} submitLabel="Save" onClose={() => setDialog(null)}
        fields={[{ name: "section", label: "Section", type: "select", required: true, options: toOptions(sections.options, sectionLabel) }]}
        onSubmit={(v) => (current ? move.mutateAsync({ id: current.enrollment_id, section: String(v.section) }) : enroll.mutateAsync({ student: id, section: String(v.section) }))} />
      <ConfirmDialog open={dialog === "delete"} title="Delete student" description="The record is archived, not erased: enrollments, marks and invoices are kept for the school's records."
        confirmLabel="Delete student" destructive isPending={remove.isPending} error={remove.error ? serverMessage(remove.error) : null} onCancel={() => setDialog(null)}
        onConfirm={() => remove.mutate(id, { onSuccess: () => router.replace("/students") })} />
    </>
  );
}
