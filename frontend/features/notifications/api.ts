import { apiFetch } from "@/lib/api-client";
import type { Paginated } from "@/types/api";

import type { AppNotification } from "./types";

export const notificationsApi = {
  list: (params: { page?: number; unread?: boolean }) =>
    apiFetch<Paginated<AppNotification>>("/notifications/", { query: { page: params.page, unread: params.unread ? "true" : undefined } }),
  unreadCount: () => apiFetch<{ count: number }>("/notifications/unread-count/"),
  markRead: (id: string) => apiFetch<AppNotification>(`/notifications/${id}/read/`, { method: "POST" }),
  markAllRead: () => apiFetch<{ updated: number }>("/notifications/mark-all-read/", { method: "POST" }),
};
