"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { SelectField } from "@/components/common/SelectField";
import { Skeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
import { usePlans, usePlatformSettings, useUpdateSettings } from "@/features/platform/hooks";
import type { SettingItem } from "@/features/platform/types";
import { serverMessage } from "@/lib/forms";

function SettingsForm({ items }: { items: SettingItem[] }) {
  const plans = usePlans();
  const update = useUpdateSettings();
  const initial = Object.fromEntries(items.map((item) => [item.key, String(item.value)]));
  const [draft, setDraft] = useState<Record<string, string>>(initial);
  const [saved, setSaved] = useState(false);

  const changed = items.filter((item) => draft[item.key] !== String(item.value));

  const save = () => {
    setSaved(false);
    const values: Record<string, string | number> = {};
    for (const item of changed) values[item.key] = item.kind === "int" ? Number(draft[item.key]) : draft[item.key];
    update.mutate(values, { onSuccess: () => setSaved(true) });
  };

  return (
    <div className="max-w-2xl space-y-5 rounded-lg border bg-card p-4 shadow-sm">
      {update.error ? <FormAlert>{serverMessage(update.error)}</FormAlert> : null}
      {saved ? <FormAlert variant="success">Settings saved.</FormAlert> : null}
      {items.map((item) => {
        const common = { label: item.key.replace(/_/g, " "), value: draft[item.key] };
        const onChange = (value: string) => {
          setSaved(false);
          setDraft((current) => ({ ...current, [item.key]: value }));
        };
        return (
          <div key={item.key} className="space-y-1">
            {item.kind === "choice" ? (
              <SelectField {...common} onChange={(e) => onChange(e.target.value)}>
                {item.choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
              </SelectField>
            ) : item.key === "trial_plan_slug" ? (
              <SelectField {...common} onChange={(e) => onChange(e.target.value)}>
                <option value="">No plan (no limits during trial)</option>
                {(plans.data ?? []).filter((p) => p.is_active).map((p) => <option key={p.id} value={p.slug}>{p.name}</option>)}
              </SelectField>
            ) : (
              <FormField {...common} type={item.kind === "int" ? "number" : "text"} min={item.minimum ?? undefined} max={item.maximum ?? undefined} onChange={(e) => onChange(e.target.value)} />
            )}
            <p className="text-sm text-muted-foreground">
              {item.description} Default: {String(item.default) || "none"}.
            </p>
          </div>
        );
      })}
      <Button onClick={save} disabled={changed.length === 0 || update.isPending}>
        {update.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Save changes
      </Button>
    </div>
  );
}

export default function PlatformSettingsPage() {
  const { data, isLoading, error, refetch } = usePlatformSettings();
  return (
    <>
      <PageHeader title="Platform settings" description="Trial length, notice windows and what happens when a subscription ends. Changes apply immediately." />
      {error ? (
        <div className="rounded-lg border bg-card"><ErrorState error={error} onRetry={() => void refetch()} /></div>
      ) : isLoading || !data ? (
        <Skeleton className="h-96 max-w-2xl" />
      ) : (
        <SettingsForm key={data.map((i) => String(i.value)).join("|")} items={data} />
      )}
    </>
  );
}
