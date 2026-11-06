"use client";

import { AlertTriangle, Info, OctagonAlert } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

type Tone = "info" | "warning" | "danger";
const TONES: Record<Tone, { className: string; Icon: typeof Info }> = {
  info: { className: "border-blue-600/30 bg-blue-600/10 text-blue-800 dark:text-blue-300", Icon: Info },
  warning: { className: "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300", Icon: AlertTriangle },
  danger: { className: "border-red-600/40 bg-red-600/10 text-red-800 dark:text-red-300", Icon: OctagonAlert },
};

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Billing status strip. Only the School Admin sees reminders; everybody sees the read-only warning because it
 *  explains why saving fails. Billing actions live with the platform administration, never here. */
export function SubscriptionBanner() {
  const { me } = useAuth();
  const sub = me?.subscription;
  if (!sub || !me) return null;
  const isAdmin = me.user.role === "SCHOOL_ADMIN";
  const days = sub.days_remaining ?? 0;
  const contact = "Contact platform administration to";

  let tone: Tone | null = null;
  let message = "";

  if (sub.state === "EXPIRED") {
    tone = "danger";
    message = isAdmin
      ? `Your ${sub.is_trial ? "free trial" : "subscription"} has ended. Your data is safe but read-only until it is renewed. ${contact} ${sub.is_trial ? "subscribe" : "renew"}.`
      : "Your school's subscription has ended, so data is read-only for now.";
  } else if (isAdmin && sub.state === "PAST_DUE") {
    tone = "warning";
    message = `Your subscription has ended. Full access continues for ${plural(days, "more day")}. ${contact} renew.`;
  } else if (isAdmin && sub.state === "TRIALING") {
    tone = sub.is_expiring ? "warning" : "info";
    message = `Free trial: ${plural(days, "day")} left. ${contact} subscribe.`;
  } else if (isAdmin && sub.state === "ACTIVE" && sub.is_expiring) {
    tone = "warning";
    message = `Your subscription ends in ${plural(days, "day")}. ${contact} renew.`;
  } else if (isAdmin && sub.state === "CANCELLED") {
    tone = "info";
    message = `Your subscription was cancelled. You keep full access until ${formatDate(sub.ends_at)}.`;
  }

  if (!tone) return null;
  const { className, Icon } = TONES[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex items-start gap-2 rounded-md border p-3 text-sm", className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p>{message}</p>
    </div>
  );
}
