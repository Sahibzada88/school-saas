import { apiFetch } from "@/lib/api-client";
import type { AuditLogEntry } from "@/features/audit/types";
import type { SchoolUser } from "@/features/school/types";
import type { Paginated } from "@/types/api";

import type {
  AuditListParams,
  LifecycleAction,
  PaymentListParams,
  Plan,
  PlatformDashboard,
  PlatformPayment,
  PlatformSchool,
  PlatformSchoolDetail,
  PlatformSubscription,
  SchoolListParams,
  SettingItem,
  SubscriptionAction,
  SubscriptionEvent,
  SubscriptionListParams,
} from "./types";

export type PlanInput = Partial<Omit<Plan, "id" | "subscriber_count" | "created_at">>;

export interface SubscriptionActionBody {
  days?: number;
  reason?: string;
  plan?: string;
  confirm?: boolean;
}

export interface RecordPaymentBody {
  school: string;
  amount: string;
  payment_method: string;
  transaction_reference?: string;
  payment_date?: string;
  months?: number;
  notes?: string;
  currency?: string;
  plan?: string | null;
}

export const platformApi = {
  dashboard: () => apiFetch<PlatformDashboard>("/platform/dashboard/"),

  schools: (params: SchoolListParams) => apiFetch<Paginated<PlatformSchool>>("/platform/schools/", { query: params }),
  school: (id: string) => apiFetch<PlatformSchoolDetail>(`/platform/schools/${id}/`),
  schoolUsers: (id: string, page: number) =>
    apiFetch<Paginated<SchoolUser>>(`/platform/schools/${id}/users/`, { query: { page } }),
  schoolActivity: (id: string, page: number) =>
    apiFetch<Paginated<AuditLogEntry>>(`/platform/schools/${id}/activity/`, { query: { page } }),
  transition: (id: string, action: LifecycleAction, reason: string) =>
    apiFetch<PlatformSchoolDetail>(`/platform/schools/${id}/${action}/`, { method: "POST", body: { reason, confirm: true } }),
  notify: (id: string, body: { title: string; body: string; severity: string }) =>
    apiFetch<{ recipients: number }>(`/platform/schools/${id}/notify/`, { method: "POST", body }),

  auditLogs: (params: AuditListParams) => apiFetch<Paginated<AuditLogEntry>>("/platform/audit-logs/", { query: params }),
  auditActions: () => apiFetch<string[]>("/platform/audit-logs/actions/"),

  plans: () => apiFetch<Plan[]>("/platform/plans/"),
  createPlan: (body: PlanInput) => apiFetch<Plan>("/platform/plans/", { method: "POST", body }),
  updatePlan: (id: string, body: PlanInput) => apiFetch<Plan>(`/platform/plans/${id}/`, { method: "PATCH", body }),

  subscriptions: (params: SubscriptionListParams) =>
    apiFetch<Paginated<PlatformSubscription>>("/platform/subscriptions/", { query: params }),
  subscriptionAction: (id: string, action: SubscriptionAction, body: SubscriptionActionBody) =>
    apiFetch<PlatformSubscription>(`/platform/subscriptions/${id}/${action}/`, { method: "POST", body }),
  subscriptionEvents: (id: string) => apiFetch<SubscriptionEvent[]>(`/platform/subscriptions/${id}/events/`),

  payments: (params: PaymentListParams) => apiFetch<Paginated<PlatformPayment>>("/platform/payments/", { query: params }),
  recordPayment: (body: RecordPaymentBody) => apiFetch<PlatformPayment>("/platform/payments/", { method: "POST", body }),

  settings: () => apiFetch<SettingItem[]>("/platform/settings/"),
  updateSettings: (values: Record<string, string | number>) =>
    apiFetch<SettingItem[]>("/platform/settings/", { method: "PATCH", body: values }),
};
