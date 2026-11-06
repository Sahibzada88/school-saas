import { readCookie } from "@/lib/api-client";

/** True while the backend's non-secret "session probably exists" cookie is present. */
export function hasSessionHint(): boolean {
  return Boolean(readCookie("sid_hint"));
}
