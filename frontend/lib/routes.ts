import type { Me } from "@/types/auth";

export type GuardArea = "school" | "platform" | "any";

/** Where a signed-in user belongs. */
export function homeRouteFor(me: Me): string {
  if (me.user.role === "SUPER_ADMIN") return "/platform/dashboard";
  if (me.user.must_change_password) return "/change-password";
  if (me.school?.status !== "ACTIVE" || me.subscription?.access === "BLOCKED") return "/suspended";
  return "/dashboard";
}

/** Returns a path to redirect to when `me` may not view `area`, or null when access is fine. */
export function guardRedirect(me: Me, area: GuardArea): string | null {
  if (area === "any") return null;
  const isPlatform = me.user.role === "SUPER_ADMIN";
  if (area === "platform") return isPlatform ? null : "/forbidden";
  if (isPlatform) return "/platform/dashboard";
  if (me.user.must_change_password) return "/change-password";
  if (me.school?.status !== "ACTIVE" || me.subscription?.access === "BLOCKED") return "/suspended";
  return null;
}

/** Only same-site relative paths are accepted from ?next= (prevents open redirects). */
export function safeNext(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return null;
  return value;
}
