"use client";

import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { Skeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
import { NotificationItem } from "@/features/notifications/components/NotificationItem";
import { useMarkAllRead, useMarkRead, useNotifications } from "@/features/notifications/hooks";

export default function NotificationsPage() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const { data, isLoading, isFetching, error, refetch } = useNotifications({ page, unread: unreadOnly });
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  return (
    <>
      <PageHeader
        title="Notifications"
        description="Billing, account and platform messages for your school."
        actions={
          <>
            <Button variant="outline" onClick={() => { setUnreadOnly((v) => !v); setPage(1); }}>
              {unreadOnly ? "Show all" : "Unread only"}
            </Button>
            <Button variant="outline" disabled={markAll.isPending} onClick={() => markAll.mutate()}>
              Mark all read
            </Button>
          </>
        }
      />
      <div className="overflow-hidden rounded-lg border bg-card shadow-sm">
        {error ? (
          <ErrorState error={error} onRetry={() => void refetch()} />
        ) : isLoading ? (
          <div className="space-y-3 p-4">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-5 w-3/5" />
          </div>
        ) : (data?.results.length ?? 0) === 0 ? (
          <EmptyState title={unreadOnly ? "No unread notifications" : "No notifications yet"} description="Important messages will appear here." />
        ) : (
          <ul className="divide-y">
            {data?.results.map((n) => (
              <NotificationItem key={n.id} notification={n} onOpen={() => { if (!n.is_read) markRead.mutate(n.id); }} />
            ))}
          </ul>
        )}
      </div>
      <Pagination pagination={data?.pagination} onPageChange={setPage} disabled={isFetching} />
    </>
  );
}
