import { API_URL } from "@/lib/env";
import type { ApiEnvelope } from "@/types/api";

export class ApiError extends Error {
  status: number;
  code?: string;
  errors: Record<string, unknown>;
  requestId?: string;

  constructor(
    message: string,
    status: number,
    code?: string,
    errors: Record<string, unknown> = {},
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.errors = errors;
    this.requestId = requestId;
  }
}

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions extends Omit<RequestInit, "body"> {
  query?: QueryParams;
  body?: unknown;
  /** Do not try /auth/refresh/ and retry when the API answers 401. */
  skipAuthRefresh?: boolean;
}

type RawOptions = Omit<RequestOptions, "skipAuthRefresh">;

const CSRF_COOKIE = "csrf_token";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
/** Auth endpoints that must never trigger a refresh-and-retry. */
const NO_REFRESH_PREFIXES = [
  "/auth/login/",
  "/auth/register/",
  "/auth/refresh/",
  "/auth/logout/",
  "/auth/csrf/",
  "/auth/password-reset/",
];

/** `path` is relative to /api/v1 and should end with "/" (e.g. "/health/"). */
export function buildUrl(path: string, query?: QueryParams): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return `${API_URL}${normalized}${qs ? `?${qs}` : ""}`;
}

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const entry = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : null;
}

async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;

  let response: Response;
  try {
    response = await fetch(buildUrl("/auth/csrf/"), {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("Network error. Please check your connection and try again.", 0, "network_error");
  }
  const payload = (await response.json().catch(() => null)) as ApiEnvelope<{ csrf_token: string }> | null;
  if (!response.ok || !payload || payload.success !== true) {
    throw new ApiError("Could not start a secure session. Please reload the page.", response.status, "csrf_unavailable");
  }
  return payload.data.csrf_token;
}

/** One request, no retry. Unwraps the {success,data,message} envelope or throws ApiError. */
async function rawRequest<T>(path: string, options: RawOptions = {}): Promise<T> {
  const { query, body, headers, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();
  const csrfHeaders: Record<string, string> = UNSAFE_METHODS.has(method)
    ? { "X-CSRF-Token": await ensureCsrfToken() }
    : {};

  // FormData (CSV uploads): let the browser set the multipart Content-Type with its boundary.
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      credentials: "same-origin",
      ...rest,
      headers: {
        Accept: "application/json",
        ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}),
        ...csrfHeaders,
        ...headers,
      },
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Network error. Please check your connection and try again.", 0, "network_error");
  }

  if (response.status === 204) return undefined as T;

  let payload: ApiEnvelope<T> | null = null;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    payload = null;
  }

  if (!response.ok || !payload || payload.success !== true) {
    const failure = payload && payload.success === false ? payload : null;
    throw new ApiError(
      failure?.message ?? (response.statusText || "Request failed"),
      response.status,
      failure?.code,
      failure?.errors,
      failure?.request_id,
    );
  }

  return payload.data;
}

export type RefreshOutcome = "ok" | "rotated" | "failed";
let refreshInFlight: Promise<RefreshOutcome> | null = null;

/** Single-flight: concurrent 401s share one refresh call. "rotated" means another tab refreshed first,
 *  so fresh cookies already exist and the original request can simply be retried. */
export function refreshSession(): Promise<RefreshOutcome> {
  if (!refreshInFlight) {
    refreshInFlight = rawRequest("/auth/refresh/", { method: "POST" })
      .then((): RefreshOutcome => "ok")
      .catch((error: unknown): RefreshOutcome =>
        error instanceof ApiError && error.code === "token_rotated" ? "rotated" : "failed",
      )
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

/** Browser-side JSON fetch with CSRF header handling and a one-time refresh-and-retry on 401. */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuthRefresh, ...rawOptions } = options;
  try {
    return await rawRequest<T>(path, rawOptions);
  } catch (error) {
    const canRefresh =
      !skipAuthRefresh &&
      error instanceof ApiError &&
      error.status === 401 &&
      !NO_REFRESH_PREFIXES.some((prefix) => path.startsWith(prefix));
    if (!canRefresh) throw error;
    if ((await refreshSession()) === "failed") throw error;
    return rawRequest<T>(path, rawOptions);
  }
}
