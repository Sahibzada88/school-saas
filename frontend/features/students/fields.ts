import type { FieldSpec } from "@/components/common/SpecForm";
import { GENDER_OPTIONS } from "@/lib/options";

type Option = { value: string; label: string };

/** `accountOptions`: School users with the Student role (only the School Admin may list users). */
export const studentFields = (accountOptions?: Option[]): FieldSpec[] => [
  { name: "first_name", label: "First name", type: "text", required: true },
  { name: "last_name", label: "Last name", type: "text" },
  { name: "date_of_birth", label: "Date of birth", type: "date", required: true },
  { name: "gender", label: "Gender", type: "select", required: true, options: GENDER_OPTIONS },
  { name: "phone", label: "Phone", type: "tel" },
  { name: "email", label: "Email", type: "email" },
  { name: "blood_group", label: "Blood group", type: "text" },
  { name: "admission_date", label: "Admission date", type: "date", hint: "Defaults to today" },
  { name: "address", label: "Address", type: "text", full: true },
  ...(accountOptions ? [{ name: "user", label: "Student's sign-in account", type: "select" as const, nullable: true, options: accountOptions, hint: "Lets the student see their own attendance, fees and results." }] : []),
  { name: "notes", label: "Notes", type: "textarea" },
  { name: "photo", label: "Photo", type: "image" },
];

/** `accountOptions`: School users with the Parent role. */
export const guardianFields = (accountOptions?: Option[]): FieldSpec[] => [
  { name: "first_name", label: "First name", type: "text", required: true },
  { name: "last_name", label: "Last name", type: "text" },
  { name: "phone", label: "Phone", type: "tel", required: true },
  { name: "email", label: "Email", type: "email" },
  { name: "national_id", label: "National ID", type: "text" },
  { name: "occupation", label: "Occupation", type: "text" },
  ...(accountOptions ? [{ name: "user", label: "Parent's sign-in account", type: "select" as const, nullable: true, options: accountOptions, hint: "Lets the parent see their children's attendance, fees and results, and receive alerts." }] : []),
  { name: "address", label: "Address", type: "text", full: true },
];

export const STUDENT_FIELDS: FieldSpec[] = studentFields();
export const GUARDIAN_FIELDS: FieldSpec[] = guardianFields();

export const RELATIONSHIP_OPTIONS = [
  { value: "FATHER", label: "Father" },
  { value: "MOTHER", label: "Mother" },
  { value: "GUARDIAN", label: "Guardian" },
  { value: "OTHER", label: "Other" },
];
