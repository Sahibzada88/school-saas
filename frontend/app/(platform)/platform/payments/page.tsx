"use client";

import { useState } from "react";

import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { SelectField } from "@/components/common/SelectField";
import { PaymentsTable } from "@/features/billing/components/PaymentsTable";
import { usePlatformPayments } from "@/features/platform/hooks";
import { useDebounce } from "@/hooks/useDebounce";

export default function PaymentsPage() {
  const [search, setSearch] = useState("");
  const [method, setMethod] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounce(search.trim());

  const { data, isLoading, isFetching, error, refetch } = usePlatformPayments({
    page,
    search: debouncedSearch || undefined,
    method: method || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const reset = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setPage(1);
  };

  return (
    <>
      <PageHeader title="Payments" description="Subscription payments recorded by platform staff. To record one, open the school's Subscription tab." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FormField label="Search" type="search" placeholder="Reference or school" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
        <SelectField label="Method" value={method} onChange={(e) => reset(setMethod)(e.target.value)}>
          <option value="">All methods</option>
          <option value="BANK_TRANSFER">Bank transfer</option>
          <option value="JAZZCASH">JazzCash</option>
          <option value="EASYPAISA">Easypaisa</option>
          <option value="CASH">Cash</option>
          <option value="OTHER">Other</option>
        </SelectField>
        <FormField label="From" type="date" value={dateFrom} onChange={(e) => reset(setDateFrom)(e.target.value)} />
        <FormField label="To" type="date" value={dateTo} onChange={(e) => reset(setDateTo)(e.target.value)} />
      </div>
      <PaymentsTable rows={data?.results} isLoading={isLoading} error={error} onRetry={() => void refetch()} />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </>
  );
}
