"use client";

import { useState } from "react";

import { PageHeader } from "@/components/common/PageHeader";
import { ResourceManager } from "@/components/common/ResourceManager";
import { Badge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { classSubjectHooks, subjectHooks } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { ClassSubject, SchoolClass, Subject } from "@/types/school";

export default function SubjectsPage() {
  const { can } = useAuth();
  const manage = can("academics.manage");
  const [tab, setTab] = useState<"subjects" | "by-class">("subjects");
  const classes = useAllOptions<SchoolClass>("/school/classes", {}, tab === "by-class");
  const subjects = useAllOptions<Subject>("/school/subjects", {}, tab === "by-class");

  return (
    <>
      <PageHeader title="Subjects" description="The subjects your school teaches and which classes study them." />
      <Tabs tabs={[{ value: "subjects", label: "Subjects" }, { value: "by-class", label: "Subjects by class" }]} value={tab} onChange={setTab} />
      {tab === "subjects" ? (
        <ResourceManager<Subject> noun="subject" hooks={subjectHooks} canManage={manage} rowLabel={(s) => s.name}
          fields={[{ name: "name", label: "Subject name", type: "text", required: true }, { name: "code", label: "Code", type: "text", required: true, placeholder: "MTH" }]}
          columns={[{ key: "n", header: "Subject", cell: (s) => <span className="font-medium">{s.name}</span> }, { key: "c", header: "Code", cell: (s) => s.code }]} />
      ) : (
        <ResourceManager<ClassSubject> noun="class subject" hooks={classSubjectHooks} canManage={manage} allowEdit={false} rowLabel={(c) => `${c.subject_name} in class ${c.class_name}`}
          fields={[
            { name: "school_class", label: "Class", type: "select", required: true, options: toOptions(classes.options, (c) => c.name) },
            { name: "subject", label: "Subject", type: "select", required: true, options: toOptions(subjects.options, (s) => s.name) },
            { name: "is_optional", label: "Optional subject", type: "checkbox" },
          ]}
          columns={[{ key: "c", header: "Class", cell: (c) => c.class_name }, { key: "s", header: "Subject", cell: (c) => c.subject_name }, { key: "o", header: "", cell: (c) => (c.is_optional ? <Badge>Optional</Badge> : null) }]} />
      )}
    </>
  );
}
