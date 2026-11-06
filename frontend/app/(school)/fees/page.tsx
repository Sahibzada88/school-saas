"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { DownloadButton } from "@/components/common/DownloadButton";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { ResourceManager } from "@/components/common/ResourceManager";
import { SelectField } from "@/components/common/SelectField";
import { SpecFormDialog } from "@/components/common/SpecForm";
import { Badge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { StructureDialog } from "@/features/fees/StructureDialog";
import { invoiceTone } from "@/features/fees/tone";
import { feeCategoryHooks, feePaymentHooks, feeStructureHooks, invoiceHooks, useGenerateInvoices, useReversePayment, useSendFeeReminders } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { useDebounce } from "@/hooks/useDebounce";
import { formatDate, formatMoney } from "@/lib/format";
import { sectionLabel, toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { FeeCategory, FeePaymentRow, FeeStructure, Invoice, Section } from "@/types/school";

type Tab = "invoices" | "payments" | "structures" | "categories";

function InvoicesTab() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [page, setPage] = useState(1);
  const [generating, setGenerating] = useState(false);
  const [reminding, setReminding] = useState(false);
  const reminders = useSendFeeReminders();
  const debounced = useDebounce(search.trim());
  const { data, isLoading, isFetching, error, refetch } = invoiceHooks.useList({ page, search: debounced || undefined, status: status || undefined, overdue: overdue ? "true" : undefined });
  const generate = useGenerateInvoices();
  const structures = useAllOptions<FeeStructure>("/school/fees/structures", {}, generating);
  const sections = useAllOptions<Section>("/school/sections", {}, generating);
  const [result, setResult] = useState<string | null>(null);
  const reset = <V,>(set: (v: V) => void) => (v: V) => { set(v); setPage(1); };
  const columns: Column<Invoice>[] = [
    { key: "n", header: "Invoice", cell: (i) => <Link href={`/fees/invoices/${i.id}`} className="font-medium underline-offset-4 hover:underline">{i.invoice_number}</Link> },
    { key: "s", header: "Student", cell: (i) => <div className="leading-tight">{i.student.full_name}<div className="text-xs text-muted-foreground">{i.student.student_number}</div></div> },
    { key: "p", header: "Period", cell: (i) => i.period_label }, { key: "d", header: "Due", cell: (i) => formatDate(i.due_date) },
    { key: "t", header: "Total", className: "tabular-nums", cell: (i) => formatMoney(i.total, "PKR") }, { key: "b", header: "Balance", className: "tabular-nums", cell: (i) => formatMoney(i.balance, "PKR") },
    { key: "st", header: "Status", cell: (i) => <Badge tone={invoiceTone(i)}>{i.is_overdue ? "Overdue" : i.status.replace("_", " ").toLowerCase()}</Badge> },
  ];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid flex-1 gap-3 sm:grid-cols-3">
          <FormField label="Search" type="search" placeholder="Invoice, student…" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
          <SelectField label="Status" value={status} onChange={(e) => reset(setStatus)(e.target.value)}><option value="">All</option><option value="ISSUED">Issued</option><option value="PARTIALLY_PAID">Partially paid</option><option value="PAID">Paid</option><option value="VOID">Void</option></SelectField>
          <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={overdue} onChange={(e) => reset(setOverdue)(e.target.checked)} /> Overdue only</label>
        </div>
        <div className="flex gap-2">
          {can("exports.fees") ? <DownloadButton path="/school/exports/fees/csv/" filename="invoices.csv" query={{ status: status || undefined }}>CSV</DownloadButton> : null}
          {can("fees.manage") ? <Button variant="outline" onClick={() => { setResult(null); setReminding(true); }}>Send reminders</Button> : null}
          {can("fees.manage") ? <Button onClick={() => { setResult(null); setGenerating(true); }}>Generate invoices</Button> : null}
        </div>
      </div>
      {result ? <p className="rounded-md border bg-card p-3 text-sm" role="status">{result}</p> : null}
      <DataTable columns={columns} rows={data?.results} rowKey={(i) => i.id} isLoading={isLoading} error={error} onRetry={() => void refetch()} emptyTitle="No invoices" emptyDescription="Create a fee structure, then generate invoices for a period." />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
      <SpecFormDialog open={reminding} title="Send fee reminders" submitLabel="Send reminders" onClose={() => setReminding(false)} initial={{ mode: "overdue", days: 7 }}
        description="Parents who have a sign-in account get an in-app notification (and an email if email is configured), once per invoice per day. Parents without an account are counted but not reached: use the WhatsApp buttons on the Reports page for them."
        fields={[
          { name: "mode", label: "Which invoices", type: "select", required: true, options: [{ value: "overdue", label: "Overdue (past the due date)" }, { value: "due_soon", label: "Due soon" }] },
          { name: "days", label: "Due within (days), for 'Due soon'", type: "number", min: 1, max: 30 },
        ]}
        onSubmit={async (v) => { const r = await reminders.mutateAsync({ mode: v.mode as "overdue" | "due_soon", days: Number(v.days) || 7 }); setResult(`${r.invoices} invoice(s) matched: ${r.notified} parent(s) notified, ${r.no_account} without a parent account.`); }} />
      <SpecFormDialog open={generating} title="Generate invoices" description="Creates one invoice per enrolled student for the period. Students who already have one are skipped." submitLabel="Generate" onClose={() => setGenerating(false)}
        fields={[
          { name: "structure", label: "Fee structure", type: "select", required: true, options: toOptions(structures.options, (s) => `${s.name} (${s.class_name})`) },
          { name: "period_label", label: "Period", type: "text", required: true, placeholder: "Oct-2026" }, { name: "due_date", label: "Due date", type: "date", required: true },
          { name: "section", label: "Only this section (optional)", type: "select", nullable: true, options: toOptions(sections.options, sectionLabel) },
        ]}
        onSubmit={async (v) => { const r = await generate.mutateAsync(v); setResult(`${r.created} invoice(s) created, ${r.skipped} skipped (already invoiced).`); }} />
    </div>
  );
}

