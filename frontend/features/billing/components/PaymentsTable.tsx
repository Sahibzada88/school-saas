import Link from "next/link";

import { DataTable, type Column } from "@/components/common/DataTable";
import type { PlatformPayment } from "@/features/platform/types";
import { formatDate, formatMoney } from "@/lib/format";

const METHOD_LABELS: Record<string, string> = {
  BANK_TRANSFER: "Bank transfer",
  JAZZCASH: "JazzCash",
  EASYPAISA: "Easypaisa",
  CASH: "Cash",
  OTHER: "Other",
};

export function PaymentsTable({
  rows,
  isLoading,
  error,
  onRetry,
  showSchool = true,
}: {
  rows: PlatformPayment[] | undefined;
  isLoading: boolean;
  error?: unknown;
  onRetry?: () => void;
  showSchool?: boolean;
}) {
  const columns: Column<PlatformPayment>[] = [
    { key: "date", header: "Date", cell: (p) => formatDate(p.payment_date) },
    ...(showSchool
      ? [{
          key: "school",
          header: "School",
          cell: (p: PlatformPayment) => (
            <Link href={`/platform/schools/${p.school_id}`} className="underline underline-offset-4">
              {p.school_name}
            </Link>
          ),
        }]
      : []),
    { key: "amount", header: "Amount", className: "tabular-nums", cell: (p) => <span className="font-medium">{formatMoney(p.amount, p.currency)}</span> },
    { key: "method", header: "Method", cell: (p) => METHOD_LABELS[p.payment_method] ?? p.payment_method },
    { key: "reference", header: "Reference", cell: (p) => <span className="font-mono text-xs">{p.transaction_reference || "—"}</span> },
    { key: "period", header: "Covers", cell: (p) => `${formatDate(p.period_start)} → ${formatDate(p.period_end)} (${p.months} mo)` },
    { key: "by", header: "Recorded by", cell: (p) => p.created_by_name ?? "—" },
  ];
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(p) => p.id}
      isLoading={isLoading}
      error={error}
      onRetry={onRetry}
      emptyTitle="No payments recorded"
      emptyDescription="Payments appear here after a Super Admin records them."
    />
  );
}
