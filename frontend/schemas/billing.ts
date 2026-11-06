import { z } from "zod";

const money = z.string().trim().regex(/^\d+(\.\d{1,2})?$/, "Enter an amount like 5000 or 5000.50");
const optionalWholeNumber = z.string().trim().regex(/^\d*$/, "Whole number, or leave empty for unlimited");

export const planSchema = z.object({
  name: z.string().trim().min(2, "Name is required").max(100),
  slug: z.string().trim().min(2, "Slug is required").max(80).regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers and dashes only"),
  description: z.string().trim().max(1000),
  monthly_price: money,
  currency: z.string().trim().length(3, "Use a 3-letter code, e.g. PKR"),
  max_students: optionalWholeNumber,
  max_teachers: optionalWholeNumber,
  max_classes: optionalWholeNumber,
  features: z.string().max(2000),
  sort_order: z.string().trim().regex(/^\d{1,4}$/, "A number from 0 to 9999"),
  is_active: z.boolean(),
  is_public: z.boolean(),
});
export type PlanValues = z.infer<typeof planSchema>;

const METHODS = ["BANK_TRANSFER", "JAZZCASH", "EASYPAISA", "CASH", "OTHER"] as const;

export const paymentSchema = z.object({
  amount: money,
  currency: z.string().trim().refine((v) => v === "" || /^[A-Za-z]{3}$/.test(v), "Use a 3-letter code, or leave empty"),
  payment_method: z.enum(METHODS, { message: "Choose a payment method" }),
  transaction_reference: z.string().trim().max(100),
  payment_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Choose a date"),
  months: z
    .string()
    .trim()
    .regex(/^\d+$/, "Whole number of months")
    .refine((v) => Number(v) >= 1 && Number(v) <= 36, "Between 1 and 36 months"),
  plan: z.string(),
  notes: z.string().trim().max(1000),
});
export type PaymentValues = z.infer<typeof paymentSchema>;

export const notifySchema = z.object({
  title: z.string().trim().min(1, "Title is required").max(120),
  body: z.string().trim().max(1000),
  severity: z.enum(["INFO", "WARNING", "CRITICAL"]),
});
export type NotifyValues = z.infer<typeof notifySchema>;
