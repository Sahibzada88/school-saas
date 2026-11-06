import type { Role } from "@/types/auth";

export const ROLE_LABELS: Record<Role, string> = {
  SUPER_ADMIN: "Super Admin",
  SCHOOL_ADMIN: "School Admin",
  TEACHER: "Teacher",
  ACCOUNTANT: "Accountant",
  RECEPTIONIST: "Receptionist",
  PARENT: "Parent",
  STUDENT: "Student",
};

/** Roles a School Admin may assign (never SUPER_ADMIN). */
export const SCHOOL_ROLE_OPTIONS = (Object.keys(ROLE_LABELS) as Role[])
  .filter((role) => role !== "SUPER_ADMIN")
  .map((role) => ({ value: role, label: ROLE_LABELS[role] }));
