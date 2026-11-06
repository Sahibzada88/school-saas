import { AlertTriangle, Info, OctagonAlert } from "lucide-react";

import type { AppNotification } from "@/features/notifications/types";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const SEVERITY = {
  INFO: { Icon: Info, className: "text-blue-600" },
  WARNING: { Icon: AlertTriangle, className: "text-amber-600" },
  CRITICAL: { Icon: OctagonAlert, className: "text-red-600" },
} as const;

export function NotificationItem({ notification, onOpen }: { notification: AppNotification; onOpen?: () => void }) {
  const { Icon, className } = SEVERITY[notification.severity];
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className={cn("flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50", !notification.is_read && "bg-primary/5")}
      >
        <Icon className={cn("mt-0.5 size-4 shrink-0", className)} aria-hidden />
        <span className="min-w-0 flex-1 space-y-0.5">
          <span className="flex items-center gap-2 text-sm font-medium">
            <span className="truncate">{notification.title}</span>
            {!notification.is_read ? <span className="size-2 shrink-0 rounded-full bg-primary" aria-label="Unread" /> : null}
          </span>
          {notification.body ? <span className="block text-sm text-muted-foreground">{notification.body}</span> : null}
          <span className="block text-xs text-muted-foreground">{formatDateTime(notification.created_at)}</span>
        </span>
      </button>
    </li>
  );
}
