"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { AuthCard } from "@/features/auth/components/AuthCard";
import { ApiError } from "@/lib/api-client";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/schemas/auth";
import { authService } from "@/services/auth";

export function ForgotPasswordForm() {
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema), defaultValues: { email: "" } });

  const onSubmit = handleSubmit(async ({ email }) => {
    setFormError(null);
    try {
      await authService.requestPasswordReset(email);
      setSent(true);
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Something went wrong. Please try again.");
    }
  });

  return (
    <AuthCard
      title="Forgot your password?"
      description="Enter your email and we will send you a reset link."
      footer={
        <Link href="/login" className="font-medium text-foreground underline underline-offset-4">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <FormAlert variant="success">If an account exists for that email, a reset link has been sent.</FormAlert>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {formError ? <FormAlert>{formError}</FormAlert> : null}
          <FormField label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null} Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
