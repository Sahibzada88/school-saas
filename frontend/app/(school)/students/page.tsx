"use client";

import { Upload, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Avatar } from "@/components/common/Avatar";
import { DataTable, type Column } from "@/components/common/DataTable";
import { DownloadButton } from "@/components/common/DownloadButton";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { ResourceManager } from "@/components/common/ResourceManager";
import { SelectField } from "@/components/common/SelectField";
import { SpecFormDialog } from "@/components/common/SpecForm";
import { Badge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { ImportDialog } from "@/features/imports/ImportDialog";
import { guardianHooks, studentHooks } from "@/features/school/resources";
import type { SchoolUser } from "@/features/school/types";
import { guardianFields, studentFields } from "@/features/students/fields";
import { useAuth } from "@/hooks/useAuth";
import { useDebounce } from "@/hooks/useDebounce";
import { STUDENT_STATUS_OPTIONS, sectionLabel, toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { Guardian, SchoolClass, Section, Student } from "@/types/school";

const TONES: Record<string, "green" | "gray" | "amber" | "blue" | "red"> = { ACTIVE: "green", INACTIVE: "gray", TRANSFERRED: "amber", GRADUATED: "blue", SUSPENDED: "red" };
const accountLabel = (u: SchoolUser) => `${u.first_name} ${u.last_name} (${u.email})`;

function GuardiansTab() {
  const { can } = useAuth();
  const parents = useAllOptions<SchoolUser>("/school/users", { role: "PARENT" }, can("school.users.manage"));
  return (
    <ResourceManager<Guardian>
      noun="guardian" hooks={guardianHooks} canManage={can("guardians.manage")} wide rowLabel={(g) => g.full_name}
      fields={guardianFields(can("school.users.manage") ? toOptions(parents.options, accountLabel) : undefined)}
      initialFor={(g) => ({ ...g, user: (g as unknown as { user?: string }).user ?? "" })}
      emptyDescription="Guardians are created from a student's profile (Guardians tab) or imported with the students CSV."
      columns={[
        { key: "n", header: "Guardian", cell: (g) => <span className="font-medium">{g.full_name}</span> },
        { key: "p", header: "Phone", cell: (g) => g.phone }, { key: "e", header: "Email", cell: (g) => g.email || "—" },
        { key: "o", header: "Occupation", cell: (g) => g.occupation || "—" },
        { key: "a", header: "Account", cell: (g) => ((g as unknown as { user?: string | null }).user ? <Badge tone="green">Linked</Badge> : <Badge>No login</Badge>) },
      ]}
    />
  );
}

function StudentsTab() {
  const { can } = useAuth();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [section, setSection] = useState("");
  const [klass, setKlass] = useState("");
  const [page, setPage] = useState(1);
  const [admitting, setAdmitting] = useState(false);
  const [importing, setImporting] = useState(false);
  const debounced = useDebounce(search.trim());
  const params = { page, search: debounced || undefined, status: status || undefined, section: section || undefined, class: klass || undefined };
  const { data, isLoading, isFetching, error, refetch } = studentHooks.useList(params);
  const create = studentHooks.useCreate();
  const sections = useAllOptions<Section>("/school/sections");
  const classes = useAllOptions<SchoolClass>("/school/classes");
  const accounts = useAllOptions<SchoolUser>("/school/users", { role: "STUDENT" }, can("school.users.manage"));

  const reset = <V,>(setter: (v: V) => void) => (v: V) => { setter(v); setPage(1); };
  const columns: Column<Student>[] = [
    {
      key: "name", header: "Student",
      cell: (s) => (
        <div className="flex items-center gap-3">
          <Avatar name={s.full_name} url={s.photo_url} />
          <div className="leading-tight">
            <Link href={`/students/${s.id}`} className="font-medium underline-offset-4 hover:underline">{s.full_name}</Link>
            <div className="text-xs text-muted-foreground">{s.student_number}</div>
          </div>
        </div>
      ),
    },
    { key: "class", header: "Class", cell: (s) => (s.current_class ? `${s.current_class.class_name}-${s.current_class.section_name}` : "Not enrolled") },
    { key: "gender", header: "Gender", cell: (s) => s.gender.charAt(0) + s.gender.slice(1).toLowerCase() },
    { key: "phone", header: "Phone", cell: (s) => s.phone || "—" },
    { key: "status", header: "Status", cell: (s) => <Badge tone={TONES[s.status]}>{s.status.charAt(0) + s.status.slice(1).toLowerCase()}</Badge> },
  ];

  return (
    <>
      <div className="flex flex-wrap justify-end gap-2">
        {can("exports.students") ? <DownloadButton path="/school/exports/students/csv/" filename="students.csv" query={params}>CSV</DownloadButton> : null}
        {can("students.view") ? <DownloadButton path="/school/reports/students/pdf/" filename="students.pdf" query={{ status: status || undefined, section: section || undefined, class: klass || undefined }}>PDF</DownloadButton> : null}
        {can("students.manage") && section ? <DownloadButton path="/school/reports/id-cards/pdf/" filename="id-cards.pdf" query={{ section }}>ID cards (section)</DownloadButton> : null}
        {can("students.manage") ? <Button variant="outline" onClick={() => setImporting(true)}><Upload className="size-4" /> Import CSV</Button> : null}
        {can("students.manage") ? <Button onClick={() => setAdmitting(true)}><UserPlus className="size-4" /> Admit student</Button> : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FormField label="Search" type="search" placeholder="Name, number, phone" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
        <SelectField label="Status" value={status} onChange={(e) => reset(setStatus)(e.target.value)}>
          <option value="">All statuses</option>
          {STUDENT_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </SelectField>
        <SelectField label="Class" value={klass} onChange={(e) => reset(setKlass)(e.target.value)}>
          <option value="">All classes</option>
          {toOptions(classes.options, (c) => c.name).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </SelectField>
        <SelectField label="Section" value={section} onChange={(e) => reset(setSection)(e.target.value)}>
          <option value="">All sections</option>
          {toOptions(sections.options, sectionLabel).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </SelectField>
      </div>
      <DataTable columns={columns} rows={data?.results} rowKey={(s) => s.id} isLoading={isLoading} error={error} onRetry={() => void refetch()}
        emptyTitle="No students found" emptyDescription={can("students.manage") ? "Admit your first student, or import a CSV file." : "Nothing to show yet."} />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
      <SpecFormDialog wide open={admitting} title="Admit a student" submitLabel="Admit student" onClose={() => setAdmitting(false)}
        fields={studentFields(can("school.users.manage") ? toOptions(accounts.options, accountLabel) : undefined)}
        onSubmit={async (values) => { const created = await create.mutateAsync(values); router.push(`/students/${(created as Student).id}`); }} />
      <ImportDialog open={importing} onClose={() => setImporting(false)} title="Import students from CSV" noun="student" endpoint="/school/students/import/"
        templatePath="/school/students/import-template/" templateName="students-template.csv"
        columns="first_name*, last_name, date_of_birth* (YYYY-MM-DD), gender* (MALE/FEMALE/OTHER), phone, email, address, blood_group, class + section (both, to enrol), guardian_name + guardian_phone (+ guardian_relationship)" />
    </>
  );
}

export default function StudentsPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState<"students" | "guardians">("students");
  return (
    <>
      <PageHeader title="Students" description="Admissions, profiles, guardians and class placement." />
      <Tabs tabs={[{ value: "students", label: "Students" }, ...(can("students.view") ? [{ value: "guardians" as const, label: "Guardians" }] : [])]} value={tab} onChange={setTab} />
      {tab === "students" ? <StudentsTab /> : <GuardiansTab />}
    </>
  );
}
