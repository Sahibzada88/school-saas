"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/hooks/useAuth";
import { homeRouteFor } from "@/lib/routes";

/** Signed-in users do not need the login/register screens. (Reset links stay usable while signed in.) */
export default function AuthLayout({ children }: { children: ReactNode }) {
  const { me, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const redirectAway = pathname === "/login" || pathname === "/register";

  useEffect(() => {
    if (!isLoading && me && redirectAway) router.replace(homeRouteFor(me));
  }, [isLoading, me, redirectAway, router]);

  return <>{children}</>;
}
