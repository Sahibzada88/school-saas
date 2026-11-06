"use client";

import { ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { RequireAuth } from "@/components/common/RequireAuth";
import { Skeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
import { NotificationItem } from "@/features/notifications/components/NotificationItem";
import { useNotifications } from "@/features/notifications/hooks";
import { useAuth } from "@/hooks/useAuth";
import { homeRouteFor } from "@/lib/routes";

function SuspendedNotice() {
  const { me, logout } = useAuth();
  const router = useRouter();
  const home = me ? homeRouteFor(me) : "/login";
  const notifications = useNotifications({ unread: false }, home === "/suspended");

  // Reactivated (or never blocked): send the user where they belong.
  useEffect(() => {
    if (home !== "/suspended") router.replace(home);
  }, [home, router]);

  const schoolDisabled = me?.school?.status !== "ACTIVE";
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <ShieldAlert className="size-10 text-destructive" aria-hidden />
      <h1 className="text-xl font-semibold tracking-tight">{schoolDisabled ? "Account disabled" : "Subscription not active"}</h1>
      <p className="text-sm text-muted-foreground">
        {schoolDisabled
          ? "Your school account has been temporarily disabled. Please contact platform administration."
          : "Access is paused because your school's subscription is not active. Please contact platform administration."}
      </p>
      {notifications.isLoading ? (
        <Skeleton className="h-16 w-full" />
      ) : (notifications.data?.results.length ?? 0) > 0 ? (
        <ul className="w-full divide-y overflow-hidden rounded-lg border bg-card text-left">
          {notifications.data?.results.slice(0, 3).map((n) => <NotificationItem key={n.id} notification={n} />)}
        </ul>
      ) : null}
      <Button variant="outline" onClick={() => void logout()}>
        Sign out
      </Button>
    </main>
  );
}

export default function SuspendedPage() {
  return (
    <RequireAuth area="any">
      <SuspendedNotice />
    </RequireAuth>
  );
}
