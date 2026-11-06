"use client";

import { useState } from "react";

import { PageHeader } from "@/components/common/PageHeader";
import { ResourceManager } from "@/components/common/ResourceManager";
import { Badge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { PromotionPanel } from "@/features/academics/PromotionPanel";
import { classHooks, sectionHooks, sessionHooks } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { formatDate } from "@/lib/format";
import { toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { AcademicSession, Section, SchoolClass, Teacher } from "@/types/school";

type Tab = "classes" | "sections" | "sessions" | "year-end";

export default function ClassesPage() {
  const { can } = useAuth();
  const manage = can("academics.manage");
  const [tab, setTab] = useState<Tab>("classes");
  const classes = useAllOptions<SchoolClass>("/school/classes");
  const teachers = useAllOptions<Teacher>("/school/teachers", {}, manage && tab === "sections");

  return (
    <>
      <PageHeader title="Classes & sections" description="Academic sessions, classes and their sections." />
      <Tabs tabs={[{ value: "classes", label: "Classes" }, { value: "sections", label: "Sections" }, { value: "sessions", label: "Sessions" }, ...(can("students.lifecycle") ? [{ value: "year-end" as const, label: "Year-end" }] : [])]} value={tab} onChange={setTab} />
      {tab === "classes" ? (
        <ResourceManager<SchoolClass> noun="class" hooks={classHooks} canManage={manage} rowLabel={(c) => c.name}
          fields={[{ name: "name", label: "Class name", type: "text", required: true, placeholder: "e.g. 10" }, { name: "level_order", label: "Order", type: "number", hint: "Used to sort classes (1 = lowest)." }]}
          columns={[{ key: "n", header: "Class", cell: (c) => <span className="font-medium">{c.name}</span> }, { key: "o", header: "Order", cell: (c) => c.level_order }, { key: "s", header: "Sections", cell: (c) => c.section_count }]} />
      ) : null}
      {tab === "sections" ? (
        <ResourceManager<Section> noun="section" hooks={sectionHooks} canManage={manage} rowLabel={(s) => `${s.class_name}-${s.name}`}
          fields={[
            { name: "school_class", label: "Class", type: "select", required: true, options: toOptions(classes.options, (c) => c.name) },
            { name: "name", label: "Section name", type: "text", required: true, placeholder: "e.g. A" },
            { name: "capacity", label: "Capacity", type: "number", nullable: true, hint: "Leave empty for no limit." },
            { name: "class_teacher", label: "Class teacher", type: "select", nullable: true, options: toOptions(teachers.options, (t) => t.full_name) },
          ]}
          columns={[{ key: "c", header: "Class", cell: (s) => s.class_name }, { key: "n", header: "Section", cell: (s) => <span className="font-medium">{s.name}</span> },
            { key: "t", header: "Class teacher", cell: (s) => s.class_teacher_name ?? "—" }, { key: "st", header: "Students", cell: (s) => (s.capacity ? `${s.student_count} / ${s.capacity}` : s.student_count) }]} />
      ) : null}
      {tab === "sessions" ? (
        <ResourceManager<AcademicSession> noun="session" hooks={sessionHooks} canManage={manage} rowLabel={(s) => s.name}
          fields={[
            { name: "name", label: "Name", type: "text", required: true, placeholder: "e.g. 2027" },
            { name: "start_date", label: "Starts", type: "date", required: true }, { name: "end_date", label: "Ends", type: "date", required: true },
            { name: "is_current", label: "This is the current session", type: "checkbox" },
          ]}
          columns={[{ key: "n", header: "Session", cell: (s) => <span className="font-medium">{s.name}</span> }, { key: "a", header: "Starts", cell: (s) => formatDate(s.start_date) },
            { key: "b", header: "Ends", cell: (s) => formatDate(s.end_date) }, { key: "c", header: "", cell: (s) => (s.is_current ? <Badge tone="green">Current</Badge> : null) }]} />
      ) : null}
      {tab === "year-end" ? <PromotionPanel /> : null}
    </>
  );
}
