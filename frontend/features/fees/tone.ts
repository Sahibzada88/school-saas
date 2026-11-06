import type { Invoice } from "@/types/school";

export const invoiceTone = (i: Pick<Invoice, "status" | "is_overdue">) =>
  i.status === "PAID" ? "green" : i.status === "VOID" ? "gray" : i.is_overdue ? "red" : "amber";
