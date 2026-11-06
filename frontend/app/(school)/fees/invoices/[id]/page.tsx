"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DataTable, type Column } from "@/components/common/DataTable";
import { DownloadButton } from "@/components/common/DownloadButton";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Skeleton } from "@/components/common/Skeleton";
import { SpecFormDialog } from "@/components/common/SpecForm";
import { Badge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { invoiceTone } from "@/features/fees/tone";
import { useInvoiceAction, useInvoiceDetail, useReversePayment } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { formatDate, formatMoney } from "@/lib/format";
import { today } from "@/lib/options";
import { whatsappLink } from "@/lib/whatsapp";
import type { InvoiceDetail } from "@/types/school";

type Dialog = "payment" | "discount" | "fine" | "void" | { reverse: InvoiceDetail["payments"][number] } | null;
const money = (v: string) => formatMoney(v, "PKR");

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const { data: invoice, isLoading, error, refetch } = useInvoiceDetail(id);
  const act = useInvoiceAction(id);
  const reverse = useReversePayment();
  const [dialog, setDialog] = useState<Dialog>(null);
  if (error) return <div className="rounded-lg border bg-card"><ErrorState error={error} onRetry={() => void refetch()} /></div>;
  if (isLoading || !invoice) return <Skeleton className="h-96 w-full" />;
  const open = invoice.status !== "VOID";
  const whatsapp = invoice.guardian && open && Number(invoice.balance) > 0
    ? whatsappLink(invoice.guardian.phone, `Assalam o Alaikum ${invoice.guardian.name}, ${invoice.student.full_name} ki fee (invoice ${invoice.invoice_number}, ${invoice.period_label}) ka balance ${money(invoice.balance)} hai, last date ${formatDate(invoice.due_date)}. Shukriya.`)
    : null;
  const close = () => setDialog(null);

  const paymentColumns: Column<InvoiceDetail["payments"][number]>[] = [
    { key: "r", header: "Receipt", cell: (p) => <span className="font-medium">{p.receipt_number}</span> }, { key: "d", header: "Date", cell: (p) => formatDate(p.paid_on) },
    { key: "a", header: "Amount", className: "tabular-nums", cell: (p) => money(p.amount) }, { key: "m", header: "Method", cell: (p) => `${p.method.toLowerCase()}${p.reference ? ` (${p.reference})` : ""}` },
    { key: "s", header: "Status", cell: (p) => <Badge tone={p.status === "POSTED" ? "green" : "gray"}>{p.status.toLowerCase()}</Badge> },
    { key: "x", header: "", className: "text-right", cell: (p) => (
      <div className="flex justify-end gap-2">
        <DownloadButton path={`/school/fees/payments/${p.id}/receipt/pdf/`} filename={`receipt-${p.receipt_number}.pdf`}>Receipt</DownloadButton>
        {can("fees.reverse") && p.status === "POSTED" ? <Button variant="outline" size="sm" onClick={() => setDialog({ reverse: p })}>Reverse</Button> : null}
      </div>) },
  ];

  return (
    <>
      <Link href="/fees" className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:underline"><ArrowLeft className="size-4" /> All invoices</Link>
      <PageHeader
        title={<span className="flex flex-wrap items-center gap-3">{invoice.invoice_number} <Badge tone={invoiceTone(invoice)}>{invoice.is_overdue ? "Overdue" : invoice.status.replace("_", " ").toLowerCase()}</Badge></span>}
        description={`${invoice.student.full_name} (${invoice.student.student_number}) · ${invoice.period_label} · due ${formatDate(invoice.due_date)}`}
        actions={
          <>
            <DownloadButton path={`/school/fees/invoices/${id}/pdf/`} filename={`invoice-${invoice.invoice_number}.pdf`}>PDF</DownloadButton>
            {whatsapp ? <Button variant="outline" size="sm" onClick={() => window.open(whatsapp, "_blank", "noopener,noreferrer")}>WhatsApp reminder</Button> : null}
            {open && can("fees.payments.record") && Number(invoice.balance) > 0 ? <Button onClick={() => setDialog("payment")}>Record payment</Button> : null}
            {open && can("fees.manage") ? <Button variant="outline" onClick={() => setDialog("discount")}>Add discount</Button> : null}
            {open && can("fees.manage") ? <Button variant="outline" onClick={() => setDialog("fine")}>Add fine</Button> : null}
            {open && can("fees.manage") ? <Button variant="outline" onClick={() => setDialog("void")}>Void</Button> : null}
          </>
        }
      />
      {invoice.status === "VOID" ? <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">Void: {invoice.void_reason}</p> : null}
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="space-y-2 rounded-lg border bg-card p-4 shadow-sm lg:col-span-2">
          <h2 className="font-medium">Items</h2>
          <table className="w-full text-sm"><tbody className="divide-y">
            {invoice.items.map((i, n) => <tr key={`i${n}`}><td className="py-1.5">{i.description}</td><td className="py-1.5 text-right tabular-nums">{money(i.amount)}</td></tr>)}
            {invoice.discounts.map((d, n) => <tr key={`d${n}`} className="text-green-700 dark:text-green-400"><td className="py-1.5">Discount: {d.reason}{d.kind === "PERCENT" ? ` (${d.value}%)` : ""}</td><td className="py-1.5 text-right tabular-nums">−{money(d.amount)}</td></tr>)}
            {invoice.fines.map((f, n) => <tr key={`f${n}`} className="text-red-700 dark:text-red-400"><td className="py-1.5">Fine: {f.reason}</td><td className="py-1.5 text-right tabular-nums">{money(f.amount)}</td></tr>)}
          </tbody></table>
        </section>
        <dl className="space-y-2 rounded-lg border bg-card p-4 text-sm shadow-sm">
          <div className="flex justify-between"><dt className="text-muted-foreground">Subtotal</dt><dd className="tabular-nums">{money(invoice.subtotal)}</dd></div>
          <div className="flex justify-between"><dt className="text-muted-foreground">Discounts</dt><dd className="tabular-nums">−{money(invoice.discount_total)}</dd></div>
          <div className="flex justify-between"><dt className="text-muted-foreground">Fines</dt><dd className="tabular-nums">{money(invoice.fine_total)}</dd></div>
          <div className="flex justify-between border-t pt-2 font-medium"><dt>Total</dt><dd className="tabular-nums">{money(invoice.total)}</dd></div>
          <div className="flex justify-between"><dt className="text-muted-foreground">Paid</dt><dd className="tabular-nums">{money(invoice.paid_total)}</dd></div>
          <div className="flex justify-between text-base font-semibold"><dt>Balance</dt><dd className="tabular-nums">{money(invoice.balance)}</dd></div>
        </dl>
      </div>
      <section className="space-y-2"><h2 className="font-medium">Payments</h2><DataTable columns={paymentColumns} rows={invoice.payments} rowKey={(p) => p.id} isLoading={false} emptyTitle="No payments yet" /></section>

      <SpecFormDialog open={dialog === "payment"} title="Record payment" description={`Outstanding balance: ${money(invoice.balance)}`} submitLabel="Record payment" onClose={close} initial={{ paid_on: today(), method: "CASH", amount: invoice.balance }}
        fields={[
          { name: "amount", label: "Amount", type: "number", required: true, step: "0.01", min: 0.01 }, { name: "paid_on", label: "Date", type: "date", required: true },
          { name: "method", label: "Method", type: "select", required: true, options: ["CASH", "BANK", "ONLINE", "CHEQUE", "OTHER"].map((m) => ({ value: m, label: m.toLowerCase() })) }, { name: "reference", label: "Reference", type: "text" },
        ]} onSubmit={(v) => act.mutateAsync({ action: "payments", body: v })} />
      <SpecFormDialog open={dialog === "discount"} title="Add discount" submitLabel="Apply" onClose={close} initial={{ kind: "PERCENT" }}
        fields={[
          { name: "kind", label: "Type", type: "select", required: true, options: [{ value: "PERCENT", label: "Percent of subtotal" }, { value: "FIXED", label: "Fixed amount" }] },
          { name: "value", label: "Value", type: "number", required: true, step: "0.01" }, { name: "reason", label: "Reason", type: "text", required: true, full: true },
        ]} onSubmit={(v) => act.mutateAsync({ action: "discounts", body: v })} />
      <SpecFormDialog open={dialog === "fine"} title="Add fine" submitLabel="Add fine" onClose={close}
        fields={[{ name: "amount", label: "Amount", type: "number", required: true, step: "0.01" }, { name: "reason", label: "Reason", type: "text", required: true }]} onSubmit={(v) => act.mutateAsync({ action: "fines", body: v })} />
      <SpecFormDialog open={dialog === "void"} title="Void invoice" description="Only invoices without posted payments can be voided. The student can be re-invoiced for the period afterwards." submitLabel="Void invoice" onClose={close}
        fields={[{ name: "reason", label: "Reason", type: "textarea", required: true }]} onSubmit={(v) => act.mutateAsync({ action: "void", body: v })} />
      <SpecFormDialog open={typeof dialog === "object" && dialog !== null} title="Reverse payment" description="The amount returns to the invoice balance. This cannot be undone." submitLabel="Reverse payment" onClose={close}
        fields={[{ name: "reason", label: "Reason", type: "textarea", required: true }]} onSubmit={(v) => reverse.mutateAsync({ id: (dialog as { reverse: { id: string } }).reverse.id, reason: String(v.reason) })} />
    </>
  );
}
