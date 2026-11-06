"use client";

import { useAuth } from "@/providers/auth-provider";

/** UX-only mirror of the backend registry (the backend is the enforcer). */
export function usePermissions() {
  const { can, permissions } = useAuth();
  return { can, permissions };
}
