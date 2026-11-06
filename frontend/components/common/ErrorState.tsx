import { AlertCircle, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";

/** Error and permission-denied states for any failed query. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const denied = error instanceof ApiError && error.status === 403;
  const message = denied
    ? error.message || "You do not have permission to view this."
    : error instanceof ApiError
      ? error.message
      : "Something went wrong. Please try again.";
  const Icon = denied ? Lock : AlertCircle;

  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-4 py-12 text-center">
      <Icon className="size-8 text-muted-foreground" aria-hidden />
      <p className="max-w-sm text-sm text-muted-foreground">{message}</p>
      {onRetry && !denied ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export function PermissionDenied() {
  return (
    <div className="rounded-lg border bg-card">
      <div role="alert" className="flex flex-col items-center gap-2 px-4 py-12 text-center">
        <Lock className="size-8 text-muted-foreground" aria-hidden />
        <p className="font-medium">Permission denied</p>
        <p className="text-sm text-muted-foreground">You do not have access to this page.</p>
      </div>
    </div>
  );
}
