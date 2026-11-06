import { Lock } from "lucide-react";
import Link from "next/link";

export default function ForbiddenPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <Lock className="size-10 text-muted-foreground" aria-hidden />
      <h1 className="text-xl font-semibold tracking-tight">Permission denied</h1>
      <p className="text-sm text-muted-foreground">You do not have access to this page.</p>
      <Link href="/" className="text-sm font-medium underline underline-offset-4">
        Go to your home page
      </Link>
    </main>
  );
}
