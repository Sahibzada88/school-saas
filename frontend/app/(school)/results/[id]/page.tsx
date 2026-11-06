"use client";

import { ArrowLeft, Printer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DownloadButton } from "@/components/common/DownloadButton";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/common/Skeleton";
import { Badge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { FormAlert } from "@/components/common/FormAlert";
import { TextareaField } from "@/components/common/TextareaField";
import { useResultDetail, useSaveRemarks } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { serverMessage } from "@/lib/forms";
import { useState } from "react";
import type { ReportCardDetail } from "@/types/school";

function RemarksForm({ card }: { card: ReportCardDetail }) {
  const { can, user } = useAuth();
  const save = useSaveRemarks();
  const isAdmin = user?.role === "SCHOOL_ADMIN";
  const [teacher, setTeacher] = useState(card.teacher_remarks);
  const [principal, setPrincipal] = useState(card.principal_remarks);
  const [saved, setSaved] = useState(false);
  if (!can("marks.enter")) return null;
  return (
    <section className="space-y-3 rounded-lg border bg-card p-4 shadow-sm print:hidden">
      <h2 className="font-medium">Remarks</h2>
      <TextareaField label="Teacher's remarks" value={teacher} maxLength={300} onChange={(e) => { setSaved(false); setTeacher(e.target.value); }} />
      {isAdmin ? <TextareaField label="Principal's remarks" value={principal} maxLength={300} onChange={(e) => { setSaved(false); setPrincipal(e.target.value); }} /> : null}
      {save.error ? <FormAlert>{serverMessage(save.error)}</FormAlert> : null}
      {saved ? <FormAlert variant="success">Remarks saved. They appear on the report card PDF.</FormAlert> : null}
      <Button disabled={save.isPending} onClick={() => save.mutate({ id: card.id, body: { teacher_remarks: teacher, ...(isAdmin ? { principal_remarks: principal } : {}) } }, { onSuccess: () => setSaved(true) })}>Save remarks</Button>
    </section>
  );
}

export default function ResultDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: card, isLoading, error, refetch } = useResultDetail(id);
  if (error) return <div className="rounded-lg border bg-card"><ErrorState error={error} onRetry={() => void refetch()} /></div>;
  if (isLoading || !card) return <Skeleton className="h-96 w-full" />;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link href="/results" className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:underline"><ArrowLeft className="size-4" /> All results</Link>
        <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => window.print()}><Printer className="size-4" /> Print</Button><DownloadButton path={`/school/results/${id}/pdf/`} filename="report-card.pdf" variant="default">Download PDF</DownloadButton></div>
      </div>
      <article className="space-y-6 rounded-lg border bg-card p-6 shadow-sm print:border-0 print:shadow-none">
        <header className="text-center"><h1 className="text-2xl font-semibold">{card.school_name}</h1><p className="text-muted-foreground">Report card · {card.exam_name} · {card.session_name}</p></header>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-muted-foreground">Student</dt><dd className="font-medium">{card.student_name}</dd></div>
          <div><dt className="text-muted-foreground">Student number</dt><dd className="font-medium">{card.student_number}</dd></div>
          <div><dt className="text-muted-foreground">Class / Section</dt><dd className="font-medium">{card.class_name} - {card.section_name}</dd></div>
          <div><dt className="text-muted-foreground">Roll number</dt><dd className="font-medium">{card.roll_number ?? "—"}</dd></div>
        </dl>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="py-2">Subject</th><th className="py-2 text-right">Total</th><th className="py-2 text-right">Obtained</th><th className="py-2 text-center">Grade</th><th className="py-2 text-right">Result</th></tr></thead>
          <tbody className="divide-y">{card.breakdown.lines.map((l) => (
            <tr key={l.subject}><td className="py-2">{l.subject}</td><td className="py-2 text-right tabular-nums">{l.total}</td><td className="py-2 text-right tabular-nums">{l.is_absent ? "Absent" : l.obtained}</td><td className="py-2 text-center">{l.grade}</td><td className="py-2 text-right">{l.is_pass ? "Pass" : "Fail"}</td></tr>
          ))}</tbody>
        </table></div>
        <dl className="grid gap-3 rounded-md bg-muted/50 p-4 text-sm sm:grid-cols-4">
          <div><dt className="text-muted-foreground">Total</dt><dd className="text-lg font-semibold tabular-nums">{card.obtained_marks} / {card.total_marks}</dd></div>
          <div><dt className="text-muted-foreground">Percentage</dt><dd className="text-lg font-semibold tabular-nums">{card.percentage}%</dd></div>
          <div><dt className="text-muted-foreground">Grade · GPA</dt><dd className="text-lg font-semibold">{card.grade} · {card.gpa}</dd></div>
          <div><dt className="text-muted-foreground">Position</dt><dd className="text-lg font-semibold">{card.position_section ?? "—"} <span className="text-xs font-normal text-muted-foreground">(class {card.position_class ?? "—"})</span></dd></div>
        </dl>
        <p className="text-center"><Badge tone={card.result_status === "PASS" ? "green" : "red"}>{card.result_status}</Badge></p>
        {card.teacher_remarks ? <p className="text-sm"><strong>Teacher&apos;s remarks:</strong> {card.teacher_remarks}</p> : null}
        {card.principal_remarks ? <p className="text-sm"><strong>Principal&apos;s remarks:</strong> {card.principal_remarks}</p> : null}
      </article>
      <RemarksForm key={card.id} card={card} />
    </div>
  );
}
