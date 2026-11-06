"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Skeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
import { NotificationItem } from "@/features/notifications/components/NotificationItem";
import { useMarkAllRead, useMarkRead, useNotifications, useUnreadCount } from "@/features/notifications/hooks";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const count = useUnreadCount();
  const list = useNotifications({}, open);
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();
  const unread = count.data?.count ?? 0;

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="icon"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell className="size-4" />
        {unread > 0 ? (
          <span className="absolute -right-1 -top-1 flex min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold leading-4 text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </Button>

      {open ? (
        <>
          <button type="button" aria-label="Close notifications" className="fixed inset-0 z-30 cursor-default" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-lg border bg-card text-card-foreground shadow-lg">
            <div className="flex items-center justify-between border-b px-4 py-2">
              <span className="text-sm font-medium">Notifications</span>
              <Button variant="ghost" size="sm" disabled={unread === 0 || markAll.isPending} onClick={() => markAll.mutate()}>
                Mark all read
              </Button>
            </div>
            <ul className="max-h-96 divide-y overflow-y-auto">
              {list.isLoading ? (
                <li className="space-y-2 p-4">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                </li>
              ) : list.error ? (
                <li className="p-4 text-sm text-muted-foreground">Could not load notifications.</li>
              ) : (list.data?.results.length ?? 0) === 0 ? (
                <li className="p-6 text-center text-sm text-muted-foreground">You are all caught up.</li>
              ) : (
                list.data?.results.slice(0, 8).map((notification) => (
                  <NotificationItem
                    key={notification.id}
                    notification={notification}
                    onOpen={() => {
                      if (!notification.is_read) markRead.mutate(notification.id);
                    }}
                  />
                ))
              )}
            </ul>
            <div className="border-t px-4 py-2 text-center">
              <Link href="/notifications" onClick={() => setOpen(false)} className="text-sm underline underline-offset-4">
                View all
              </Link>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
