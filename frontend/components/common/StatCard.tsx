import type { ReactNode } from "react";

import { Skeleton } from "@/components/common/Skeleton";

export function StatCard({
  label,
  value,
  hint,
  isLoading,
}: {
  label: string;
  value?: ReactNode;
  hint?: string;
  isLoading?: boolean;
}) {
  return (
    <div className="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
      <p className="text-sm text-muted-foreground">{label}</p>
      {isLoading ? <Skeleton className="mt-2 h-8 w-16" /> : <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>}
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
