"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormAlert } from "@/components/common/FormAlert";
import { SelectField } from "@/components/common/SelectField";
import { Button } from "@/components/ui/button";
import { enrollmentHooks, usePromote } from "@/features/school/resources";
import { serverMessage } from "@/lib/forms";
import { sectionLabel, toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { AcademicSession, Enrollment, Section } from "@/types/school";

type Outcome = "PROMOTE" | "REPEAT" | "GRADUATE";
const OUTCOMES: { value: Outcome; label: string }[] = [
  { value: "PROMOTE", label: "Promote" }, { value: "REPEAT", label: "Repeat" }, { value: "GRADUATE", label: "Graduate" },
];

/** Year-end processing, one section at a time: pick the students' outcome, the target sections, then confirm. */
export function PromotionPanel() {
  const sessions = useAllOptions<AcademicSession>("/school/sessions");
  const sections = useAllOptions<Section>("/school/sections");
  const promote = usePromote();
  const [fromSession, setFromSession] = useState("");
  const [toSession, setToSession] = useState("");
  const [fromSection, setFromSection] = useState("");
  const [promoteTo, setPromoteTo] = useState("");
  const [repeatTo, setRepeatTo] = useState("");
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const currentId = sessions.options.find((s) => s.is_current)?.id ?? "";
  const from = fromSession || currentId;
  const list = enrollmentHooks.useList({ session: from, section: fromSection, status: "ENROLLED", page_size: 100 }, Boolean(from && fromSection));
  const rows = list.data?.results ?? [];
  const outcomeOf = (id: string): Outcome => outcomes[id] ?? "PROMOTE";
  const needs = (o: Outcome) => rows.some((r) => outcomeOf(r.id) === o);
  const problem =
    !from || !toSession ? "Choose the session you are moving from and into."
    : from === toSession ? "The target session must be different."
    : rows.length === 0 ? "Choose a section that has enrolled students."
    : needs("PROMOTE") && !promoteTo ? "Choose the section promoted students go to."
    : needs("REPEAT") && !repeatTo ? "Choose the section repeating students go to."
    : null;

  const columns: Column<Enrollment>[] = [
    { key: "r", header: "Roll", cell: (e) => e.roll_number ?? "—" },
    { key: "n", header: "Student", cell: (e) => <div className="leading-tight"><span className="font-medium">{e.student_name}</span><div className="text-xs text-muted-foreground">{e.student_number}</div></div> },
    {
      key: "o", header: "Outcome",
      cell: (e) => (
        <select aria-label={`Outcome for ${e.student_name}`} value={outcomeOf(e.id)} onChange={(ev) => { setResult(null); setOutcomes((m) => ({ ...m, [e.id]: ev.target.value as Outcome })); }}
          className="h-9 rounded-md border border-input bg-background px-2 text-sm">
          {OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ),
    },
  ];
  const sessionOptions = toOptions(sessions.options, (s) => s.name + (s.is_current ? " (current)" : ""));
  const sectionOptions = toOptions(sections.options, sectionLabel);

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Move a section's students into the next session. Create the new session (and its classes/sections) first. Students marked <strong>Graduate</strong> leave the school; promoted and repeating students get a new enrollment in the target session. Do one section at a time.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <SelectField label="From session" value={from} onChange={(e) => { setFromSession(e.target.value); setOutcomes({}); }}><option value="">Choose…</option>{sessionOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
        <SelectField label="Into session" value={toSession} onChange={(e) => setToSession(e.target.value)}><option value="">Choose…</option>{sessionOptions.filter((o) => o.value !== from).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
        <SelectField label="Section being processed" value={fromSection} onChange={(e) => { setFromSection(e.target.value); setOutcomes({}); setResult(null); }}><option value="">Choose…</option>{sectionOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
        <SelectField label="Promoted students go to" value={promoteTo} onChange={(e) => setPromoteTo(e.target.value)}><option value="">Choose…</option>{sectionOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
        <SelectField label="Repeating students go to" value={repeatTo} onChange={(e) => setRepeatTo(e.target.value)}><option value="">Choose…</option>{sectionOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
      </div>
      {fromSection ? <DataTable columns={columns} rows={rows} rowKey={(e) => e.id} isLoading={list.isLoading} error={list.error} emptyTitle="No enrolled students in this section for that session" /> : null}
      {result ? <FormAlert variant="success">{result}</FormAlert> : null}
      {problem && fromSection ? <p className="text-sm text-muted-foreground">{problem}</p> : null}
      <Button disabled={Boolean(problem) || promote.isPending} onClick={() => setConfirming(true)}>Process {rows.length || ""} student(s)</Button>
      <ConfirmDialog
        open={confirming} title="Process year-end for this section" confirmLabel="Process" isPending={promote.isPending}
        description={`${rows.filter((r) => outcomeOf(r.id) === "PROMOTE").length} promoted, ${rows.filter((r) => outcomeOf(r.id) === "REPEAT").length} repeating, ${rows.filter((r) => outcomeOf(r.id) === "GRADUATE").length} graduating. This cannot be undone from here.`}
        error={promote.error ? serverMessage(promote.error) : null} onCancel={() => { setConfirming(false); promote.reset(); }}
        onConfirm={() =>
          promote.mutate(
            {
              from_session: from, to_session: toSession, ...(promoteTo ? { promote_to: promoteTo } : {}), ...(repeatTo ? { repeat_to: repeatTo } : {}),
              decisions: rows.map((r) => ({ enrollment: r.id, outcome: outcomeOf(r.id) })),
            },
            { onSuccess: (r) => { setConfirming(false); setOutcomes({}); setResult(`Done: ${r.promoted} promoted, ${r.repeated} repeating, ${r.graduated} graduated.`); } },
          )
        }
      />
    </div>
  );
}
