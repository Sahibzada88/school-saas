"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { ResourceManager } from "@/components/common/ResourceManager";
import { Badge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { EXAM_TONES } from "@/features/exams/constants";
import { GradingScaleDialog } from "@/features/exams/GradingScaleDialog";
import { examHooks, examTypeHooks, gradingScaleHooks } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { formatDate, humanizeCode } from "@/lib/format";
import { toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { AcademicSession, Exam, ExamType, GradingScale } from "@/types/school";

export default function ExamsPage() {
  const { can } = useAuth();
  const manage = can("exams.manage");
  const [tab, setTab] = useState<"exams" | "grading" | "types">("exams");
  const [scale, setScale] = useState<"new" | GradingScale | null>(null);
  const sessions = useAllOptions<AcademicSession>("/school/sessions", {}, manage);
  const types = useAllOptions<ExamType>("/school/exam-types", {}, manage);
  const scales = gradingScaleHooks.useList({ page_size: 50 }, manage && tab === "grading");

  const scaleColumns: Column<GradingScale>[] = [
    { key: "n", header: "Scale", cell: (s) => <span className="font-medium">{s.name}{s.is_default ? " (default)" : ""}</span> },
    { key: "b", header: "Grades", cell: (s) => s.bands.map((b) => `${b.grade} ${b.min_percent}–${b.max_percent}`).join(" · ") },
    { key: "a", header: "", className: "text-right", cell: (s) => <Button variant="outline" size="sm" onClick={() => setScale(s)}>Edit</Button> },
  ];

  return (
    <>
      <PageHeader title="Exams" description={manage ? "Plan exams, enter marks and publish results." : "Published exams and results."} />
      <Tabs tabs={[{ value: "exams", label: "Exams" }, ...(manage ? [{ value: "grading" as const, label: "Grading scales" }, { value: "types" as const, label: "Exam types" }] : [])]} value={tab} onChange={setTab} />
      {tab === "exams" ? (
        <ResourceManager<Exam> noun="exam" hooks={examHooks} canManage={manage} allowEdit={manage} rowLabel={(e) => e.name}
          fields={[
            { name: "name", label: "Exam name", type: "text", required: true, placeholder: "Midterm 2027" },
            { name: "session", label: "Session", type: "select", required: true, options: toOptions(sessions.options, (s) => s.name) },
            { name: "exam_type", label: "Exam type", type: "select", required: true, options: toOptions(types.options, (t) => t.name) },
            { name: "start_date", label: "Starts", type: "date", nullable: true }, { name: "end_date", label: "Ends", type: "date", nullable: true },
          ]}
          columns={[
            { key: "n", header: "Exam", cell: (e) => <Link href={`/exams/${e.id}`} className="font-medium underline-offset-4 hover:underline">{e.name}</Link> },
            { key: "t", header: "Type", cell: (e) => e.exam_type_name }, { key: "s", header: "Session", cell: (e) => e.session_name },
            { key: "d", header: "Dates", cell: (e) => (e.start_date ? `${formatDate(e.start_date)} – ${formatDate(e.end_date)}` : "—") },
            { key: "c", header: "Subjects", cell: (e) => e.subject_count },
            { key: "st", header: "Status", cell: (e) => <Badge tone={EXAM_TONES[e.status]}>{humanizeCode(e.status)}</Badge> },
          ]} />
      ) : null}
      {tab === "grading" ? (
        <div className="space-y-3">
          <div className="flex justify-end"><Button onClick={() => setScale("new")}>Add grading scale</Button></div>
          <DataTable columns={scaleColumns} rows={scales.data?.results} rowKey={(s) => s.id} isLoading={scales.isLoading} error={scales.error} emptyTitle="No grading scales" />
          <GradingScaleDialog target={scale} onClose={() => setScale(null)} />
        </div>
      ) : null}
      {tab === "types" ? (
        <ResourceManager<ExamType> noun="exam type" hooks={examTypeHooks} canManage={manage} rowLabel={(t) => t.name}
          fields={[{ name: "name", label: "Name", type: "text", required: true }]} columns={[{ key: "n", header: "Exam type", cell: (t) => <span className="font-medium">{t.name}</span> }]} />
      ) : null}
    </>
  );
}
