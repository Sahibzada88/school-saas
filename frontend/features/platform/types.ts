import type { AuditLogEntry } from "@/features/audit/types";
import type { SchoolStatus, SubscriptionState, SubscriptionSummary } from "@/types/auth";

export interface SubscriptionPayload extends SubscriptionSummary {
  id: string;
  status: SubscriptionState;
  trial_start: string;
  trial_end: string;
  start_date: string | null;
  end_date: string | null;
  cancelled_at: string | null;
  suspended_at: string | null;
}

export interface PlatformSchool {
  id: string;
  name: string;
  slug: string;
  status: SchoolStatus;
  email: string;
  city: string;
  country: string;
  created_at: string;
  user_count: number;
  admin_email: string | null;
  subscription: SubscriptionPayload | null;
}

export interface PlatformSchoolDetail extends PlatformSchool {
  phone: string;
  address: string;
  timezone: string;
  currency: string;
  status_reason: string;
  status_changed_at: string | null;
  status_changed_by_name: string | null;
  active_user_count: number;
  admin: { name: string; email: string; phone: string } | null;
}

export interface PlatformPayment {
  id: string;
  school_id: string;
  school_name: string;
  subscription_id: string;
  amount: string;
  currency: string;
  payment_method: PaymentMethod;
  transaction_reference: string;
  payment_date: string;
  months: number;
  period_start: string;
  period_end: string;
  notes: string;
  created_by_name: string | null;
  created_at: string;
}

export type PaymentMethod = "BANK_TRANSFER" | "JAZZCASH" | "EASYPAISA" | "CASH" | "OTHER";

export interface PlatformDashboard {
  people: { students: number; teachers: number };
  schools: { total: number; by_status: Record<SchoolStatus, number> };
  users: { total: number; by_role: Record<string, number> };
  subscriptions: { by_state: Record<SubscriptionState, number>; expiring_soon: number };
  revenue: { currency: string; last_30_days: string; all_time: string }[];
  registrations: { last_30_days: number; daily: { date: string; count: number }[] };
  recent_schools: PlatformSchool[];
  recent_payments: PlatformPayment[];
}

export type LifecycleAction = "suspend" | "deactivate" | "reactivate";

export interface Plan {
  id: string;
  name: string;
  slug: string;
  description: string;
  monthly_price: string;
  currency: string;
  max_students: number | null;
  max_teachers: number | null;
  max_classes: number | null;
  features: string[];
  is_active: boolean;
  is_public: boolean;
  sort_order: number;
  subscriber_count: number;
  created_at: string;
}

export interface PlatformSubscription extends SubscriptionPayload {
  school: { id: string; name: string; status: SchoolStatus };
}

export interface SubscriptionEvent {
  id: string;
  created_at: string;
  event_type: string;
  from_status: string;
  to_status: string;
  delta_days: number | null;
  reason: string;
  from_plan: string | null;
  to_plan: string | null;
  actor_name: string;
}

export type SubscriptionAction = "extend-trial" | "extend" | "change-plan" | "cancel" | "suspend" | "resume";

export interface SettingItem {
  key: string;
  kind: "int" | "choice" | "str";
  value: string | number;
  default: string | number;
  description: string;
  minimum: number | null;
  maximum: number | null;
  choices: string[];
  max_length: number | null;
}

export type SchoolListParams = { page?: number; search?: string; status?: string; subscription_state?: string; ordering?: string };
export type AuditListParams = { page?: number; action?: string; search?: string; date_from?: string; date_to?: string; school?: string };
export type SubscriptionListParams = { page?: number; state?: string; search?: string; plan?: string; expiring?: string; ordering?: string };
export type PaymentListParams = { page?: number; school?: string; method?: string; search?: string; date_from?: string; date_to?: string };
export type { AuditLogEntry };
