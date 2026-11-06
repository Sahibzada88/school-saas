import { ApiError, buildUrl, refreshSession, type QueryParams } from "@/lib/api-client";
import type { ApiFailure } from "@/types/api";

function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return match ? decodeURIComponent(match[1]) : fallback;
}

async function fetchOnce(path: string, query?: QueryParams): Promise<Response> {
  try {
    return await fetch(buildUrl(path, query), { credentials: "same-origin" });
  } catch {
    throw new ApiError("Network error. Please check your connection and try again.", 0, "network_error");
  }
}

/** Authenticated download (PDF/CSV). Cookies travel with the request; errors surface as ApiError. */
export async function downloadFile(path: string, fallbackName: string, query?: QueryParams): Promise<void> {
  let response = await fetchOnce(path, query);
  if (response.status === 401 && (await refreshSession()) !== "failed") {
    response = await fetchOnce(path, query);
  }

  if (!response.ok) {
    let failure: Partial<ApiFailure> = {};
    try {
      failure = (await response.json()) as ApiFailure;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(
      failure.message ?? "Download failed",
      response.status,
      failure.code,
      failure.errors,
      failure.request_id,
    );
  }

  const blob = await response.blob();
  const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), fallbackName);
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}
