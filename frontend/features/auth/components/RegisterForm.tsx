"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { AuthCard } from "@/features/auth/components/AuthCard";
import { useAuth } from "@/hooks/useAuth";
import { applyServerErrors } from "@/lib/forms";
import { homeRouteFor } from "@/lib/routes";
import { registerSchema, type RegisterValues } from "@/schemas/auth";

const SERVER_FIELDS = ["school_name", "admin_name", "email", "phone", "country", "city", "password"] as const;

export function RegisterForm() {
  const { register: registerSchool } = useAuth();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      school_name: "",
      admin_name: "",
      email: "",
      phone: "",
      country: "",
      city: "",
      password: "",
      confirm_password: "",
    },
  });

  const onSubmit = handleSubmit(async ({ confirm_password: _confirm, ...payload }) => {
    void _confirm;
    setFormError(null);
    try {
      const me = await registerSchool(payload);
      router.replace(homeRouteFor(me));
    } catch (error) {
      setFormError(applyServerErrors(error, setError, SERVER_FIELDS));
    }
  });

  return (
    <AuthCard
      title="Register your school"
      description="Create your school account and start a free trial."
      footer={
        <>
          Already registered?{" "}
          <Link href="/login" className="font-medium text-foreground underline underline-offset-4">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError ? <FormAlert>{formError}</FormAlert> : null}
        <FormField label="School name" autoComplete="organization" error={errors.school_name?.message} {...register("school_name")} />
        <FormField label="Your name" autoComplete="name" error={errors.admin_name?.message} {...register("admin_name")} />
        <FormField label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
        <FormField label="Phone (optional)" type="tel" autoComplete="tel" error={errors.phone?.message} {...register("phone")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Country" autoComplete="country-name" error={errors.country?.message} {...register("country")} />
          <FormField label="City" autoComplete="address-level2" error={errors.city?.message} {...register("city")} />
        </div>
        <FormField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 10 characters."
          error={errors.password?.message}
          {...register("password")}
        />
        <FormField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password?.message}
          {...register("confirm_password")}
        />
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null} Create school account
        </Button>
      </form>
    </AuthCard>
  );
}
