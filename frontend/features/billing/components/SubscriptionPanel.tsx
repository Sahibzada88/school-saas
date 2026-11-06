"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { Skeleton } from "@/components/common/Skeleton";
import { SubscriptionStateBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { RecordPaymentDialog } from "@/features/billing/components/RecordPaymentDialog";
import { SubscriptionActionDialog } from "@/features/billing/components/SubscriptionActionDialog";
import { useSubscriptionEvents } from "@/features/platform/hooks";
import type { PlatformSchoolDetail, SubscriptionAction, SubscriptionEvent } from "@/features/platform/types";
import { formatDate, formatDateTime, humanizeCode } from "@/lib/format";

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

const EVENT_COLUMNS: Column<SubscriptionEvent>[] = [
  { key: "when", header: "When", cell: (e) => <span className="whitespace-nowrap">{formatDateTime(e.created_at)}</span> },
  { key: "type", header: "Event", cell: (e) => humanizeCode(e.event_type) },
  {
    key: "change",
    header: "Change",
    cell: (e) =>
      [
        e.from_status || e.to_status ? `${e.from_status || "—"} → ${e.to_status || "—"}` : null,
        e.from_plan || e.to_plan ? `plan ${e.from_plan ?? "none"} → ${e.to_plan ?? "none"}` : null,
        e.delta_days ? `${e.delta_days > 0 ? "+" : ""}${e.delta_days} days` : null,
      ]
        .filter(Boolean)
        .join(" · ") || "—",
  },
  { key: "actor", header: "By", cell: (e) => e.actor_name },
  { key: "reason", header: "Reason", cell: (e) => <span className="text-muted-foreground">{e.reason || "—"}</span> },
];

export function SubscriptionPanel({ school }: { school: PlatformSchoolDetail }) {
  const sub = school.subscription;
  const [action, setAction] = useState<SubscriptionAction | null>(null);
  const [paying, setPaying] = useState(false);
  const events = useSubscriptionEvents(sub?.id);

  if (!sub) {
    return <p className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">This school has no subscription record.</p>;
  }

  const paid = sub.start_date !== null;
  const buttons: { action: SubscriptionAction; label: string; show: boolean }[] = [
    { action: "extend-trial", label: "Extend trial", show: !paid && sub.status !== "SUSPENDED" },
    { action: "extend", label: "Extend subscription", show: paid && sub.status !== "SUSPENDED" },
    { action: "change-plan", label: "Change plan", show: true },
    { action: "cancel", label: "Cancel", show: sub.status === "ACTIVE" || sub.status === "PAST_DUE" },
    { action: "suspend", label: "Suspend", show: sub.status !== "SUSPENDED" },
    { action: "resume", label: "Resume", show: sub.status === "SUSPENDED" },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-4 rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <SubscriptionStateBadge state={sub.state} />
            <span className="text-sm text-muted-foreground">
              {sub.state === "TRIALING" || sub.state === "ACTIVE" || sub.state === "CANCELLED"
                ? `${sub.days_remaining} day(s) left`
                : sub.state === "PAST_DUE"
                  ? `Grace period: ${sub.days_remaining} day(s) left`
                  : null}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setPaying(true)}>Record payment</Button>
            {buttons.filter((b) => b.show).map((b) => (
              <Button key={b.action} variant="outline" onClick={() => setAction(b.action)}>
                {b.label}
              </Button>
            ))}
          </div>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Detail label="Plan" value={sub.plan?.name ?? "None (no limits)"} />
          <Detail label="Stored status" value={humanizeCode(sub.status)} />
          <Detail label="Access" value={humanizeCode(sub.access)} />
          <Detail label="Trial" value={`${formatDate(sub.trial_start)} → ${formatDate(sub.trial_end)}`} />
          <Detail label="Paid since" value={formatDate(sub.start_date)} />
          <Detail label="Paid until" value={formatDate(sub.end_date)} />
        </dl>
      </div>

      <section className="space-y-3">
        <h2 className="font-medium">History</h2>
        {events.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <DataTable columns={EVENT_COLUMNS} rows={events.data} rowKey={(e) => e.id} isLoading={false} error={events.error} emptyTitle="No history yet" />
        )}
      </section>

      <SubscriptionActionDialog subscriptionId={sub.id} action={action} onClose={() => setAction(null)} />
      <RecordPaymentDialog schoolId={school.id} open={paying} onClose={() => setPaying(false)} />
    </div>
  );
}
