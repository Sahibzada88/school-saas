"use client";

import type { ReactNode } from "react";

import { RequireAuth } from "@/components/common/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { SubscriptionBanner } from "@/features/billing/components/SubscriptionBanner";
import { useAuth } from "@/hooks/useAuth";
import { SCHOOL_NAV } from "@/lib/navigation";

function SchoolShell({ children }: { children: ReactNode }) {
  const { school } = useAuth();
  return (
    <AppShell title={school?.name ?? "School"} nav={SCHOOL_NAV}>
      <SubscriptionBanner />
      {children}
    </AppShell>
  );
}

export default function SchoolLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth area="school">
      <SchoolShell>{children}</SchoolShell>
    </RequireAuth>
  );
}
