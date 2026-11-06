"use client";

import { useState } from "react";

import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { SelectField } from "@/components/common/SelectField";
import { AuditLogTable } from "@/features/audit/components/AuditLogTable";
import { useAuditActions, usePlatformAuditLogs } from "@/features/platform/hooks";
import { useDebounce } from "@/hooks/useDebounce";
import { humanizeCode } from "@/lib/format";

export default function PlatformAuditLogsPage() {
  const [action, setAction] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounce(search.trim());
  const actions = useAuditActions();

  const { data, isLoading, isFetching, error, refetch } = usePlatformAuditLogs({
    page,
    action: action || undefined,
    search: debouncedSearch || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const reset = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setPage(1);
  };

  return (
    <>
      <PageHeader title="Audit logs" description="Security and administration events across all schools." />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SelectField label="Action" value={action} onChange={(e) => reset(setAction)(e.target.value)}>
          <option value="">All actions</option>
          {(actions.data ?? []).map((code) => (
            <option key={code} value={code}>
              {humanizeCode(code)}
            </option>
          ))}
        </SelectField>
        <FormField label="Search" type="search" placeholder="Details or actor email" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
        <FormField label="From" type="date" value={dateFrom} onChange={(e) => reset(setDateFrom)(e.target.value)} />
        <FormField label="To" type="date" value={dateTo} onChange={(e) => reset(setDateTo)(e.target.value)} />
      </div>

      <AuditLogTable rows={data?.results} isLoading={isLoading} error={error} onRetry={() => void refetch()} showSchool showIp />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </>
  );
}
