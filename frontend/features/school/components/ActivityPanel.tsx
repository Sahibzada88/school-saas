"use client";

import { useState } from "react";

import { FormField } from "@/components/common/FormField";
import { Pagination } from "@/components/common/Pagination";
import { AuditLogTable } from "@/features/audit/components/AuditLogTable";
import { useSchoolAudit } from "@/features/school/hooks";
import { useDebounce } from "@/hooks/useDebounce";

export function ActivityPanel() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounce(search.trim());
  const { data, isLoading, isFetching, error, refetch } = useSchoolAudit({ page, search: debouncedSearch || undefined });

  return (
    <div className="space-y-4">
      <div className="max-w-sm">
        <FormField
          label="Search activity"
          type="search"
          placeholder="Search details"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
      </div>
      <AuditLogTable rows={data?.results} isLoading={isLoading} error={error} onRetry={() => void refetch()} />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </div>
  );
}
