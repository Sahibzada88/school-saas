"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField } from "@/components/common/SelectField";
import { Skeleton } from "@/components/common/Skeleton";
import { SpecFormDialog, type FieldSpec } from "@/components/common/SpecForm";
import { Button } from "@/components/ui/button";
import { timetableHooks } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { serverMessage } from "@/lib/forms";
import { WEEKDAYS, sectionLabel, toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { AcademicSession, Section, Subject, Teacher, TimetableSlot } from "@/types/school";

const DAYS = [0, 1, 2, 3, 4, 5];
const hhmm = (t: string) => t.slice(0, 5);

export default function TimetablePage() {
  const { can } = useAuth();
  const manage = can("timetable.manage");
  const sections = useAllOptions<Section>("/school/sections");
  const sessions = useAllOptions<AcademicSession>("/school/sessions");
  const subjects = useAllOptions<Subject>("/school/subjects", {}, manage);
  const teachers = useAllOptions<Teacher>("/school/teachers", {}, manage);
  const [section, setSection] = useState("");
  const { data, isLoading, error, refetch } = timetableHooks.useList({ section: section || undefined, page_size: 100 });
  const create = timetableHooks.useCreate();
  const update = timetableHooks.useUpdate();
  const remove = timetableHooks.useRemove();
  const [editing, setEditing] = useState<{ slot?: TimetableSlot; weekday?: number; period?: number } | null>(null);
  const [deleting, setDeleting] = useState<TimetableSlot | null>(null);

  const slots = data?.results ?? [];
  const periods = Array.from(new Set([...slots.map((s) => s.period_no), ...(manage && section ? [1, 2, 3, 4, 5, 6] : [])])).sort((a, b) => a - b);
  const current = sessions.options.find((s) => s.is_current);
  const fields: FieldSpec[] = [
    { name: "subject", label: "Subject", type: "select", required: true, options: toOptions(subjects.options, (s) => s.name) },
    { name: "teacher", label: "Teacher", type: "select", required: true, options: toOptions(teachers.options, (t) => t.full_name) },
    { name: "weekday", label: "Day", type: "select", required: true, options: WEEKDAYS.map((d, i) => ({ value: String(i), label: d })) },
    { name: "period_no", label: "Period", type: "number", required: true, min: 1 },
    { name: "start_time", label: "Starts", type: "time", required: true }, { name: "end_time", label: "Ends", type: "time", required: true },
    { name: "room", label: "Room", type: "text" },
  ];

  return (
    <>
      <PageHeader title="Timetable" description={manage ? "Weekly plan per section. Teacher clashes are rejected." : "Your weekly schedule."} />
      <div className="max-w-sm">
        <SelectField label="Section" value={section} onChange={(e) => setSection(e.target.value)}>
          <option value="">{manage ? "Choose a section…" : "All"}</option>
          {toOptions(sections.options, sectionLabel).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </SelectField>
      </div>
      {error ? <div className="rounded-lg border bg-card"><ErrorState error={error} onRetry={() => void refetch()} /></div> : isLoading ? <Skeleton className="h-64 w-full" /> : (
        <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr><th className="px-3 py-2 text-left">Period</th>{DAYS.map((d) => <th key={d} className="px-3 py-2 text-left">{WEEKDAYS[d]}</th>)}</tr>
            </thead>
            <tbody className="divide-y">
              {periods.length === 0 ? <tr><td colSpan={7} className="px-3 py-10 text-center text-muted-foreground">{manage && !section ? "Choose a section to plan its timetable." : "No timetable entries yet."}</td></tr> : null}
              {periods.map((p) => (
                <tr key={p}>
                  <th scope="row" className="px-3 py-2 text-left font-medium">{p}</th>
                  {DAYS.map((d) => {
                    const slot = slots.find((s) => s.weekday === d && s.period_no === p);
                    return (
                      <td key={d} className="px-3 py-2 align-top">
                        {slot ? (
                          <div className="relative">
                            <button type="button" disabled={!manage} onClick={() => setEditing({ slot })} className="w-full rounded-md bg-primary/10 p-2 text-left leading-tight hover:bg-primary/20 disabled:cursor-default">
                              <div className="font-medium">{slot.subject_name}</div>
                              <div className="text-xs text-muted-foreground">{slot.teacher_name}</div>
                              <div className="text-xs text-muted-foreground">{hhmm(slot.start_time)}–{hhmm(slot.end_time)}{slot.room ? ` · ${slot.room}` : ""}{!section ? ` · ${slot.section_name}` : ""}</div>
                            </button>
                            {manage ? <button type="button" aria-label="Remove period" onClick={() => setDeleting(slot)} className="absolute right-1 top-1 rounded p-0.5 text-muted-foreground hover:bg-background"><X className="size-3" /></button> : null}
                          </div>
                        ) : manage && section ? (
                          <button type="button" aria-label={`Add ${WEEKDAYS[d]} period ${p}`} onClick={() => setEditing({ weekday: d, period: p })} className="flex w-full justify-center rounded-md border border-dashed p-2 text-muted-foreground hover:bg-muted/50"><Plus className="size-4" /></button>
                        ) : null}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {manage && section ? <Button variant="outline" onClick={() => setEditing({})}><Plus className="size-4" /> Add a period</Button> : null}

      <SpecFormDialog wide open={editing !== null} title={editing?.slot ? "Edit period" : "Add a period"} fields={fields} onClose={() => setEditing(null)}
        initial={editing?.slot ? { ...editing.slot, weekday: String(editing.slot.weekday), start_time: hhmm(editing.slot.start_time), end_time: hhmm(editing.slot.end_time) } : { weekday: editing?.weekday !== undefined ? String(editing.weekday) : "", period_no: editing?.period ?? "" }}
        onSubmit={async (v) => {
          const body = { ...v, weekday: Number(v.weekday), session: current?.id, section };
          if (editing?.slot) await update.mutateAsync({ id: editing.slot.id, body });
          else await create.mutateAsync(body);
        }} />
      <ConfirmDialog open={deleting !== null} title="Remove period" description="This period is removed from the timetable." confirmLabel="Remove" destructive isPending={remove.isPending}
        error={remove.error ? serverMessage(remove.error) : null} onCancel={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })} />
    </>
  );
}
