"use client";

import { Megaphone, Pin, Plus } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { Skeleton } from "@/components/common/Skeleton";
import { SpecFormDialog } from "@/components/common/SpecForm";
import { Badge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { announcementHooks, useMarkAnnouncementRead } from "@/features/school/resources";
import { useAuth } from "@/hooks/useAuth";
import { formatDateTime } from "@/lib/format";
import { serverMessage } from "@/lib/forms";
import { toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { Announcement, SchoolClass } from "@/types/school";

const AUDIENCES = [["ALL", "Everyone"], ["STAFF", "All staff"], ["TEACHERS", "Teachers"], ["PARENTS", "Parents"], ["STUDENTS", "Students"], ["CLASS", "One class"]] as const;

export default function AnnouncementsPage() {
  const { can, user } = useAuth();
  const isAdmin = user?.role === "SCHOOL_ADMIN";
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error, refetch } = announcementHooks.useList({ page });
  const create = announcementHooks.useCreate();
  const remove = announcementHooks.useRemove();
  const markRead = useMarkAnnouncementRead();
  const classes = useAllOptions<SchoolClass>("/school/classes", {}, can("announcements.create"));
  const [composing, setComposing] = useState(false);
  const [deleting, setDeleting] = useState<Announcement | null>(null);
  const audienceOptions = (isAdmin ? AUDIENCES : AUDIENCES.filter(([v]) => v === "CLASS")).map(([value, label]) => ({ value, label }));

  return (
    <>
      <PageHeader title="Announcements" description="The school notice board."
        actions={can("announcements.create") ? <Button onClick={() => setComposing(true)}><Plus className="size-4" /> New announcement</Button> : null} />
      {error ? <div className="rounded-lg border bg-card"><ErrorState error={error} onRetry={() => void refetch()} /></div> : isLoading ? <div className="space-y-3"><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /></div> : (data?.results.length ?? 0) === 0 ? (
        <div className="rounded-lg border bg-card"><EmptyState title="No announcements" description="Notices from your school will appear here." /></div>
      ) : (
        <ul className="space-y-3">
          {data?.results.map((a) => (
            <li key={a.id} className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="space-y-1">
                  <h2 className="flex items-center gap-2 font-medium">{a.is_pinned ? <Pin className="size-4 text-muted-foreground" aria-label="Pinned" /> : <Megaphone className="size-4 text-muted-foreground" aria-hidden />}{a.title}{!a.is_read ? <Badge tone="blue">New</Badge> : null}</h2>
                  <p className="text-xs text-muted-foreground">{formatDateTime(a.published_at)} · {a.created_by_name ?? "School"} · {a.audience === "CLASS" ? `Class ${a.class_name}` : AUDIENCES.find(([v]) => v === a.audience)?.[1]}</p>
                </div>
                <div className="flex gap-2">
                  {!a.is_read ? <Button variant="outline" size="sm" onClick={() => markRead.mutate(a.id)}>Mark as read</Button> : null}
                  {can("announcements.create") ? <Button variant="outline" size="sm" onClick={() => setDeleting(a)}>Delete</Button> : null}
                </div>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm">{a.body}</p>
            </li>
          ))}
        </ul>
      )}
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
      <SpecFormDialog open={composing} title="New announcement" submitLabel="Post" onClose={() => setComposing(false)} initial={{ audience: isAdmin ? "ALL" : "CLASS" }}
        fields={[
          { name: "title", label: "Title", type: "text", required: true, full: true }, { name: "body", label: "Message", type: "textarea", required: true },
          { name: "audience", label: "Audience", type: "select", required: true, options: audienceOptions },
          { name: "school_class", label: "Class (for 'One class')", type: "select", nullable: true, options: toOptions(classes.options, (c) => c.name) },
          { name: "expires_at", label: "Expires (optional)", type: "datetime", nullable: true }, { name: "is_pinned", label: "Pin to the top", type: "checkbox" },
        ]}
        onSubmit={(v) => create.mutateAsync(v)} />
      <ConfirmDialog open={deleting !== null} title="Delete announcement" description={deleting?.title} confirmLabel="Delete" destructive isPending={remove.isPending}
        error={remove.error ? serverMessage(remove.error) : null} onCancel={() => { setDeleting(null); remove.reset(); }} onConfirm={() => deleting && remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })} />
    </>
  );
}
