"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { ErrorState } from "@/components/common/ErrorState";
import { FormAlert } from "@/components/common/FormAlert";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { Skeleton } from "@/components/common/Skeleton";
import { Badge, SchoolStatusBadge, SubscriptionStateBadge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { AuditLogTable } from "@/features/audit/components/AuditLogTable";
import { NotifyDialog } from "@/features/billing/components/NotifyDialog";
import { PaymentsTable } from "@/features/billing/components/PaymentsTable";
import { SubscriptionPanel } from "@/features/billing/components/SubscriptionPanel";
import { LifecycleDialog } from "@/features/platform/components/LifecycleDialog";
import { usePlatformPayments, usePlatformSchool, useSchoolActivity, useSchoolUsers } from "@/features/platform/hooks";
import type { LifecycleAction, PlatformSchoolDetail } from "@/features/platform/types";
import type { SchoolUser } from "@/features/school/types";
import { formatDate, formatDateTime } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/roles";

type TabValue = "overview" | "users" | "subscription" | "payments" | "activity";
const TABS: { value: TabValue; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "users", label: "Users" },
  { value: "subscription", label: "Subscription" },
  { value: "payments", label: "Payments" },
  { value: "activity", label: "Activity" },
];

const ACTIONS_BY_STATUS: Record<string, { action: LifecycleAction; label: string; destructive?: boolean }[]> = {
  ACTIVE: [
    { action: "suspend", label: "Suspend", destructive: true },
    { action: "deactivate", label: "Deactivate", destructive: true },
  ],
  SUSPENDED: [
    { action: "reactivate", label: "Reactivate" },
    { action: "deactivate", label: "Deactivate", destructive: true },
  ],
  INACTIVE: [{ action: "reactivate", label: "Reactivate" }],
};

const USER_COLUMNS: Column<SchoolUser>[] = [
  { key: "name", header: "Name", cell: (u) => `${u.first_name} ${u.last_name}`.trim() },
  { key: "email", header: "Email", cell: (u) => u.email },
  { key: "role", header: "Role", cell: (u) => ROLE_LABELS[u.role] },
  { key: "active", header: "Status", cell: (u) => <Badge tone={u.is_active ? "green" : "gray"}>{u.is_active ? "Active" : "Inactive"}</Badge> },
  { key: "login", header: "Last sign-in", cell: (u) => formatDateTime(u.last_login) },
];

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value === null || value === undefined || value === "" ? "—" : value}</dd>
    </div>
  );
}

function Overview({ school }: { school: PlatformSchoolDetail }) {
  return (
    <div className="space-y-4">
      {school.status !== "ACTIVE" ? (
        <FormAlert>
          This school is {school.status.toLowerCase()}.
          {school.status_reason ? ` Reason: ${school.status_reason}` : ""}
          {school.status_changed_by_name ? ` (by ${school.status_changed_by_name}, ${formatDateTime(school.status_changed_at)})` : ""}
        </FormAlert>
      ) : null}
      <dl className="grid gap-4 rounded-lg border bg-card p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-3">
        <Detail label="Email" value={school.email} />
        <Detail label="Phone" value={school.phone} />
        <Detail label="Location" value={`${school.city}, ${school.country}`} />
        <Detail label="Address" value={school.address} />
        <Detail label="Time zone" value={school.timezone} />
        <Detail label="Currency" value={school.currency} />
        <Detail label="Registered" value={formatDate(school.created_at)} />
        <Detail label="Users" value={`${school.active_user_count} active of ${school.user_count}`} />
        <Detail label="School admin" value={school.admin ? `${school.admin.name} (${school.admin.email})` : null} />
      </dl>
    </div>
  );
}

function UsersTab({ id }: { id: string }) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error, refetch } = useSchoolUsers(id, page, true);
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Read-only. Viewing this list is recorded in the audit log.</p>
      <DataTable columns={USER_COLUMNS} rows={data?.results} rowKey={(u) => u.id} isLoading={isLoading} error={error} onRetry={() => void refetch()} emptyTitle="No users" />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </div>
  );
}

function PaymentsTab({ id }: { id: string }) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error, refetch } = usePlatformPayments({ school: id, page });
  return (
    <div className="space-y-3">
      <PaymentsTable rows={data?.results} isLoading={isLoading} error={error} onRetry={() => void refetch()} showSchool={false} />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </div>
  );
}

function ActivityTab({ id }: { id: string }) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error, refetch } = useSchoolActivity(id, page, true);
  return (
    <div className="space-y-3">
      <AuditLogTable rows={data?.results} isLoading={isLoading} error={error} onRetry={() => void refetch()} showIp />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </div>
  );
}

export default function PlatformSchoolDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: school, isLoading, error, refetch } = usePlatformSchool(id);
  const [tab, setTab] = useState<TabValue>("overview");
  const [pendingAction, setPendingAction] = useState<LifecycleAction | null>(null);
  const [notifying, setNotifying] = useState(false);

  const back = (
    <Link href="/platform/schools" className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:underline">
      <ArrowLeft className="size-4" /> All schools
    </Link>
  );

  if (error) {
    return (
      <div className="space-y-4">
        {back}
        <div className="rounded-lg border bg-card">
          <ErrorState error={error} onRetry={() => void refetch()} />
        </div>
      </div>
    );
  }

  return (
    <>
      {back}
      {isLoading || !school ? (
        <div className="space-y-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-40" />
        </div>
      ) : (
        <>
          <PageHeader
            title={
              <span className="flex flex-wrap items-center gap-3">
                {school.name} <SchoolStatusBadge status={school.status} />
                {school.subscription ? <SubscriptionStateBadge state={school.subscription.state} /> : null}
              </span>
            }
            description={school.slug}
            actions={
              <>
                <Button variant="outline" onClick={() => setNotifying(true)}>Send notification</Button>
                {(ACTIONS_BY_STATUS[school.status] ?? []).map(({ action, label, destructive }) => (
                  <Button key={action} variant={destructive ? "outline" : "default"} onClick={() => setPendingAction(action)}>
                    {label}
                  </Button>
                ))}
              </>
            }
          />
          <Tabs tabs={TABS} value={tab} onChange={setTab} />
          {tab === "overview" ? <Overview school={school} /> : null}
          {tab === "users" ? <UsersTab id={id} /> : null}
          {tab === "subscription" ? <SubscriptionPanel school={school} /> : null}
          {tab === "payments" ? <PaymentsTab id={id} /> : null}
          {tab === "activity" ? <ActivityTab id={id} /> : null}
          <LifecycleDialog action={pendingAction} schoolId={id} schoolName={school.name} onClose={() => setPendingAction(null)} />
          <NotifyDialog schoolId={id} open={notifying} onClose={() => setNotifying(false)} />
        </>
      )}
    </>
  );
}