function PaymentsTab() {
  const { can } = useAuth();
  const [page, setPage] = useState(1);
  const [method, setMethod] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const { data, isLoading, isFetching, error, refetch } = feePaymentHooks.useList({ page, method: method || undefined, date_from: from || undefined, date_to: to || undefined });
  const reverse = useReversePayment();
  const [reversing, setReversing] = useState<FeePaymentRow | null>(null);
  const columns: Column<FeePaymentRow>[] = [
    { key: "r", header: "Receipt", cell: (p) => <span className="font-medium">{p.receipt_number}</span> }, { key: "d", header: "Date", cell: (p) => formatDate(p.paid_on) },
    { key: "s", header: "Student", cell: (p) => p.student_name }, { key: "i", header: "Invoice", cell: (p) => <Link href={`/fees/invoices/${p.invoice}`} className="underline underline-offset-4">{p.invoice_number}</Link> },
    { key: "a", header: "Amount", className: "tabular-nums", cell: (p) => formatMoney(p.amount, "PKR") }, { key: "m", header: "Method", cell: (p) => p.method.toLowerCase() },
    { key: "st", header: "Status", cell: (p) => <Badge tone={p.status === "POSTED" ? "green" : "gray"}>{p.status.toLowerCase()}</Badge> },
    { key: "act", header: "", className: "text-right", cell: (p) => (
      <div className="flex justify-end gap-2">
        <DownloadButton path={`/school/fees/payments/${p.id}/receipt/pdf/`} filename={`receipt-${p.receipt_number}.pdf`}>Receipt</DownloadButton>
        {can("fees.reverse") && p.status === "POSTED" ? <Button variant="outline" size="sm" onClick={() => setReversing(p)}>Reverse</Button> : null}
      </div>) },
  ];
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField label="Method" value={method} onChange={(e) => { setMethod(e.target.value); setPage(1); }}><option value="">All</option>{["CASH", "BANK", "ONLINE", "CHEQUE", "OTHER"].map((m) => <option key={m} value={m}>{m.toLowerCase()}</option>)}</SelectField>
        <FormField label="From" type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} /><FormField label="To" type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} />
      </div>
      <DataTable columns={columns} rows={data?.results} rowKey={(p) => p.id} isLoading={isLoading} error={error} onRetry={() => void refetch()} emptyTitle="No payments" />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
      <SpecFormDialog open={reversing !== null} title="Reverse payment" description={reversing ? `Receipt ${reversing.receipt_number}: the amount returns to the invoice balance. This cannot be undone.` : ""} submitLabel="Reverse payment" onClose={() => setReversing(null)}
        fields={[{ name: "reason", label: "Reason", type: "textarea", required: true }]} onSubmit={(v) => reverse.mutateAsync({ id: reversing!.id, reason: String(v.reason) })} />
    </div>
  );
}

