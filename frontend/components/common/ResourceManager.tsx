"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { DataTable, type Column } from "@/components/common/DataTable";
import { Pagination } from "@/components/common/Pagination";
import { SpecFormDialog, type FieldSpec, type FormValues } from "@/components/common/SpecForm";
import { Button } from "@/components/ui/button";
import type { QueryParams } from "@/lib/api-client";
import { serverMessage } from "@/lib/forms";
import type { createResourceHooks } from "@/lib/resource";

type Hooks<T> = ReturnType<typeof createResourceHooks<T>>;

/** List + create + edit + delete for one resource, driven by field specs. Keeps simple CRUD screens tiny. */
export function ResourceManager<T extends { id: string }>({
  noun, hooks, columns, fields, canManage, params, extraBody, initialFor, createInitial, allowCreate = true, allowEdit = true, allowDelete = true, wide, emptyDescription, rowLabel, imageUrlsFor,
}: {
  noun: string;
  hooks: Hooks<T>;
  columns: Column<T>[];
  fields: FieldSpec[];
  canManage: boolean;
  params?: QueryParams;
  /** Fields sent with every create/update but not edited by the user (e.g. the parent exam id). */
  extraBody?: Record<string, unknown>;
  initialFor?: (row: T) => FormValues;
  createInitial?: FormValues;
  allowCreate?: boolean;
  allowEdit?: boolean;
  allowDelete?: boolean;
  wide?: boolean;
  emptyDescription?: string;
  rowLabel?: (row: T) => string;
  imageUrlsFor?: (row: T) => Record<string, string | null | undefined>;
}) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error, refetch } = hooks.useList({ ...params, page });
  const create = hooks.useCreate();
  const update = hooks.useUpdate();
  const remove = hooks.useRemove();
  const [editing, setEditing] = useState<T | "new" | null>(null);
  const [deleting, setDeleting] = useState<T | null>(null);

  const all: Column<T>[] = [
    ...columns,
    ...(canManage && (allowEdit || allowDelete)
      ? [{
          key: "__actions", header: "", className: "text-right",
          cell: (row: T) => (
            <div className="flex justify-end gap-2">
              {allowEdit ? <Button variant="outline" size="sm" onClick={() => setEditing(row)}>Edit</Button> : null}
              {allowDelete ? <Button variant="outline" size="sm" onClick={() => setDeleting(row)}>Delete</Button> : null}
            </div>
          ),
        }]
      : []),
  ];
  const editingRow = editing && editing !== "new" ? editing : null;

  return (
    <div className="space-y-3">
      {canManage && allowCreate ? <div className="flex justify-end"><Button onClick={() => setEditing("new")}><Plus className="size-4" /> Add {noun}</Button></div> : null}
      <DataTable columns={all} rows={data?.results} rowKey={(r) => r.id} isLoading={isLoading} error={error} onRetry={() => void refetch()}
        emptyTitle={`No ${noun}s yet`} emptyDescription={emptyDescription ?? (canManage ? `Add a ${noun} to get started.` : undefined)} />
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
      <SpecFormDialog
        wide={wide} open={editing !== null} title={editingRow ? `Edit ${noun}` : `Add ${noun}`} fields={fields}
        initial={editingRow ? (initialFor ? initialFor(editingRow) : (editingRow as unknown as FormValues)) : createInitial}
        imageUrls={editingRow && imageUrlsFor ? imageUrlsFor(editingRow) : undefined}
        onClose={() => setEditing(null)}
        onSubmit={(values) => (editingRow ? update.mutateAsync({ id: editingRow.id, body: { ...values, ...extraBody } }) : create.mutateAsync({ ...values, ...extraBody }))}
      />
      <ConfirmDialog open={deleting !== null} title={`Delete ${noun}`} description={deleting && rowLabel ? `${rowLabel(deleting)} will be removed.` : "This cannot be undone."}
        confirmLabel="Delete" destructive isPending={remove.isPending} error={remove.error ? serverMessage(remove.error) : null}
        onCancel={() => { setDeleting(null); remove.reset(); }} onConfirm={() => deleting && remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })} />
    </div>
  );
}
