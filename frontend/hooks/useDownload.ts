"use client";

import { useCallback, useState } from "react";

import { ApiError, type QueryParams } from "@/lib/api-client";
import { downloadFile } from "@/lib/download";

export function useDownload() {
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = useCallback(async (path: string, fallbackName: string, query?: QueryParams) => {
    setIsDownloading(true);
    setError(null);
    try {
      await downloadFile(path, fallbackName, query);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download failed");
    } finally {
      setIsDownloading(false);
    }
  }, []);

  return { download, isDownloading, error };
}
