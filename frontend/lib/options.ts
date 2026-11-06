import type { Section } from "@/types/school";

export const toOptions = <T extends { id: string }>(items: T[] | undefined, label: (item: T) => string) =>
  (items ?? []).map((item) => ({ value: item.id, label: label(item) }));

export const sectionLabel = (section: Section) => `${section.class_name}-${section.name}`;

export const GENDER_OPTIONS = [
  { value: "MALE", label: "Male" },
  { value: "FEMALE", label: "Female" },
  { value: "OTHER", label: "Other" },
];

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const STUDENT_STATUS_OPTIONS = ["ACTIVE", "INACTIVE", "TRANSFERRED", "GRADUATED", "SUSPENDED"].map((value) => ({
  value,
  label: value.charAt(0) + value.slice(1).toLowerCase(),
}));

export const today = () => new Date().toISOString().slice(0, 10);
