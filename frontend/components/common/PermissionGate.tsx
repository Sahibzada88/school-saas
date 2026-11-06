"use client";

import type { ReactNode } from "react";

import { usePermissions } from "@/hooks/usePermissions";

/** Hides UI the user cannot use. This is cosmetic: the API enforces permissions regardless. */
export function PermissionGate({
  permission,
  children,
  fallback = null,
}: {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { can } = usePermissions();
  return <>{can(permission) ? children : fallback}</>;
}
