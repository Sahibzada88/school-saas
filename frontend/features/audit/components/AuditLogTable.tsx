import Link from "next/link";

import { DataTable, type Column } from "@/components/common/DataTable";
import { Badge } from "@/components/common/StatusBadge";
import type { AuditLogEntry } from "@/features/audit/types";
import { formatDateTime, humanizeCode } from "@/lib/format";

export function AuditLogTable({
  rows,
  isLoading,
  error,
  onRetry,
  showSchool = false,
  showIp = false,
}: {
  rows: AuditLogEntry[] | undefined;
  isLoading: boolean;
  error?: unknown;
  onRetry?: () => void;
  showSchool?: boolean;
  showIp?: boolean;
}) {
  const columns: Column<AuditLogEntry>[] = [
    { key: "when", header: "When", cell: (row) => <span className="whitespace-nowrap">{formatDateTime(row.created_at)}</span> },
    { key: "action", header: "Action", cell: (row) => <Badge>{humanizeCode(row.action)}</Badge> },
    {
      key: "actor",
      header: "Actor",
      cell: (row) => (
        <div className="leading-tight">
          <div>{row.actor_name ?? "System"}</div>
          {row.actor_email ? <div className="text-xs text-muted-foreground">{row.actor_email}</div> : null}
        </div>
      ),
    },
    ...(showSchool
      ? [
          {
            key: "school",
            header: "School",
            cell: (row: AuditLogEntry) =>
              row.school_id ? (
                <Link href={`/platform/schools/${row.school_id}`} className="underline underline-offset-4">
                  {row.school_name}
                </Link>
              ) : (
                "—"
              ),
          },
        ]
      : []),
    { key: "description", header: "Details", cell: (row) => <span className="text-muted-foreground">{row.description || "—"}</span> },
    ...(showIp ? [{ key: "ip", header: "IP", cell: (row: AuditLogEntry) => <span className="font-mono text-xs">{row.ip ?? "—"}</span> }] : []),
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      isLoading={isLoading}
      error={error}
      onRetry={onRetry}
      emptyTitle="No activity yet"
      emptyDescription="Actions will appear here as they happen."
    />
  );
}
