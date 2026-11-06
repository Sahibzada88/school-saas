"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { DownloadButton } from "@/components/common/DownloadButton";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { SelectField } from "@/components/common/SelectField";
import { Badge } from "@/components/common/StatusBadge";
import { resultHooks } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { Exam, ReportCardSummary } from "@/types/school";

export default function ResultsPage() {
  const { can } = useAuth();
  const [exam, setExam] = useState("");
  const [page, setPage] = useState(1);
  const exams = useAllOptions<Exam>("/school/exams");
  const { data, isLoading, isFetching, error, refetch } = resultHooks.useList({ page, exam: exam || undefined });
  const columns: Column<ReportCardSummary>[] = [
    { key: "s", header: "Student", cell: (r) => <div className="leading-tight"><Link href={`/results/${r.id}`} className="font-medium underline-offset-4 hover:underline">{r.student_name}</Link><div className="text-xs text-muted-foreground">{r.student_number}</div></div> },
    { key: "e", header: "Exam", cell: (r) => r.exam_name }, { key: "c", header: "Class", cell: (r) => `${r.class_name}-${r.section_name}` },
    { key: "m", header: "Marks", className: "tabular-nums", cell: (r) => `${r.obtained_marks}/${r.total_marks}` }, { key: "p", header: "%", className: "tabular-nums", cell: (r) => `${r.percentage}%` },
    { key: "g", header: "Grade", cell: (r) => r.grade }, { key: "pos", header: "Position", cell: (r) => r.position_section ?? "—" },
    { key: "r", header: "Result", cell: (r) => <Badge tone={r.result_status === "PASS" ? "green" : "red"}>{r.result_status}</Badge> },
    { key: "d", header: "", className: "text-right", cell: (r) => <DownloadButton path={`/school/results/${r.id}/pdf/`} filename="report-card.pdf">PDF</DownloadButton> },
  ];
  return (
    <>
      <PageHeader title="Results" description="Published report cards."
        actions={exam && can("exports.exams") ? <DownloadButton path="/school/exports/results/csv/" filename="results.csv" query={{ exam }}>CSV</DownloadButton> : null} />
      <div className="max-w-sm">
        <SelectField label="Exam" value={exam} onChange={(e) => { setExam(e.target.value); setPage(1); }}>
          <option value="">All exams</option>{toOptions(exams.options, (e) => e.name).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </SelectField>
      </div>
      <DataTable columns={columns} rows={data?.results} rowKey={(r) => r.id} isLoading={isLoading} error={error} onRetry={() => void refetch()} emptyTitle="No published results" emptyDescription="Results appear here once an exam is published." />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </>
  );
}
