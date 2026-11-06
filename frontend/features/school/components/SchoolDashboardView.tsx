"use client";

import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";

import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { Badge } from "@/components/common/StatusBadge";
import { AuditLogTable } from "@/features/audit/components/AuditLogTable";
import { useSchoolDashboard } from "@/features/school/hooks";
import { formatDate, formatMoney, humanizeCode } from "@/lib/format";

const CHECKLIST_LINKS: Record<string, string> = { profile: "/settings", team: "/settings", classes: "/classes", teachers: "/teachers", students: "/students" };

export function SchoolDashboardView() {
  const { data, isLoading, error, refetch } = useSchoolDashboard();

  if (error) {
    return (
      <div className="rounded-lg border bg-card">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    );
  }

  const att = data?.attendance_today;
  const pending = (data?.checklist ?? []).filter((item) => !item.done).length;

  return (
    <>
      <PageHeader title="Dashboard" description={data ? `${data.school.name} · ${data.school.city}, ${data.school.country}` : undefined} />

      <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Students" value={data?.students.active} hint={data ? `${data.students.total} on record` : undefined} isLoading={isLoading} />
        <StatCard label="Teachers" value={data?.teachers.active} hint={data ? `${data.teachers.total} on record` : undefined} isLoading={isLoading} />
        <StatCard
          label="Today's attendance"
          value={att ? (att.marked === 0 ? "Not marked" : `${att.percentage ?? 0}%`) : undefined}
          hint={att ? `${att.marked} of ${att.enrolled} marked · ${att.counts.ABSENT ?? 0} absent` : undefined}
          isLoading={isLoading}
        />
        <StatCard
          label="Outstanding fees"
          value={data ? formatMoney(data.fees.outstanding_total, data.fees.currency) : undefined}
          hint={data ? `${data.fees.outstanding_count} open invoices · ${data.fees.overdue_count} overdue` : undefined}
          isLoading={isLoading}
        />
        <StatCard label="Active users" value={data?.users.active} hint={data ? `${data.users.total} accounts` : undefined} isLoading={isLoading} />
        <StatCard label="Upcoming exams" value={data?.upcoming_exams.length} isLoading={isLoading} />
      </section>

      {data && data.upcoming_exams.length > 0 ? (
        <section className="space-y-2 rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="font-medium">Upcoming exams</h2>
          <ul className="divide-y text-sm">
            {data.upcoming_exams.map((e) => (
              <li key={e.id} className="flex items-center justify-between py-2">
                <Link href={`/exams/${e.id}`} className="font-medium underline-offset-4 hover:underline">{e.name}</Link>
                <span className="flex items-center gap-2 text-muted-foreground">{e.start_date ? formatDate(e.start_date) : "Date not set"}<Badge tone="blue">{humanizeCode(e.status)}</Badge></span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {pending > 0 || isLoading ? (
        <section className="space-y-3 rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="font-medium">Getting started</h2>
          <ul className="space-y-2 text-sm">
            {(data?.checklist ?? []).map((item) => (
              <li key={item.key} className="flex items-center gap-2">
                {item.done ? <CheckCircle2 className="size-4 text-green-600" aria-label="Done" /> : <Circle className="size-4 text-muted-foreground" aria-label="To do" />}
                {item.done ? <span className="text-muted-foreground line-through">{item.label}</span> : <Link href={CHECKLIST_LINKS[item.key] ?? "/settings"} className="underline-offset-4 hover:underline">{item.label}</Link>}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="space-y-3">
        <h2 className="font-medium">Recent activity</h2>
        <AuditLogTable rows={data?.recent_activity} isLoading={isLoading} />
      </section>
    </>
  );
}
