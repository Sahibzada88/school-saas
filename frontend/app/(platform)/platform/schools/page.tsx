"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { SelectField } from "@/components/common/SelectField";
import { SchoolStatusBadge, SubscriptionStateBadge } from "@/components/common/StatusBadge";
import { usePlatformSchools } from "@/features/platform/hooks";
import type { PlatformSchool } from "@/features/platform/types";
import { useDebounce } from "@/hooks/useDebounce";
import { formatDate } from "@/lib/format";

const COLUMNS: Column<PlatformSchool>[] = [
  {
    key: "name",
    header: "School",
    cell: (row) => (
      <div className="leading-tight">
        <Link href={`/platform/schools/${row.id}`} className="font-medium underline-offset-4 hover:underline">
          {row.name}
        </Link>
        <div className="text-xs text-muted-foreground">{row.slug}</div>
      </div>
    ),
  },
  { key: "status", header: "Status", cell: (row) => <SchoolStatusBadge status={row.status} /> },
  {
    key: "subscription",
    header: "Subscription",
    cell: (row) =>
      row.subscription ? (
        <div className="leading-tight">
          <SubscriptionStateBadge state={row.subscription.state} />
          <div className="mt-0.5 text-xs text-muted-foreground">
            {row.subscription.plan?.name ?? "No plan"} · until {formatDate(row.subscription.state === "TRIALING" ? row.subscription.ends_at : row.subscription.end_date)}
          </div>
        </div>
      ) : (
        "—"
      ),
  },
  { key: "admin", header: "School admin", cell: (row) => row.admin_email ?? "—" },
  { key: "city", header: "Location", cell: (row) => `${row.city}, ${row.country}` },
  { key: "users", header: "Users", cell: (row) => row.user_count, className: "tabular-nums" },
  { key: "created", header: "Registered", cell: (row) => formatDate(row.created_at) },
];

export default function PlatformSchoolsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [subState, setSubState] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounce(search.trim());

  const { data, isLoading, isFetching, error, refetch } = usePlatformSchools({
    page,
    search: debouncedSearch || undefined,
    status: status || undefined,
    subscription_state: subState || undefined,
    ordering,
  });

  return (
    <>
      <PageHeader title="Schools" description="Every school registered on the platform." />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FormField
          label="Search"
          type="search"
          placeholder="Name, city, email…"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
        <SelectField
          label="Status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="SUSPENDED">Suspended</option>
          <option value="INACTIVE">Inactive</option>
        </SelectField>
        <SelectField
          label="Subscription"
          value={subState}
          onChange={(event) => {
            setSubState(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All</option>
          {["TRIALING", "ACTIVE", "PAST_DUE", "EXPIRED", "CANCELLED", "SUSPENDED"].map((value) => (
            <option key={value} value={value}>{value.replace("_", " ").toLowerCase()}</option>
          ))}
        </SelectField>
        <SelectField label="Sort by" value={ordering} onChange={(event) => setOrdering(event.target.value)}>
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="name">Name (A–Z)</option>
          <option value="-user_count">Most users</option>
        </SelectField>
      </div>

      <DataTable
        columns={COLUMNS}
        rows={data?.results}
        rowKey={(row) => row.id}
        isLoading={isLoading}
        error={error}
        onRetry={() => void refetch()}
        emptyTitle="No schools found"
        emptyDescription="Try a different search or status filter."
      />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </>
  );
}