export default function FeesPage() {
  const { can } = useAuth();
  const manage = can("fees.manage");
  const [tab, setTab] = useState<Tab>("invoices");
  const [structure, setStructure] = useState<"new" | FeeStructure | null>(null);
  return (
    <>
      <PageHeader title="Fees" description={manage ? "Structures, invoices and payments." : "Invoices and payments."}
        actions={can("reports.view") && manage ? <DownloadButton path="/school/reports/fees/outstanding/pdf/" filename="outstanding-fees.pdf">Outstanding PDF</DownloadButton> : null} />
      <Tabs tabs={[{ value: "invoices", label: "Invoices" }, { value: "payments", label: "Payments" }, ...(manage ? [{ value: "structures" as const, label: "Fee structures" }, { value: "categories" as const, label: "Categories" }] : [])]} value={tab} onChange={setTab} />
      {tab === "invoices" ? <InvoicesTab /> : null}
      {tab === "payments" ? <PaymentsTab /> : null}
      {tab === "structures" && manage ? <div className="flex justify-end"><Button onClick={() => setStructure("new")}>New fee structure</Button></div> : null}
      {tab === "structures" ? (
        <ResourceManager<FeeStructure> noun="fee structure" hooks={feeStructureHooks} canManage={manage} allowCreate={false} allowEdit={false} rowLabel={(s) => s.name} fields={[]}
          columns={[
            { key: "n", header: "Structure", cell: (s) => <span className="font-medium">{s.name}</span> }, { key: "c", header: "Class", cell: (s) => s.class_name }, { key: "se", header: "Session", cell: (s) => s.session_name },
            { key: "f", header: "Frequency", cell: (s) => s.frequency.toLowerCase().replace("_", " ") }, { key: "i", header: "Items", cell: (s) => s.items.map((i) => `${i.category_name} ${i.amount}`).join(", ") },
            { key: "t", header: "Total", className: "tabular-nums", cell: (s) => formatMoney(s.total, "PKR") },
            { key: "e", header: "", className: "text-right", cell: (s) => <Button variant="outline" size="sm" onClick={() => setStructure(s)}>Edit</Button> },
          ]} />
      ) : null}
      <StructureDialog target={structure} onClose={() => setStructure(null)} />
      {tab === "categories" ? (
        <ResourceManager<FeeCategory> noun="fee category" hooks={feeCategoryHooks} canManage={manage} rowLabel={(c) => c.name}
          fields={[{ name: "name", label: "Name", type: "text", required: true }, { name: "code", label: "Code", type: "text", required: true, placeholder: "TUI" }, { name: "is_recurring", label: "Recurring fee", type: "checkbox" }]}
          columns={[{ key: "n", header: "Category", cell: (c) => <span className="font-medium">{c.name}</span> }, { key: "c", header: "Code", cell: (c) => c.code }, { key: "r", header: "", cell: (c) => (c.is_recurring ? <Badge>Recurring</Badge> : null) }]} />
      ) : null}
    </>
  );
}
