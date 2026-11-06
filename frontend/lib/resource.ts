"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type QueryParams } from "@/lib/api-client";
import type { Paginated } from "@/types/api";

/** Every school-data query key starts with this root, so any mutation can refresh dependent screens safely. */
export const DATA_ROOT = ["school-data"] as const;

export function createResource<T>(basePath: string) {
  return {
    list: (params: QueryParams = {}) => apiFetch<Paginated<T>>(`${basePath}/`, { query: params }),
    get: (id: string) => apiFetch<T>(`${basePath}/${id}/`),
    create: (body: unknown) => apiFetch<T>(`${basePath}/`, { method: "POST", body }),
    update: (id: string, body: unknown) => apiFetch<T>(`${basePath}/${id}/`, { method: "PATCH", body }),
    remove: (id: string) => apiFetch<null>(`${basePath}/${id}/`, { method: "DELETE" }),
  };
}
export type Resource<T> = ReturnType<typeof createResource<T>>;

export function createResourceHooks<T>(key: string, resource: Resource<T>) {
  return {
    useList: (params: QueryParams = {}, enabled = true) =>
      useQuery({ queryKey: [...DATA_ROOT, key, "list", params], queryFn: () => resource.list(params), enabled, placeholderData: keepPreviousData }),
    useGet: (id: string | undefined) =>
      useQuery({ queryKey: [...DATA_ROOT, key, "item", id], queryFn: () => resource.get(id as string), enabled: Boolean(id) }),
    useCreate: () => {
      const queryClient = useQueryClient();
      return useMutation({ mutationFn: (body: unknown) => resource.create(body), onSuccess: () => queryClient.invalidateQueries({ queryKey: DATA_ROOT }) });
    },
    useUpdate: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: ({ id, body }: { id: string; body: unknown }) => resource.update(id, body),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: DATA_ROOT }),
      });
    },
    useRemove: () => {
      const queryClient = useQueryClient();
      return useMutation({ mutationFn: (id: string) => resource.remove(id), onSuccess: () => queryClient.invalidateQueries({ queryKey: DATA_ROOT }) });
    },
  };
}

/** Whole (<= 100) option lists for <select>s, e.g. all sections of the school. */
export function useAllOptions<T>(path: string, query: QueryParams = {}, enabled = true) {
  const result = useQuery({
    queryKey: [...DATA_ROOT, "options", path, query],
    queryFn: () => apiFetch<Paginated<T>>(`${path}/`, { query: { page_size: 100, ...query } }),
    enabled,
    staleTime: 60_000,
  });
  return { ...result, options: result.data?.results ?? [] };
}

/** Generic one-off mutation that refreshes all school data afterwards (custom actions: publish, void, ...). */
export function useDataMutation<TVars, TData>(fn: (vars: TVars) => Promise<TData>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => queryClient.invalidateQueries({ queryKey: DATA_ROOT }) });
}

export function useDataQuery<T>(key: unknown[], fn: () => Promise<T>, enabled = true) {
  return useQuery({ queryKey: [...DATA_ROOT, ...key], queryFn: fn, enabled });
}
