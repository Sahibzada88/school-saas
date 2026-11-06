import type { AuditLogEntry } from "@/features/audit/types";
import { apiFetch } from "@/lib/api-client";
import type { CreateUserValues, EditUserValues, ProfileValues } from "@/schemas/school";
import type { Paginated } from "@/types/api";

import type { AuditParams, SchoolDashboard, SchoolProfile, SchoolUser, UserListParams } from "./types";

export const schoolApi = {
  dashboard: () => apiFetch<SchoolDashboard>("/school/dashboard/"),
  profile: () => apiFetch<SchoolProfile>("/school/profile/"),
  updateProfile: (values: Partial<ProfileValues> & { logo?: string | null }) =>
    apiFetch<SchoolProfile>("/school/profile/", { method: "PATCH", body: values }),
  users: (params: UserListParams) => apiFetch<Paginated<SchoolUser>>("/school/users/", { query: params }),
  createUser: (values: CreateUserValues) => apiFetch<SchoolUser>("/school/users/", { method: "POST", body: values }),
  updateUser: (id: string, values: Partial<EditUserValues> & { is_active?: boolean }) =>
    apiFetch<SchoolUser>(`/school/users/${id}/`, { method: "PATCH", body: values }),
  auditLogs: (params: AuditParams) => apiFetch<Paginated<AuditLogEntry>>("/school/audit-logs/", { query: params }),
};
