"use client";

import { useState } from "react";

import { Avatar } from "@/components/common/Avatar";
import { Upload } from "lucide-react";

import { DownloadButton } from "@/components/common/DownloadButton";
import { PageHeader } from "@/components/common/PageHeader";
import { ResourceManager } from "@/components/common/ResourceManager";
import type { FieldSpec } from "@/components/common/SpecForm";
import { Badge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { ImportDialog } from "@/features/imports/ImportDialog";
import { assignmentHooks, teacherHooks } from "@/features/school/resources";
import type { SchoolUser } from "@/features/school/types";
import { useAuth } from "@/hooks/useAuth";
import { formatDate } from "@/lib/format";
import { GENDER_OPTIONS, sectionLabel, toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { AcademicSession, Section, Subject, Teacher, TeacherAssignment } from "@/types/school";

type Tab = "teachers" | "assignments";

export default function TeachersPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("teachers");
  const [importing, setImporting] = useState(false);
  const users = useAllOptions<SchoolUser>("/school/users", { role: "TEACHER" }, can("school.users.manage"));
  const teachers = useAllOptions<Teacher>("/school/teachers", {}, tab === "assignments");
  const sections = useAllOptions<Section>("/school/sections", {}, tab === "assignments");
  const subjects = useAllOptions<Subject>("/school/subjects", {}, tab === "assignments");
  const sessions = useAllOptions<AcademicSession>("/school/sessions", {}, tab === "assignments");

  const teacherFields: FieldSpec[] = [
    { name: "first_name", label: "First name", type: "text", required: true },
    { name: "last_name", label: "Last name", type: "text" },
    { name: "gender", label: "Gender", type: "select", required: true, options: GENDER_OPTIONS },
    { name: "date_of_birth", label: "Date of birth", type: "date", nullable: true },
    { name: "phone", label: "Phone", type: "tel" },
    { name: "email", label: "Email", type: "email" },
    { name: "qualification", label: "Qualification", type: "text" },
    { name: "joining_date", label: "Joining date", type: "date", hint: "Defaults to today" },
    { name: "status", label: "Status", type: "select", required: true, options: ["ACTIVE", "ON_LEAVE", "RESIGNED", "TERMINATED"].map((v) => ({ value: v, label: v.replace("_", " ").toLowerCase() })) },
    ...(can("school.users.manage") ? [{ name: "user", label: "Sign-in account", type: "select" as const, nullable: true, options: toOptions(users.options, (u) => `${u.first_name} ${u.last_name} (${u.email})`), hint: "Link a School user with the Teacher role so they can mark attendance and enter marks." }] : []),
    { name: "address", label: "Address", type: "text", full: true },
    { name: "photo", label: "Photo", type: "image" },
  ];
  const currentSession = sessions.options.find((s) => s.is_current);

  return (
    <>
      <PageHeader title="Teachers" description="Staff profiles and class assignments."
        actions={
          <>
            {can("exports.teachers") ? <DownloadButton path="/school/exports/teachers/csv/" filename="teachers.csv">CSV</DownloadButton> : null}
            {can("teachers.manage") ? <Button variant="outline" onClick={() => setImporting(true)}><Upload className="size-4" /> Import CSV</Button> : null}
          </>
        } />
      <ImportDialog open={importing} onClose={() => setImporting(false)} title="Import teachers from CSV" noun="teacher" endpoint="/school/teachers/import/"
        templatePath="/school/teachers/import-template/" templateName="teachers-template.csv"
        columns="first_name*, last_name, gender* (MALE/FEMALE/OTHER), phone, email, qualification, joining_date (YYYY-MM-DD), date_of_birth, address" />
      <Tabs tabs={[{ value: "teachers", label: "Teachers" }, { value: "assignments", label: "Assignments" }]} value={tab} onChange={setTab} />
      {tab === "teachers" ? (
        <ResourceManager<Teacher>
          noun="teacher" hooks={teacherHooks} canManage={can("teachers.manage")} fields={teacherFields} wide rowLabel={(t) => t.full_name}
          createInitial={{ status: "ACTIVE" }} imageUrlsFor={(t) => ({ photo: t.photo_url })}
          initialFor={(t) => ({ ...t, user: (t as unknown as { user?: string }).user ?? "" })}
          columns={[
            { key: "n", header: "Teacher", cell: (t) => <div className="flex items-center gap-3"><Avatar name={t.full_name} url={t.photo_url} /><div className="leading-tight"><span className="font-medium">{t.full_name}</span><div className="text-xs text-muted-foreground">{t.employee_id}</div></div></div> },
            { key: "q", header: "Qualification", cell: (t) => t.qualification || "—" }, { key: "p", header: "Phone", cell: (t) => t.phone || "—" },
            { key: "j", header: "Joined", cell: (t) => formatDate(t.joining_date) },
            { key: "s", header: "Status", cell: (t) => <Badge tone={t.status === "ACTIVE" ? "green" : "gray"}>{t.status.replace("_", " ").toLowerCase()}</Badge> },
          ]}
        />
      ) : (
        <ResourceManager<TeacherAssignment>
          noun="assignment" hooks={assignmentHooks} canManage={can("academics.manage")} allowEdit={false} rowLabel={(a) => `${a.teacher_name} → ${a.section_name}`}
          createInitial={{ session: currentSession?.id ?? "" }}
          fields={[
            { name: "session", label: "Session", type: "select", required: true, options: toOptions(sessions.options, (s) => s.name + (s.is_current ? " (current)" : "")) },
            { name: "teacher", label: "Teacher", type: "select", required: true, options: toOptions(teachers.options, (t) => t.full_name) },
            { name: "section", label: "Section", type: "select", required: true, options: toOptions(sections.options, sectionLabel) },
            { name: "subject", label: "Subject", type: "select", nullable: true, options: toOptions(subjects.options, (s) => s.name), hint: "Leave empty for all subjects (e.g. class teacher)." },
            { name: "is_class_teacher", label: "Class teacher of this section", type: "checkbox" },
          ]}
          columns={[
            { key: "t", header: "Teacher", cell: (a) => <span className="font-medium">{a.teacher_name}</span> },
            { key: "s", header: "Section", cell: (a) => a.section_name }, { key: "sub", header: "Subject", cell: (a) => a.subject_name ?? "All subjects" },
            { key: "c", header: "", cell: (a) => (a.is_class_teacher ? <Badge tone="blue">Class teacher</Badge> : null) },
          ]}
        />
      )}
    </>
  );
}
