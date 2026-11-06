"use client";

import { useState } from "react";

import { PermissionDenied } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { PermissionGate } from "@/components/common/PermissionGate";
import { Tabs } from "@/components/common/Tabs";
import { ActivityPanel } from "@/features/school/components/ActivityPanel";
import { ProfileForm } from "@/features/school/components/ProfileForm";
import { UsersPanel } from "@/features/school/components/UsersPanel";

type TabValue = "profile" | "users" | "activity";
const TABS: { value: TabValue; label: string }[] = [
  { value: "profile", label: "School profile" },
  { value: "users", label: "Users" },
  { value: "activity", label: "Activity" },
];

export default function SettingsPage() {
  const [tab, setTab] = useState<TabValue>("profile");

  return (
    <PermissionGate permission="school.settings.manage" fallback={<PermissionDenied />}>
      <PageHeader title="Settings" description="Manage your school profile, team and activity." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      {tab === "profile" ? <ProfileForm /> : null}
      {tab === "users" ? <UsersPanel /> : null}
      {tab === "activity" ? <ActivityPanel /> : null}
    </PermissionGate>
  );
}
