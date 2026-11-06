"use client";

import { Loader2, Upload } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { DownloadButton } from "@/components/common/DownloadButton";
import { FormAlert } from "@/components/common/FormAlert";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api-client";
import { serverMessage } from "@/lib/forms";
import { DATA_ROOT } from "@/lib/resource";
import type { ImportReport } from "@/types/school";

function Importer({ endpoint, templatePath, templateName, columns, noun, onClose }: {
  endpoint: string; templatePath: string; templateName: string; columns: string; noun: string; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("dry_run", dryRun ? "true" : "false");
    try {
      const result = await apiFetch<ImportReport>(endpoint, { method: "POST", body: form });
      setReport(result);
      if (!dryRun && result.ok) await queryClient.invalidateQueries({ queryKey: DATA_ROOT });
    } catch (e) {
      setError(serverMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const imported = report && !report.dry_run && report.ok;
  return (
    <div className="space-y-4">
      <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>Download the template and fill it in Excel (save as <strong>CSV UTF-8</strong>). Max 500 rows per file.</li>
        <li>Choose the file and press <strong>Check file</strong>. Nothing is saved yet; every problem is listed by row.</li>
        <li>When the check is clean, press <strong>Import</strong>. All rows are imported together or none.</li>
      </ol>
      <p className="text-xs text-muted-foreground">Columns: {columns}</p>
      <DownloadButton path={templatePath} filename={templateName}>Download template</DownloadButton>
      <div>
        <input type="file" accept=".csv,text/csv" aria-label="CSV file" className="text-sm" disabled={busy}
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); setError(null); }} />
      </div>
      {error ? <FormAlert>{error}</FormAlert> : null}
      {report && !report.ok ? (
        <div className="space-y-2">
          <FormAlert>{report.errors.length} row(s) have problems. Fix the file and check again.</FormAlert>
          <ul className="max-h-56 space-y-1 overflow-y-auto rounded-md border p-2 text-sm">
            {report.errors.map((e) => <li key={e.row}><strong>Row {e.row}:</strong> {e.errors.join("; ")}</li>)}
          </ul>
        </div>
      ) : null}
      {report?.ok && report.dry_run ? <FormAlert variant="success">The file is valid: {report.total} {noun}(s) ready to import.</FormAlert> : null}
      {imported ? <FormAlert variant="success">{report.created} {noun}(s) imported.</FormAlert> : null}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={busy}>{imported ? "Close" : "Cancel"}</Button>
        {!imported ? <Button variant="outline" onClick={() => void send(true)} disabled={!file || busy}>{busy ? <Loader2 className="size-4 animate-spin" /> : null} Check file</Button> : null}
        {report?.ok && report.dry_run ? <Button onClick={() => void send(false)} disabled={busy}><Upload className="size-4" /> Import {report.total}</Button> : null}
      </div>
    </div>
  );
}

export function ImportDialog({ open, onClose, title, ...rest }: {
  open: boolean; onClose: () => void; title: string; endpoint: string; templatePath: string; templateName: string; columns: string; noun: string;
}) {
  return (
    <Modal open={open} title={title} onClose={onClose} wide>
      <Importer {...rest} onClose={onClose} />
    </Modal>
  );
}
