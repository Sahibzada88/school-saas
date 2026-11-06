"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ErrorState } from "@/components/common/ErrorState";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Skeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
import { useSchoolProfile, useUpdateProfile } from "@/features/school/hooks";
import type { SchoolProfile } from "@/features/school/types";
import { applyServerErrors } from "@/lib/forms";
import { fileToDataUrl } from "@/lib/image";
import { profileSchema, type ProfileValues } from "@/schemas/school";

const FIELDS = ["name", "email", "phone", "country", "city", "address", "timezone"] as const;

function LogoUploader({ profile }: { profile: SchoolProfile }) {
  const update = useUpdateProfile();
  const [problem, setProblem] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save(value: string | null) {
    setProblem(null);
    setSaved(false);
    try {
      await update.mutateAsync({ logo: value });
      setSaved(true);
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "Could not save the logo.");
    }
  }

  return (
    <section className="max-w-2xl space-y-3 rounded-lg border bg-card p-4 shadow-sm">
      <h2 className="font-medium">School logo</h2>
      <div className="flex items-center gap-4">
        {profile.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={profile.logo_url} alt="School logo" className="size-20 rounded-md border object-contain" />
        ) : (
          <div className="flex size-20 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">No logo</div>
        )}
        <div className="space-y-1.5">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label="Upload logo"
            className="text-sm"
            disabled={update.isPending}
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              try {
                await save(await fileToDataUrl(file, 600));
              } catch (error) {
                setProblem(error instanceof Error ? error.message : "Could not read that image.");
              }
              event.target.value = "";
            }}
          />
          {profile.logo_url ? <button type="button" className="block text-xs text-muted-foreground underline" onClick={() => void save(null)}>Remove logo</button> : null}
          <p className="text-xs text-muted-foreground">PNG, JPEG or WEBP. It is resized automatically (max 600 px).</p>
        </div>
      </div>
      {problem ? <FormAlert>{problem}</FormAlert> : null}
      {saved ? <FormAlert variant="success">Logo saved.</FormAlert> : null}
    </section>
  );
}

function ProfileFormInner({ profile }: { profile: SchoolProfile }) {
  const update = useUpdateProfile();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: profile.name,
      email: profile.email,
      phone: profile.phone,
      country: profile.country,
      city: profile.city,
      address: profile.address,
      timezone: profile.timezone,
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    setSaved(false);
    try {
      await update.mutateAsync(values);
      reset(values);
      setSaved(true);
    } catch (error) {
      setFormError(applyServerErrors(error, setError, FIELDS));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-2xl space-y-4 rounded-lg border bg-card p-4 shadow-sm">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      {saved ? <FormAlert variant="success">School profile saved.</FormAlert> : null}
      <FormField label="School name" error={errors.name?.message} {...register("name")} />
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Email" type="email" error={errors.email?.message} {...register("email")} />
        <FormField label="Phone" type="tel" error={errors.phone?.message} {...register("phone")} />
        <FormField label="Country" error={errors.country?.message} {...register("country")} />
        <FormField label="City" error={errors.city?.message} {...register("city")} />
      </div>
      <FormField label="Address" error={errors.address?.message} {...register("address")} />
      <FormField
        label="Time zone"
        hint="IANA name, for example Asia/Karachi."
        error={errors.timezone?.message}
        {...register("timezone")}
      />
      <Button type="submit" disabled={!isDirty || update.isPending}>
        {update.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Save changes
      </Button>
    </form>
  );
}

export function ProfileForm() {
  const { data, isLoading, error, refetch } = useSchoolProfile();
  if (error) {
    return (
      <div className="rounded-lg border bg-card">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    );
  }
  if (isLoading || !data) return <Skeleton className="h-96 max-w-2xl" />;
  return (
    <div className="space-y-4">
      <LogoUploader profile={data} />
      <ProfileFormInner profile={data} />
    </div>
  );
}
