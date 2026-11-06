import { apiFetch, type QueryParams } from "@/lib/api-client";
import { createResource, createResourceHooks, useDataMutation, useDataQuery } from "@/lib/resource";
import type { Paginated } from "@/types/api";
import type * as T from "@/types/school";

const S = "/school";

export const students = createResource<T.Student>(`${S}/students`);
export const studentHooks = createResourceHooks("students", students);
export const guardianHooks = createResourceHooks("guardians", createResource<T.Guardian>(`${S}/guardians`));
export const teachers = createResource<T.Teacher>(`${S}/teachers`);
export const teacherHooks = createResourceHooks("teachers", teachers);
export const sessionHooks = createResourceHooks("sessions", createResource<T.AcademicSession>(`${S}/sessions`));
export const classHooks = createResourceHooks("classes", createResource<T.SchoolClass>(`${S}/classes`));
export const sectionHooks = createResourceHooks("sections", createResource<T.Section>(`${S}/sections`));
export const subjectHooks = createResourceHooks("subjects", createResource<T.Subject>(`${S}/subjects`));
export const classSubjectHooks = createResourceHooks("class-subjects", createResource<T.ClassSubject>(`${S}/class-subjects`));
export const assignmentHooks = createResourceHooks("assignments", createResource<T.TeacherAssignment>(`${S}/teacher-assignments`));
export const enrollments = createResource<T.Enrollment>(`${S}/enrollments`);
export const enrollmentHooks = createResourceHooks("enrollments", enrollments);
export const timetableHooks = createResourceHooks("timetable", createResource<T.TimetableSlot>(`${S}/timetable`));
export const examHooks = createResourceHooks("exams", createResource<T.Exam>(`${S}/exams`));
export const examSubjectHooks = createResourceHooks("exam-subjects", createResource<T.ExamSubject>(`${S}/exam-subjects`));
export const examTypeHooks = createResourceHooks("exam-types", createResource<T.ExamType>(`${S}/exam-types`));
export const gradingScaleHooks = createResourceHooks("grading-scales", createResource<T.GradingScale>(`${S}/grading-scales`));
export const resultHooks = createResourceHooks("results", createResource<T.ReportCardSummary>(`${S}/results`));
export const feeCategoryHooks = createResourceHooks("fee-categories", createResource<T.FeeCategory>(`${S}/fees/categories`));
export const feeStructureHooks = createResourceHooks("fee-structures", createResource<T.FeeStructure>(`${S}/fees/structures`));
export const invoiceHooks = createResourceHooks("invoices", createResource<T.Invoice>(`${S}/fees/invoices`));
export const feePaymentHooks = createResourceHooks("fee-payments", createResource<T.FeePaymentRow>(`${S}/fees/payments`));
export const documentHooks = createResourceHooks("student-documents", createResource<T.StudentDocument>(`${S}/student-documents`));
export const announcementHooks = createResourceHooks("announcements", createResource<T.Announcement>(`${S}/announcements`));

const post = <R>(path: string, body?: unknown) => apiFetch<R>(`${S}${path}`, { method: "POST", body: body ?? {} });

// ---------------------------------------------------------------- students
export const useStudentDetail = (id: string | undefined) => useDataQuery<T.Student>(["student", id], () => apiFetch(`${S}/students/${id}/`), Boolean(id));
export const useChangeStudentStatus = () => useDataMutation(({ id, status, reason }: { id: string; status: string; reason: string }) => post(`/students/${id}/change-status/`, { status, reason }));
export const useLinkGuardian = () => useDataMutation(({ id, body }: { id: string; body: unknown }) => post(`/students/${id}/guardians/`, body));
export const useUnlinkGuardian = () => useDataMutation(({ id, linkId }: { id: string; linkId: string }) => apiFetch(`${S}/students/${id}/guardians/${linkId}/`, { method: "DELETE" }));
export const useEnrollStudent = () => useDataMutation((body: { student: string; section: string; roll_number?: number | null }) => post(`/enrollments/`, body));
export const useMoveEnrollment = () => useDataMutation(({ id, section }: { id: string; section: string }) => apiFetch(`${S}/enrollments/${id}/`, { method: "PATCH", body: { section } }));
export const usePromote = () => useDataMutation((body: unknown) => post<{ promoted: number; repeated: number; graduated: number }>(`/enrollments/promote/`, body));

// ---------------------------------------------------------------- attendance
export const useAttendanceRoster = (section: string, date: string) =>
  useDataQuery<T.AttendanceRosterRow[]>(["att-roster", section, date], () => apiFetch(`${S}/attendance/roster/`, { query: { section, date } }), Boolean(section && date));
export const useMarkAttendance = () =>
  useDataMutation((body: { section: string; date: string; records: { student: string; status: string; remarks?: string }[] }) => post<{ saved: number }>(`/attendance/mark/`, body));
