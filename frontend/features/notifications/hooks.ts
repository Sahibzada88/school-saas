"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { notificationsApi } from "./api";

const KEY = ["notifications"] as const;

/** Polls the cheap count endpoint (it also triggers request-time generation of due billing notices). */
export const useUnreadCount = (enabled = true) =>
  useQuery({
    queryKey: [...KEY, "unread-count"],
    queryFn: notificationsApi.unreadCount,
    enabled,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

export const useNotifications = (params: { page?: number; unread?: boolean }, enabled = true) =>
  useQuery({ queryKey: [...KEY, "list", params], queryFn: () => notificationsApi.list(params), enabled, placeholderData: keepPreviousData });

function useRefreshingMutation<TVars, TData>(fn: (vars: TVars) => Promise<TData>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }) });
}

export const useMarkRead = () => useRefreshingMutation((id: string) => notificationsApi.markRead(id));
export const useMarkAllRead = () => useRefreshingMutation(() => notificationsApi.markAllRead());
