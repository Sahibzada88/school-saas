import type { AuditLogEntry } from "@/features/audit/types";
import type { Role, SchoolStatus } from "@/types/auth";

export interface SchoolUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  last_login: string | null;
  created_at: string;
}

export interface SchoolProfile {
  id: string;
  name: string;
  slug: string;
  status: SchoolStatus;
  email: string;
  phone: string;
  country: string;
  city: string;
  address: string;
  timezone: string;
  currency: string;
  logo_url: string | null;
}

export interface SchoolDashboard {
  school: { name: string; status: SchoolStatus; city: string; country: string; created_at: string };
  users: { total: number; active: number; by_role: Record<string, number> };
  students: { total: number; active: number };
  teachers: { total: number; active: number };
  attendance_today: { date: string; enrolled: number; marked: number; counts: Record<string, number>; percentage: number | null };
  fees: { outstanding_total: string; outstanding_count: number; overdue_count: number; currency: string };
  upcoming_exams: { id: string; name: string; start_date: string | null; status: string }[];
  checklist: { key: string; label: string; done: boolean }[];
  recent_activity: AuditLogEntry[];
}

export type UserListParams = {
  page?: number;
  search?: string;
  role?: string;
  is_active?: string;
};

export type AuditParams = { page?: number; search?: string; action?: string };
