"use client";

import type { ReactNode } from "react";

import { RequireAuth } from "@/components/common/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { PLATFORM_NAV } from "@/lib/navigation";

export default function PlatformLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth area="platform">
      <AppShell title="Platform admin" nav={PLATFORM_NAV}>
        {children}
      </AppShell>
    </RequireAuth>
  );
}
