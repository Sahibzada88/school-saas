"use client";

import { RequireAuth } from "@/components/common/RequireAuth";
import { ChangePasswordForm } from "@/features/auth/components/ChangePasswordForm";

export default function ChangePasswordPage() {
  return (
    <RequireAuth area="any">
      <ChangePasswordForm />
    </RequireAuth>
  );
}
