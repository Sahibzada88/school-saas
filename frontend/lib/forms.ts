import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError } from "@/lib/api-client";

function firstMessage(value: unknown): string | null {
  if (Array.isArray(value) && value.length > 0) return String(value[0]);
  if (typeof value === "string") return value;
  return null;
}

/** Maps DRF field errors onto react-hook-form fields. Returns a form-level message when something is left over. */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly string[],
): string | null {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";

  let handled = false;
  for (const [key, value] of Object.entries(error.errors ?? {})) {
    const message = firstMessage(value);
    if (message && fields.includes(key)) {
      setError(key as Path<T>, { type: "server", message });
      handled = true;
    }
  }
  if (handled) return null;

  const nonField = firstMessage((error.errors ?? {})["non_field_errors"]);
  return nonField ?? error.message;
}

/** One readable message from any API failure (first field error if present, else the summary message). */
export function serverMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  for (const value of Object.values(error.errors ?? {})) {
    const message = firstMessage(value);
    if (message) return message;
  }
  return error.message;
}