export const useMonthlyAttendance = (params: QueryParams, enabled: boolean) =>
  useDataQuery<T.MonthlyAttendance>(["att-monthly", params], () => apiFetch(`${S}/attendance/monthly/`, { query: params }), enabled);
export const useAttendanceRecords = (params: QueryParams, enabled = true) =>
  useDataQuery<Paginated<T.AttendanceRecord>>(["att-records", params], () => apiFetch(`${S}/attendance/records/`, { query: params }), enabled);
export const useTeacherRoster = (date: string) => useDataQuery<T.TeacherAttendanceRow[]>(["tatt-roster", date], () => apiFetch(`${S}/attendance/teachers/`, { query: { date } }));
export const useMarkTeachers = () => useDataMutation((body: unknown) => post<{ saved: number }>(`/attendance/teachers/`, body));

// ---------------------------------------------------------------- exams
export const useExamAction = () => useDataMutation(({ id, action, body }: { id: string; action: "schedule" | "open-marks" | "archive" | "publish"; body?: unknown }) => post<unknown>(`/exams/${id}/${action}/`, body));
export const useExamSubjects = (examId: string | undefined) => useDataQuery<T.ExamSubject[]>(["exam-subjects-of", examId], () => apiFetch(`${S}/exams/${examId}/subjects/`), Boolean(examId));
export const useExamPreview = (examId: string | undefined, enabled: boolean) =>
  useDataQuery<{ exam: string; status: string; results: T.PreviewResult[] }>(["exam-preview", examId], () => apiFetch(`${S}/exams/${examId}/preview/`), enabled && Boolean(examId));
export const useMarksRoster = (examId: string | undefined, examSubject: string) =>
  useDataQuery<T.MarksRoster>(["marks-roster", examId, examSubject], () => apiFetch(`${S}/exams/${examId}/marks/`, { query: { exam_subject: examSubject } }), Boolean(examId && examSubject));
export const useSaveMarks = (examId: string) => useDataMutation((body: unknown) => post<{ saved: number }>(`/exams/${examId}/marks/`, body));
export const useResultDetail = (id: string | undefined) => useDataQuery<T.ReportCardDetail>(["result", id], () => apiFetch(`${S}/results/${id}/`), Boolean(id));

// ---------------------------------------------------------------- fees
export const useInvoiceDetail = (id: string | undefined) => useDataQuery<T.InvoiceDetail>(["invoice", id], () => apiFetch(`${S}/fees/invoices/${id}/`), Boolean(id));
export const useGenerateInvoices = () => useDataMutation((body: unknown) => post<{ created: number; skipped: number }>(`/fees/invoices/generate/`, body));
export const useInvoiceAction = (id: string) =>
  useDataMutation(({ action, body }: { action: "void" | "discounts" | "fines" | "payments"; body: unknown }) => post<unknown>(`/fees/invoices/${id}/${action}/`, body));
export const useReversePayment = () => useDataMutation(({ id, reason }: { id: string; reason: string }) => post(`/fees/payments/${id}/reverse/`, { reason }));

// ---------------------------------------------------------------- reports / announcements
export const useOutstanding = (params: QueryParams = {}, enabled = true) => useDataQuery<T.OutstandingReport>(["outstanding", params], () => apiFetch(`${S}/reports/fees/outstanding/`, { query: params }), enabled);
export const useStudentsSummary = (enabled = true) => useDataQuery<T.StudentsSummary>(["students-summary"], () => apiFetch(`${S}/reports/students/summary/`), enabled);
export const useExamAnalysis = (examId: string) => useDataQuery<T.ExamAnalysis>(["exam-analysis", examId], () => apiFetch(`${S}/reports/exams/${examId}/`), Boolean(examId));
export const useMarkAnnouncementRead = () => useDataMutation((id: string) => post(`/announcements/${id}/read/`));
export const useUnreadAnnouncements = () => useDataQuery<{ count: number }>(["announcements-unread"], () => apiFetch(`${S}/announcements/unread-count/`));

export const useSendFeeReminders = () => useDataMutation((body: { mode: "overdue" | "due_soon"; days?: number }) => post<T.ReminderResult>(`/fees/invoices/send-reminders/`, body));
export const useSaveRemarks = () => useDataMutation(({ id, body }: { id: string; body: { teacher_remarks?: string; principal_remarks?: string } }) => post<T.ReportCardDetail>(`/results/${id}/remarks/`, body));
export const useTeacherAttendanceHistory = (params: QueryParams) =>
  useDataQuery<Paginated<{ id: string; teacher: string; teacher_name: string; date: string; status: T.AttendanceStatus; check_in: string | null; remarks: string }>>(["tatt-history", params], () => apiFetch(`${S}/attendance/teacher-records/`, { query: params }));
