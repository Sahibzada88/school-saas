"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { SelectField } from "@/components/common/SelectField";
import { SchoolStatusBadge, SubscriptionStateBadge } from "@/components/common/StatusBadge";
import { usePlans, usePlatformSubscriptions } from "@/features/platform/hooks";
import type { PlatformSubscription } from "@/features/platform/types";
import { useDebounce } from "@/hooks/useDebounce";
import { formatDate } from "@/lib/format";

const COLUMNS: Column<PlatformSubscription>[] = [
  {
    key: "school",
    header: "School",
    cell: (s) => (
      <Link href={`/platform/schools/${s.school.id}`} className="font-medium underline-offset-4 hover:underline">
        {s.school.name}
      </Link>
    ),
  },
  { key: "state", header: "Subscription", cell: (s) => <SubscriptionStateBadge state={s.state} /> },
  { key: "plan", header: "Plan", cell: (s) => s.plan?.name ?? "—" },
  {
    key: "ends",
    header: "Ends",
    cell: (s) => (
      <div className="leading-tight">
        <div>{formatDate(s.state === "TRIALING" ? s.trial_end : s.end_date)}</div>
        {s.days_remaining !== null && s.state !== "EXPIRED" ? (
          <div className={s.is_expiring || s.in_grace ? "text-xs text-amber-600" : "text-xs text-muted-foreground"}>
            {s.in_grace ? "grace: " : ""}
            {s.days_remaining} day(s)
          </div>
        ) : null}
      </div>
    ),
  },
  { key: "type", header: "Type", cell: (s) => (s.is_trial ? "Trial" : "Paid") },
  { key: "school-status", header: "School", cell: (s) => <SchoolStatusBadge status={s.school.status} /> },
];

export default function SubscriptionsPage() {
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [plan, setPlan] = useState("");
  const [expiring, setExpiring] = useState(false);
  const [ordering, setOrdering] = useState("ends_at");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounce(search.trim());
  const plans = usePlans();

  const { data, isLoading, isFetching, error, refetch } = usePlatformSubscriptions({
    page,
    search: debouncedSearch || undefined,
    state: state || undefined,
    plan: plan || undefined,
    expiring: expiring ? "true" : undefined,
    ordering,
  });

  const reset = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setPage(1);
  };

  return (
    <>
      <PageHeader title="Subscriptions" description="Computed from dates, so a trial or subscription shows as expired the moment it ends." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <FormField label="Search" type="search" placeholder="School name" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
        <SelectField label="State" value={state} onChange={(e) => reset(setState)(e.target.value)}>
          <option value="">All states</option>
          {["TRIALING", "ACTIVE", "PAST_DUE", "EXPIRED", "CANCELLED", "SUSPENDED"].map((value) => (
            <option key={value} value={value}>{value.replace("_", " ").toLowerCase()}</option>
          ))}
        </SelectField>
        <SelectField label="Plan" value={plan} onChange={(e) => reset(setPlan)(e.target.value)}>
          <option value="">All plans</option>
          {(plans.data ?? []).map((p) => <option key={p.id} value={p.slug}>{p.name}</option>)}
        </SelectField>
        <SelectField label="Sort by" value={ordering} onChange={(e) => setOrdering(e.target.value)}>
          <option value="ends_at">Ending soonest</option>
          <option value="-ends_at">Ending latest</option>
          <option value="school">School name</option>
          <option value="-created_at">Newest</option>
        </SelectField>
        <label className="flex items-end gap-2 pb-2 text-sm">
          <input type="checkbox" checked={expiring} onChange={(e) => reset(setExpiring)(e.target.checked)} /> Expiring soon only
        </label>
      </div>
      <DataTable
        columns={COLUMNS}
        rows={data?.results}
        rowKey={(s) => s.id}
        isLoading={isLoading}
        error={error}
        onRetry={() => void refetch()}
        emptyTitle="No subscriptions match"
        emptyDescription="Try removing a filter."
      />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </>
  );
}
