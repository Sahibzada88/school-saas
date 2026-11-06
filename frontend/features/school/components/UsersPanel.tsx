"use client";

import { UserPlus } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { Pagination } from "@/components/common/Pagination";
import { SelectField } from "@/components/common/SelectField";
import { Badge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { UserFormDialog } from "@/features/school/components/UserFormDialog";
import { useSchoolUsersList, useUpdateUser } from "@/features/school/hooks";
import type { SchoolUser } from "@/features/school/types";
import { useAuth } from "@/hooks/useAuth";
import { useDebounce } from "@/hooks/useDebounce";
import { ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { ROLE_LABELS, SCHOOL_ROLE_OPTIONS } from "@/lib/roles";

export function UsersPanel() {
  const { user: me } = useAuth();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [active, setActive] = useState("");
  const [page, setPage] = useState(1);
  const [dialogTarget, setDialogTarget] = useState<"create" | SchoolUser | null>(null);
  const [toggleTarget, setToggleTarget] = useState<SchoolUser | null>(null);
  const debouncedSearch = useDebounce(search.trim());
  const update = useUpdateUser();

  const { data, isLoading, isFetching, error, refetch } = useSchoolUsersList({
    page,
    search: debouncedSearch || undefined,
    role: role || undefined,
    is_active: active || undefined,
  });

  const columns: Column<SchoolUser>[] = [
    {
      key: "name",
      header: "Name",
      cell: (u) => (
        <div className="leading-tight">
          <div className="font-medium">{`${u.first_name} ${u.last_name}`.trim()}</div>
          <div className="text-xs text-muted-foreground">{u.email}</div>
        </div>
      ),
    },
    { key: "role", header: "Role", cell: (u) => ROLE_LABELS[u.role] },
    {
      key: "status",
      header: "Status",
      cell: (u) => (
        <div className="flex flex-wrap gap-1">
          <Badge tone={u.is_active ? "green" : "gray"}>{u.is_active ? "Active" : "Inactive"}</Badge>
          {u.must_change_password ? <Badge tone="amber">Password change pending</Badge> : null}
        </div>
      ),
    },
    { key: "login", header: "Last sign-in", cell: (u) => formatDateTime(u.last_login) },
    {
      key: "actions",
      header: "",
      className: "text-right",
      cell: (u) => (
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setDialogTarget(u)}>
            Edit
          </Button>
          {u.id !== me?.id ? (
            <Button variant="outline" size="sm" onClick={() => setToggleTarget(u)}>
              {u.is_active ? "Deactivate" : "Reactivate"}
            </Button>
          ) : null}
        </div>
      ),
    },
  ];

  const resetPage = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setPage(1);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid flex-1 gap-3 sm:grid-cols-3">
          <FormField label="Search" type="search" placeholder="Name or email" value={search} onChange={(e) => resetPage(setSearch)(e.target.value)} />
          <SelectField label="Role" value={role} onChange={(e) => resetPage(setRole)(e.target.value)}>
            <option value="">All roles</option>
            {SCHOOL_ROLE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </SelectField>
          <SelectField label="Status" value={active} onChange={(e) => resetPage(setActive)(e.target.value)}>
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </SelectField>
        </div>
        <Button onClick={() => setDialogTarget("create")}>
          <UserPlus className="size-4" /> Add user
        </Button>
      </div>

      <DataTable
        columns={columns}
        rows={data?.results}
        rowKey={(u) => u.id}
        isLoading={isLoading}
        error={error}
        onRetry={() => void refetch()}
        emptyTitle="No users found"
        emptyDescription="Add your team members so they can sign in."
      />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />

      <UserFormDialog target={dialogTarget} currentUserId={me?.id} onClose={() => setDialogTarget(null)} />

      <ConfirmDialog
        open={toggleTarget !== null}
        title={toggleTarget?.is_active ? "Deactivate user" : "Reactivate user"}
        description={
          toggleTarget?.is_active
            ? `${toggleTarget.email} will be signed out and unable to sign in. Nothing is deleted.`
            : `${toggleTarget?.email ?? "This user"} will be able to sign in again.`
        }
        confirmLabel={toggleTarget?.is_active ? "Deactivate" : "Reactivate"}
        destructive={toggleTarget?.is_active}
        isPending={update.isPending}
        error={update.error instanceof ApiError ? update.error.message : null}
        onCancel={() => {
          setToggleTarget(null);
          update.reset();
        }}
        onConfirm={() => {
          if (!toggleTarget) return;
          update.mutate({ id: toggleTarget.id, values: { is_active: !toggleTarget.is_active } }, { onSuccess: () => setToggleTarget(null) });
        }}
      />
    </div>
  );
}
