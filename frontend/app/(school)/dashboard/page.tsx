"use client";

import { PageHeader } from "@/components/common/PageHeader";
import { PermissionGate } from "@/components/common/PermissionGate";
import { SchoolDashboardView } from "@/features/school/components/SchoolDashboardView";
import { useAuth } from "@/hooks/useAuth";

/** Staff roles other than the School Admin get their own dashboards as their modules arrive (Phases 5-9). */
function WelcomeView() {
  const { user, school } = useAuth();
  return (
    <PageHeader
      title={`Welcome, ${user?.first_name ?? ""}`}
      description={`You are signed in to ${school?.name ?? "your school"}. Your tools will appear here as modules are enabled.`}
    />
  );
}

export default function DashboardPage() {
  return (
    <PermissionGate permission="school.dashboard.view" fallback={<WelcomeView />}>
      <SchoolDashboardView />
    </PermissionGate>
  );
}
