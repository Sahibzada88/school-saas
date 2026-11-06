import {
  Award, BarChart3, Bell, BookOpen, CalendarDays, ClipboardCheck, CreditCard, FileText, GraduationCap, Layers, LayoutDashboard, Megaphone, Receipt, School, ScrollText,
  Settings, SlidersHorizontal, Users, Wallet, type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Hidden when the caller lacks this permission (cosmetic: the API enforces it). */
  permission?: string;
}

export const PLATFORM_NAV: NavItem[] = [
  { label: "Dashboard", href: "/platform/dashboard", icon: LayoutDashboard },
  { label: "Schools", href: "/platform/schools", icon: School },
  { label: "Plans", href: "/platform/plans", icon: Layers },
  { label: "Subscriptions", href: "/platform/subscriptions", icon: CreditCard },
  { label: "Payments", href: "/platform/payments", icon: Receipt },
  { label: "Audit logs", href: "/platform/audit-logs", icon: ScrollText },
  { label: "Settings", href: "/platform/settings", icon: SlidersHorizontal },
];

export const SCHOOL_NAV: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Students", href: "/students", icon: GraduationCap, permission: "students.view" },
  { label: "Teachers", href: "/teachers", icon: Users, permission: "teachers.view" },
  { label: "Classes", href: "/classes", icon: School, permission: "academics.view" },
  { label: "Subjects", href: "/subjects", icon: BookOpen, permission: "academics.view" },
  { label: "Timetable", href: "/timetable", icon: CalendarDays, permission: "timetable.view" },
  { label: "Attendance", href: "/attendance", icon: ClipboardCheck, permission: "attendance.students.view" },
  { label: "Exams", href: "/exams", icon: FileText, permission: "results.view" },
  { label: "Results", href: "/results", icon: Award, permission: "results.view" },
  { label: "Fees", href: "/fees", icon: Wallet, permission: "fees.view" },
  { label: "Reports", href: "/reports", icon: BarChart3, permission: "reports.view" },
  { label: "Announcements", href: "/announcements", icon: Megaphone, permission: "announcements.view" },
  { label: "Notifications", href: "/notifications", icon: Bell },
  { label: "Settings", href: "/settings", icon: Settings, permission: "school.settings.manage" },
];
