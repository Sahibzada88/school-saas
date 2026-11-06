"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { FullPageSpinner } from "@/components/common/FullPageSpinner";
import { useAuth } from "@/hooks/useAuth";
import { homeRouteFor } from "@/lib/routes";

/** Entry point: send each visitor to the login screen or their home page. */
export default function HomePage() {
  const { me, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) router.replace(me ? homeRouteFor(me) : "/login");
  }, [isLoading, me, router]);

  return <FullPageSpinner />;
}
