export type StudentStatus = "ACTIVE" | "INACTIVE" | "TRANSFERRED" | "GRADUATED" | "SUSPENDED";
export type Gender = "MALE" | "FEMALE" | "OTHER";

export interface CurrentClass {
  enrollment_id: string;
  class_id: string;
  class_name: string;
  section_id: string;
  section_name: string;
  roll_number: number | null;
}

export interface Guardian {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string;
  email: string;
  national_id: string;
  occupation: string;
  address: string;
}

export interface StudentGuardianLink {
  id: string;
  guardian: Guardian;
  relationship: string;
  is_primary: boolean;
  is_emergency_contact: boolean;
}

export interface Student {
  id: string;
  student_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  gender: Gender;
  date_of_birth: string;
  admission_date: string;
  status: StudentStatus;
  phone: string;
  photo_url: string | null;
  current_class: CurrentClass | null;
  email?: string;
  address?: string;
  blood_group?: string;
  notes?: string;
  guardians?: StudentGuardianLink[];
}

export interface Teacher {
  id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  gender: Gender;
  phone: string;
  email: string;
  qualification: string;
  joining_date: string;
  status: string;
  photo_url: string | null;
  date_of_birth?: string | null;
  address?: string;
}

export interface AcademicSession { id: string; name: string; start_date: string; end_date: string; is_current: boolean }
export interface SchoolClass { id: string; name: string; level_order: number; section_count: number }
export interface Section { id: string; school_class: string; class_name: string; name: string; capacity: number | null; class_teacher: string | null; class_teacher_name: string | null; student_count: number }
export interface Subject { id: string; name: string; code: string }
export interface ClassSubject { id: string; school_class: string; class_name: string; subject: string; subject_name: string; is_optional: boolean }
export interface TeacherAssignment { id: string; session: string; teacher: string; teacher_name: string; section: string; section_name: string; subject: string | null; subject_name: string | null; is_class_teacher: boolean }

export interface Enrollment {
  id: string; student: string; student_name: string; student_number: string; session: string; session_name: string;
  school_class: string; class_name: string; section: string; section_name: string; roll_number: number | null; status: string; enrolled_on: string; ended_on: string | null;
}

export interface TimetableSlot {
  id: string; session: string; section: string; section_name: string; subject: string; subject_name: string; teacher: string; teacher_name: string;
  weekday: number; period_no: number; start_time: string; end_time: string; room: string;
}

export type AttendanceStatus = "PRESENT" | "ABSENT" | "LATE" | "LEAVE";
export interface AttendanceRosterRow { student: string; student_name: string; student_number: string; roll_number: number | null; status: AttendanceStatus | null; remarks: string }
export interface TeacherAttendanceRow { teacher: string; teacher_name: string; employee_id: string; status: AttendanceStatus | null; check_in: string | null; check_out: string | null; remarks: string }
export interface AttendanceRecord { id: string; student: string; student_name: string; section_name: string; date: string; status: AttendanceStatus; remarks: string }
export interface MonthlyAttendance {
  month: string;
  students: { student: string; student_name: string; student_number: string; present: number; absent: number; late: number; leave: number; percentage: number | null }[];
}

