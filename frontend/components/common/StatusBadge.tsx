import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { SchoolStatus, SubscriptionState } from "@/types/auth";

type Tone = "green" | "amber" | "red" | "gray" | "blue";

const TONES: Record<Tone, string> = {
  green: "bg-green-600/10 text-green-700 dark:text-green-400",
  amber: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  red: "bg-red-600/10 text-red-700 dark:text-red-400",
  gray: "bg-muted text-muted-foreground",
  blue: "bg-blue-600/10 text-blue-700 dark:text-blue-400",
};

export function Badge({ tone = "gray", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", TONES[tone])}>{children}</span>
  );
}

const SCHOOL_STATUS: Record<SchoolStatus, { tone: Tone; label: string }> = {
  ACTIVE: { tone: "green", label: "Active" },
  SUSPENDED: { tone: "amber", label: "Suspended" },
  INACTIVE: { tone: "red", label: "Inactive" },
};

export function SchoolStatusBadge({ status }: { status: SchoolStatus }) {
  const { tone, label } = SCHOOL_STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

const SUBSCRIPTION_STATE: Record<SubscriptionState, { tone: Tone; label: string }> = {
  TRIALING: { tone: "blue", label: "Trial" },
  ACTIVE: { tone: "green", label: "Active" },
  PAST_DUE: { tone: "amber", label: "Past due" },
  EXPIRED: { tone: "red", label: "Expired" },
  CANCELLED: { tone: "gray", label: "Cancelled" },
  SUSPENDED: { tone: "red", label: "Suspended" },
};

export function SubscriptionStateBadge({ state }: { state: SubscriptionState }) {
  const { tone, label } = SUBSCRIPTION_STATE[state];
  return <Badge tone={tone}>{label}</Badge>;
}
