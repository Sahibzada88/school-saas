"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

/** Last-resort boundary: any unexpected render error ends up here instead of a blank screen. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <AlertTriangle className="size-10 text-destructive" aria-hidden />
      <h1 className="text-xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="text-sm text-muted-foreground">An unexpected error occurred. Your data is safe. Try again, and contact support if it keeps happening.{error.digest ? ` (ref ${error.digest})` : ""}</p>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
