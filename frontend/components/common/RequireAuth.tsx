"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { FullPageSpinner } from "@/components/common/FullPageSpinner";
import { FormAlert } from "@/components/common/FormAlert";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { guardRedirect, type GuardArea } from "@/lib/routes";

/** Client-side route guard. Authorisation is enforced by the API; this only decides what to render/redirect. */
export function RequireAuth({ area, children }: { area: GuardArea; children: ReactNode }) {
  const { me, isLoading, isError, reload } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const redirectTo = !me ? `/login?next=${encodeURIComponent(pathname)}` : guardRedirect(me, area);

  useEffect(() => {
    if (!isLoading && !isError && redirectTo) router.replace(redirectTo);
  }, [isLoading, isError, redirectTo, router]);

  if (isLoading) return <FullPageSpinner />;

  if (isError) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-6">
        <FormAlert>We could not reach the server. Check your connection and try again.</FormAlert>
        <Button variant="outline" onClick={reload}>
          Try again
        </Button>
      </main>
    );
  }

  if (redirectTo) return <FullPageSpinner />;
  return <>{children}</>;
}
