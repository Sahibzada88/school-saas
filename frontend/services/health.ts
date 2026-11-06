import { apiFetch } from "@/lib/api-client";
import type { HealthStatus } from "@/types/api";

export function getHealth(checkDatabase = false): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health/", { query: { db: checkDatabase ? 1 : undefined } });
}