export type ExamStatus = "DRAFT" | "SCHEDULED" | "MARKS_ENTRY" | "PUBLISHED" | "ARCHIVED";
export interface Exam { id: string; name: string; session: string; session_name: string; exam_type: string; exam_type_name: string; grading_scale: string; start_date: string | null; end_date: string | null; status: ExamStatus; published_at: string | null; subject_count: number }
export interface ExamType { id: string; name: string; weightage: string | null }
export interface ExamSubject { id: string; exam: string; school_class: string; class_name: string; subject: string; subject_name: string; exam_date: string | null; start_time: string | null; duration_minutes: number | null; total_marks: string; passing_marks: string }
export interface GradeBand { grade: string; min_percent: string; max_percent: string; gpa_points: string; remark: string; is_pass: boolean }
export interface GradingScale { id: string; name: string; is_default: boolean; bands: GradeBand[] }
export interface MarksRoster {
  total_marks: string; passing_marks: string; open: boolean;
  rows: { student: string; student_name: string; student_number: string; section: string; roll_number: number | null; obtained_marks: string | null; is_absent: boolean; remarks: string; entered: boolean }[];
}
export interface ResultLine { subject: string; code: string; total: string; obtained: string; passing: string; grade: string; is_absent: boolean; is_pass: boolean; is_missing?: boolean }
export interface ReportCardSummary {
  id: string; exam: string; exam_name: string; student: string; student_name: string; student_number: string; class_name: string; section_name: string;
  total_marks: string; obtained_marks: string; percentage: string; grade: string; gpa: string; position_section: number | null; position_class: number | null; result_status: "PASS" | "FAIL";
}
export interface ReportCardDetail extends ReportCardSummary {
  session_name: string; roll_number: number | null; school_name: string; breakdown: { lines: ResultLine[] }; teacher_remarks: string; principal_remarks: string;
}
export interface PreviewResult {
  student: string; student_name: string; student_number: string; class_name: string; section_name: string; roll_number: number | null; total_marks: string; obtained_marks: string;
  percentage: string; grade: string; gpa: string; result_status: string; missing_marks: number; position_section: number | null; position_class: number | null; lines: ResultLine[];
}

export interface FeeCategory { id: string; name: string; code: string; is_recurring: boolean }
export interface FeeStructure { id: string; name: string; session: string; session_name: string; school_class: string | null; class_name: string; frequency: string; items: { category: string; category_name: string; amount: string }[]; total: string }
export type InvoiceStatus = "ISSUED" | "PARTIALLY_PAID" | "PAID" | "VOID";
export interface Invoice {
  id: string; invoice_number: string; student: { id: string; full_name: string; student_number: string }; period_label: string; issue_date: string; due_date: string;
  total: string; paid_total: string; balance: string; status: InvoiceStatus; is_overdue: boolean;
}
export interface InvoiceDetail extends Invoice {
  subtotal: string; discount_total: string; fine_total: string; void_reason: string; session_name: string; guardian: { name: string; phone: string } | null;
  items: { description: string; quantity: number; unit_amount: string; amount: string }[];
  discounts: { kind: string; value: string; amount: string; reason: string }[];
  fines: { amount: string; reason: string; applied_on: string }[];
  payments: { id: string; receipt_number: string; amount: string; method: string; reference: string; paid_on: string; status: string; reversal_reason: string }[];
}
export interface FeePaymentRow { id: string; receipt_number: string; invoice: string; invoice_number: string; student_name: string; student_number: string; amount: string; method: string; reference: string; paid_on: string; status: string; received_by_name: string | null }

export type AnnouncementAudience = "ALL" | "STAFF" | "TEACHERS" | "PARENTS" | "STUDENTS" | "CLASS";
export interface Announcement { id: string; title: string; body: string; audience: AnnouncementAudience; school_class: string | null; class_name: string | null; is_pinned: boolean; published_at: string; expires_at: string | null; created_by_name: string | null; is_read: boolean }

export interface OutstandingReport { rows: { invoice_id: string; invoice_number: string; student_name: string; student_number: string; class_name: string; period_label: string; due_date: string; balance: string; days_overdue: number; guardian_name: string; guardian_phone: string }[]; count: number; total: string; truncated: boolean }
export interface StudentsSummary { total: number; by_status: Record<string, number>; by_gender: Record<string, number>; by_class: { class_name: string; section_name: string; count: number }[] }
export interface ExamAnalysis { exam: string; status: string; students: number; passed: number; pass_rate: number | null; subjects: { class_name: string; subject: string; total_marks: string; entered: number; absent: number; average: string | null; highest: string | null; lowest: string | null; pass_rate: number | null }[] }

export interface StudentDocument { id: string; student: string; doc_type: string; title: string; received_on: string | null; notes: string }
export interface ImportReport { total: number; created: number; dry_run: boolean; ok: boolean; errors: { row: number; errors: string[] }[] }
export interface ReminderResult { invoices: number; notified: number; no_account: number }
