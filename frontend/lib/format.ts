const date = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });
const dateTime = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso?: string | null): string {
  return iso ? date.format(new Date(iso)) : "—";
}

export function formatDateTime(iso?: string | null): string {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

/** "USER_CREATED" -> "User created" */
export function humanizeCode(code: string): string {
  const text = code.toLowerCase().replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatMoney(amount: string | number, currency: string): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  try {
    return new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}
