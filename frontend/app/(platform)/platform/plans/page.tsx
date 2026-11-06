"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { PlanDialog } from "@/features/billing/components/PlanDialog";
import { usePlans } from "@/features/platform/hooks";
import type { Plan } from "@/features/platform/types";
import { formatMoney } from "@/lib/format";

const limit = (value: number | null) => (value === null ? "Unlimited" : value.toLocaleString());

export default function PlansPage() {
  const { data, isLoading, error, refetch } = usePlans();
  const [target, setTarget] = useState<"create" | Plan | null>(null);

  const columns: Column<Plan>[] = [
    {
      key: "name",
      header: "Plan",
      cell: (p) => (
        <div className="leading-tight">
          <div className="font-medium">{p.name}</div>
          <div className="text-xs text-muted-foreground">{p.slug}</div>
        </div>
      ),
    },
    { key: "price", header: "Monthly price", className: "tabular-nums", cell: (p) => formatMoney(p.monthly_price, p.currency) },
    { key: "limits", header: "Students / teachers / classes", cell: (p) => `${limit(p.max_students)} / ${limit(p.max_teachers)} / ${limit(p.max_classes)}` },
    { key: "subs", header: "Schools", cell: (p) => p.subscriber_count },
    {
      key: "status",
      header: "Status",
      cell: (p) => (
        <div className="flex gap-1">
          <Badge tone={p.is_active ? "green" : "gray"}>{p.is_active ? "Active" : "Retired"}</Badge>
          {!p.is_public ? <Badge>Private</Badge> : null}
        </div>
      ),
    },
    { key: "actions", header: "", className: "text-right", cell: (p) => <Button variant="outline" size="sm" onClick={() => setTarget(p)}>Edit</Button> },
  ];

  return (
    <>
      <PageHeader
        title="Plans"
        description="Plans and prices are data: change them here, never in code."
        actions={<Button onClick={() => setTarget("create")}><Plus className="size-4" /> New plan</Button>}
      />
      <DataTable
        columns={columns}
        rows={data}
        rowKey={(p) => p.id}
        isLoading={isLoading}
        error={error}
        onRetry={() => void refetch()}
        emptyTitle="No plans yet"
        emptyDescription="Create a plan, then assign it to schools or use it for the trial."
      />
      <PlanDialog target={target} onClose={() => setTarget(null)} />
    </>
  );
}
