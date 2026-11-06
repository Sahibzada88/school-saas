export type Role =
  | "SUPER_ADMIN"
  | "SCHOOL_ADMIN"
  | "TEACHER"
  | "ACCOUNTANT"
  | "RECEPTIONIST"
  | "PARENT"
  | "STUDENT";

export type SchoolStatus = "ACTIVE" | "SUSPENDED" | "INACTIVE";

export type SubscriptionState = "TRIALING" | "ACTIVE" | "PAST_DUE" | "EXPIRED" | "CANCELLED" | "SUSPENDED";
export type AccessLevel = "FULL" | "READ_ONLY" | "BLOCKED";

/** What the school may see about its own subscription (computed by the backend from timestamps). */
export interface SubscriptionSummary {
  state: SubscriptionState;
  access: AccessLevel;
  days_remaining: number | null;
  is_expiring: boolean;
  in_grace: boolean;
  ends_at: string | null;
  is_trial: boolean;
  plan: { name: string; slug: string } | null;
}

export interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: Role;
  must_change_password: boolean;
}

export interface AuthSchool {
  id: string;
  name: string;
  slug: string;
  status: SchoolStatus;
  status_reason: string;
}

/** Response of /auth/me, login, register, refresh and change-password. `permissions` mirrors the backend registry. */
export interface Me {
  user: AuthUser;
  school: AuthSchool | null;
  subscription: SubscriptionSummary | null;
  permissions: string[];
}
