"use client";

import Link from "next/link";

import { DataTable, type Column } from "@/components/common/DataTable";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Skeleton } from "@/components/common/Skeleton";
import { StatCard } from "@/components/common/StatCard";
import { SchoolStatusBadge } from "@/components/common/StatusBadge";
import { RegistrationsChart } from "@/features/platform/components/RegistrationsChart";
import { usePlatformDashboard } from "@/features/platform/hooks";
import type { PlatformSchool } from "@/features/platform/types";
import { PaymentsTable } from "@/features/billing/components/PaymentsTable";
import { formatDate, formatMoney } from "@/lib/format";

const RECENT_COLUMNS: Column<PlatformSchool>[] = [
  {
    key: "name",
    header: "School",
    cell: (row) => (
      <Link href={`/platform/schools/${row.id}`} className="font-medium underline-offset-4 hover:underline">
        {row.name}
      </Link>
    ),
  },
  { key: "status", header: "Status", cell: (row) => <SchoolStatusBadge status={row.status} /> },
  { key: "city", header: "Location", cell: (row) => `${row.city}, ${row.country}` },
  { key: "users", header: "Users", cell: (row) => row.user_count },
  { key: "created", header: "Registered", cell: (row) => formatDate(row.created_at) },
];

export default function PlatformDashboardPage() {
  const { data, isLoading, error, refetch } = usePlatformDashboard();

  return (
    <>
      <PageHeader title="Platform dashboard" description="Live overview of schools on the platform." />

      {error ? (
        <div className="rounded-lg border bg-card">
          <ErrorState error={error} onRetry={() => void refetch()} />
        </div>
      ) : (
        <>
          <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard label="Total schools" value={data?.schools.total} isLoading={isLoading} />
            <StatCard label="Active schools" value={data?.schools.by_status.ACTIVE} isLoading={isLoading} />
            <StatCard label="Suspended schools" value={data?.schools.by_status.SUSPENDED} isLoading={isLoading} />
            <StatCard label="Inactive schools" value={data?.schools.by_status.INACTIVE} isLoading={isLoading} />
            <StatCard label="School users" value={data?.users.total} isLoading={isLoading} />
            <StatCard label="Students" value={data?.people.students} hint="Across all schools" isLoading={isLoading} />
            <StatCard label="Teachers" value={data?.people.teachers} hint="Across all schools" isLoading={isLoading} />
            <StatCard
              label="New schools"
              value={data?.registrations.last_30_days}
              hint="Last 30 days"
              isLoading={isLoading}
            />
          </section>

          <section aria-label="Subscriptions and revenue" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="On trial" value={data?.subscriptions.by_state.TRIALING} isLoading={isLoading} />
            <StatCard label="Paying" value={data?.subscriptions.by_state.ACTIVE} isLoading={isLoading} />
            <StatCard label="Expired" value={data?.subscriptions.by_state.EXPIRED} hint="Read-only or blocked" isLoading={isLoading} />
            <StatCard label="Expiring soon" value={data?.subscriptions.expiring_soon} hint="Within the notice window" isLoading={isLoading} />
            {(data?.revenue ?? []).map((row) => (
              <StatCard
                key={row.currency}
                label={`Revenue (${row.currency})`}
                value={formatMoney(row.last_30_days, row.currency)}
                hint={`Last 30 days · all time ${formatMoney(row.all_time, row.currency)}`}
              />
            ))}
          </section>

          <section className="space-y-3 rounded-lg border bg-card p-4 shadow-sm">
            <h2 className="font-medium">Registrations, last 30 days</h2>
            {isLoading || !data ? <Skeleton className="h-64 w-full" /> : <RegistrationsChart data={data.registrations.daily} />}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">Recently registered</h2>
              <Link href="/platform/schools" className="text-sm underline underline-offset-4">
                View all schools
              </Link>
            </div>
            <DataTable
              columns={RECENT_COLUMNS}
              rows={data?.recent_schools}
              rowKey={(row) => row.id}
              isLoading={isLoading}
              emptyTitle="No schools yet"
              emptyDescription="Schools appear here as soon as they register."
            />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">Recent payments</h2>
              <Link href="/platform/payments" className="text-sm underline underline-offset-4">View all payments</Link>
            </div>
            <PaymentsTable rows={data?.recent_payments} isLoading={isLoading} />
          </section>
        </>
      )}
    </>
  );
}
