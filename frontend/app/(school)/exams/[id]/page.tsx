"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { ErrorState } from "@/components/common/ErrorState";
import { FormAlert } from "@/components/common/FormAlert";
import { PageHeader } from "@/components/common/PageHeader";
import { ResourceManager } from "@/components/common/ResourceManager";
import { SelectField } from "@/components/common/SelectField";
import { Skeleton } from "@/components/common/Skeleton";
import { Badge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { EXAM_TONES } from "@/features/exams/constants";
import {
  examHooks, examSubjectHooks, resultHooks, useExamAction, useExamAnalysis, useExamPreview, useExamSubjects, useMarksRoster, useSaveMarks,
} from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { formatDate, humanizeCode } from "@/lib/format";
import { serverMessage } from "@/lib/forms";
import { toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { ExamSubject, MarksRoster, PreviewResult, ReportCardSummary, SchoolClass, Subject } from "@/types/school";

type Tab = "schedule" | "marks" | "results";

function MarksEditor({ examId, examSubject, roster }: { examId: string; examSubject: string; roster: MarksRoster }) {
  const save = useSaveMarks(examId);
  const [values, setValues] = useState<Record<string, { marks: string; absent: boolean }>>(() =>
    Object.fromEntries(roster.rows.map((r) => [r.student, { marks: r.obtained_marks ?? "", absent: r.is_absent }])),
  );
  const [saved, setSaved] = useState(false);
  const edit = (id: string, patch: Partial<{ marks: string; absent: boolean }>) => { setSaved(false); setValues((v) => ({ ...v, [id]: { ...v[id], ...patch } })); };
  if (roster.rows.length === 0) return <p className="rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">No students to enter marks for (check your section assignment).</p>;
  const invalid = roster.rows.some((r) => { const n = Number(values[r.student]?.marks); return values[r.student]?.marks !== "" && !values[r.student]?.absent && (Number.isNaN(n) || n < 0 || n > Number(roster.total_marks)); });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Total {roster.total_marks} · pass mark {roster.passing_marks}. Leave a cell empty to clear a mark.</p>
      <ul className="divide-y rounded-lg border bg-card shadow-sm">
        {roster.rows.map((r) => (
          <li key={r.student} className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
            <div className="leading-tight"><span className="font-medium">{r.roll_number ? `${r.roll_number}. ` : ""}{r.student_name}</span><div className="text-xs text-muted-foreground">{r.student_number} · {r.section}</div></div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" disabled={!roster.open} checked={values[r.student]?.absent ?? false} onChange={(e) => edit(r.student, { absent: e.target.checked })} /> Absent</label>
              <input aria-label={`Marks for ${r.student_name}`} inputMode="decimal" disabled={!roster.open || values[r.student]?.absent} value={values[r.student]?.absent ? "" : values[r.student]?.marks ?? ""} onChange={(e) => edit(r.student, { marks: e.target.value })}
                className="h-9 w-24 rounded-md border border-input bg-background px-2 text-right text-sm disabled:opacity-50" />
            </div>
          </li>
        ))}
      </ul>
      {save.error ? <FormAlert>{serverMessage(save.error)}</FormAlert> : null}
      {saved ? <FormAlert variant="success">Marks saved.</FormAlert> : null}
      {!roster.open ? <FormAlert>Marks entry is closed for this exam.</FormAlert> : null}
      <Button disabled={!roster.open || save.isPending || invalid} onClick={() => save.mutate({
        exam_subject: examSubject,
        entries: roster.rows.map((r) => ({ student: r.student, is_absent: values[r.student]?.absent ?? false, ...(values[r.student]?.marks !== "" && !values[r.student]?.absent ? { obtained_marks: values[r.student].marks } : {}) })),
      }, { onSuccess: () => setSaved(true) })}>{save.isPending ? "Saving…" : "Save marks"}</Button>
      {invalid ? <p className="text-sm text-destructive">Marks must be between 0 and {roster.total_marks}.</p> : null}
    </div>
  );
}

function MarksTab({ examId }: { examId: string }) {
  const subjects = useExamSubjects(examId);
  const [subject, setSubject] = useState("");
  const roster = useMarksRoster(examId, subject);
  return (
    <div className="space-y-4">
      <div className="max-w-sm"><SelectField label="Subject" value={subject} onChange={(e) => setSubject(e.target.value)}><option value="">Choose a subject…</option>{(subjects.data ?? []).map((s) => <option key={s.id} value={s.id}>Class {s.class_name} · {s.subject_name}</option>)}</SelectField></div>
      {!subject ? null : roster.error ? <div className="rounded-lg border bg-card"><ErrorState error={roster.error} onRetry={() => void roster.refetch()} /></div> : roster.isLoading || !roster.data ? <Skeleton className="h-48 w-full" /> : <MarksEditor key={`${subject}-${roster.dataUpdatedAt}`} examId={examId} examSubject={subject} roster={roster.data} />}
    </div>
  );
}

function ResultsTab({ examId, status }: { examId: string; status: string }) {
  const { can } = useAuth();
  const admin = can("results.publish");
  const preview = useExamPreview(examId, admin && status !== "DRAFT");
  const published = resultHooks.useList({ exam: examId, page_size: 100 }, !admin);
  const analysis = useExamAnalysis(admin && (status === "PUBLISHED" || status === "ARCHIVED") ? examId : "");
  const publish = useExamAction();
  const [confirming, setConfirming] = useState(false);
  const [force, setForce] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const rows = preview.data?.results ?? [];
  const missing = rows.reduce((n, r) => n + r.missing_marks, 0);

  const previewColumns: Column<PreviewResult>[] = [
    { key: "p", header: "#", cell: (r) => r.position_section ?? "—" }, { key: "n", header: "Student", cell: (r) => <div className="leading-tight"><span className="font-medium">{r.student_name}</span><div className="text-xs text-muted-foreground">{r.class_name}-{r.section_name}</div></div> },
    { key: "m", header: "Marks", cell: (r) => `${r.obtained_marks}/${r.total_marks}` }, { key: "pc", header: "%", cell: (r) => `${r.percentage}%` }, { key: "g", header: "Grade", cell: (r) => r.grade },
    { key: "r", header: "Result", cell: (r) => <Badge tone={r.result_status === "PASS" ? "green" : "red"}>{r.result_status}</Badge> },
    { key: "x", header: "Missing", cell: (r) => (r.missing_marks ? <Badge tone="amber">{r.missing_marks}</Badge> : "—") },
  ];
  const cardColumns: Column<ReportCardSummary>[] = [
    { key: "n", header: "Student", cell: (r) => <Link href={`/results/${r.id}`} className="font-medium underline-offset-4 hover:underline">{r.student_name}</Link> },
    { key: "m", header: "Marks", cell: (r) => `${r.obtained_marks}/${r.total_marks}` }, { key: "p", header: "%", cell: (r) => `${r.percentage}%` }, { key: "g", header: "Grade", cell: (r) => r.grade },
    { key: "r", header: "Result", cell: (r) => <Badge tone={r.result_status === "PASS" ? "green" : "red"}>{r.result_status}</Badge> },
  ];

  if (!admin) return <DataTable columns={cardColumns} rows={published.data?.results} rowKey={(r) => r.id} isLoading={published.isLoading} error={published.error} emptyTitle="Results are not published yet" />;
  if (status === "DRAFT") return <p className="rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">Schedule the exam first. Results are computed from the marks entered.</p>;
  return (
    <div className="space-y-4">
      {done ? <FormAlert variant="success">{done}</FormAlert> : null}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">Live preview from the marks entered so far (nothing is stored until you publish). {missing ? `${missing} mark(s) still missing.` : "All marks are in."}</p>
        {status !== "ARCHIVED" ? <Button onClick={() => { setForce(false); setConfirming(true); }} disabled={rows.length === 0}>{status === "PUBLISHED" ? "Recompute & republish" : "Publish results"}</Button> : null}
      </div>
      <DataTable columns={previewColumns} rows={rows} rowKey={(r) => r.student} isLoading={preview.isLoading} error={preview.error} onRetry={() => void preview.refetch()} emptyTitle="No enrolled students for this exam's classes" />
      {analysis.data ? (
        <section className="space-y-2 rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="font-medium">Analysis: {analysis.data.passed}/{analysis.data.students} passed ({analysis.data.pass_rate ?? "—"}%)</h2>
          <DataTable isLoading={false} rows={analysis.data.subjects} rowKey={(s) => `${s.class_name}-${s.subject}`} emptyTitle="No marks" columns={[
            { key: "s", header: "Subject", cell: (s) => `${s.subject} (class ${s.class_name})` }, { key: "a", header: "Average", cell: (s) => s.average ?? "—" }, { key: "h", header: "High", cell: (s) => s.highest ?? "—" },
            { key: "l", header: "Low", cell: (s) => s.lowest ?? "—" }, { key: "p", header: "Pass rate", cell: (s) => (s.pass_rate === null ? "—" : `${s.pass_rate}%`) }, { key: "ab", header: "Absent", cell: (s) => s.absent }]} />
        </section>
      ) : null}
      <ConfirmDialog open={confirming} title={status === "PUBLISHED" ? "Recompute results" : "Publish results"} confirmLabel={status === "PUBLISHED" ? "Recompute" : "Publish"}
        description="Report cards become visible to parents and students. Grades, positions and pass/fail are calculated from the current marks and grading scale."
        isPending={publish.isPending} error={publish.error ? serverMessage(publish.error) : null} confirmDisabled={missing > 0 && !force}
        onCancel={() => { setConfirming(false); publish.reset(); }}
        onConfirm={() => publish.mutate({ id: examId, action: "publish", body: { force } }, { onSuccess: () => { setConfirming(false); setDone("Results published."); } })}>
        {missing > 0 ? <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={force} onChange={(e) => setForce(e.target.checked)} /> {missing} mark(s) are missing. Publish anyway and count them as absent (zero).</label> : null}
      </ConfirmDialog>
    </div>
  );
}

export default function ExamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const { data: exam, isLoading, error, refetch } = examHooks.useGet(id);
  const action = useExamAction();
  const classes = useAllOptions<SchoolClass>("/school/classes", {}, can("exams.manage"));
  const subjects = useAllOptions<Subject>("/school/subjects", {}, can("exams.manage"));
  const [tab, setTab] = useState<Tab>("schedule");

  if (error) return <div className="rounded-lg border bg-card"><ErrorState error={error} onRetry={() => void refetch()} /></div>;
  if (isLoading || !exam) return <Skeleton className="h-40 w-full" />;
  const editable = can("exams.manage") && (exam.status === "DRAFT" || exam.status === "SCHEDULED");

  const columns: Column<ExamSubject>[] = [
    { key: "c", header: "Class", cell: (s) => s.class_name }, { key: "s", header: "Subject", cell: (s) => <span className="font-medium">{s.subject_name}</span> },
    { key: "d", header: "Date", cell: (s) => formatDate(s.exam_date) }, { key: "t", header: "Total", cell: (s) => s.total_marks }, { key: "p", header: "Passing", cell: (s) => s.passing_marks },
  ];

  return (
    <>
      <Link href="/exams" className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:underline"><ArrowLeft className="size-4" /> All exams</Link>
      <PageHeader
        title={<span className="flex flex-wrap items-center gap-3">{exam.name} <Badge tone={EXAM_TONES[exam.status]}>{humanizeCode(exam.status)}</Badge></span>}
        description={`${exam.exam_type_name} · ${exam.session_name}`}
        actions={
          <>
            {can("exams.manage") && exam.status === "DRAFT" ? <Button onClick={() => action.mutate({ id, action: "schedule" })} disabled={action.isPending}>Schedule exam</Button> : null}
            {can("exams.manage") && exam.status === "PUBLISHED" ? <Button variant="outline" onClick={() => action.mutate({ id, action: "archive" })} disabled={action.isPending}>Archive</Button> : null}
          </>
        }
      />
      {action.error ? <FormAlert>{serverMessage(action.error)}</FormAlert> : null}
      <Tabs tabs={[{ value: "schedule", label: "Schedule" }, ...(can("marks.enter") ? [{ value: "marks" as const, label: "Marks entry" }] : []), { value: "results", label: "Results" }]} value={tab} onChange={setTab} />
      {tab === "schedule" ? (
        <ResourceManager<ExamSubject> noun="exam subject" hooks={examSubjectHooks} canManage={editable} params={{ exam: id, page_size: 100 }} extraBody={{ exam: id }} wide rowLabel={(s) => s.subject_name} columns={columns}
          emptyDescription="Add each subject (and class) that sits this exam, then schedule the exam."
          fields={[
            { name: "school_class", label: "Class", type: "select", required: true, options: toOptions(classes.options, (c) => c.name) },
            { name: "subject", label: "Subject", type: "select", required: true, options: toOptions(subjects.options, (s) => s.name) },
            { name: "exam_date", label: "Date", type: "date", nullable: true }, { name: "start_time", label: "Start time", type: "time", nullable: true },
            { name: "duration_minutes", label: "Duration (minutes)", type: "number", nullable: true }, { name: "total_marks", label: "Total marks", type: "number", required: true, step: "0.01" },
            { name: "passing_marks", label: "Passing marks", type: "number", required: true, step: "0.01" },
          ]} />
      ) : null}
      {tab === "marks" ? <MarksTab examId={id} /> : null}
      {tab === "results" ? <ResultsTab examId={id} status={exam.status} /> : null}
    </>
  );
}
