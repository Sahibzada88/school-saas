"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { CreateUserValues, EditUserValues, ProfileValues } from "@/schemas/school";

import { schoolApi } from "./api";
import type { AuditParams, UserListParams } from "./types";

export const schoolKeys = {
  all: ["school"] as const,
  dashboard: () => ["school", "dashboard"] as const,
  profile: () => ["school", "profile"] as const,
  users: (params: UserListParams) => ["school", "users", params] as const,
  audit: (params: AuditParams) => ["school", "audit", params] as const,
};

export const useSchoolDashboard = () => useQuery({ queryKey: schoolKeys.dashboard(), queryFn: schoolApi.dashboard });
export const useSchoolProfile = () => useQuery({ queryKey: schoolKeys.profile(), queryFn: schoolApi.profile });

export const useSchoolUsersList = (params: UserListParams) =>
  useQuery({ queryKey: schoolKeys.users(params), queryFn: () => schoolApi.users(params), placeholderData: keepPreviousData });

export const useSchoolAudit = (params: AuditParams) =>
  useQuery({ queryKey: schoolKeys.audit(params), queryFn: () => schoolApi.auditLogs(params), placeholderData: keepPreviousData });

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: Partial<ProfileValues> & { logo?: string | null }) => schoolApi.updateProfile(values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: schoolKeys.all }),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: CreateUserValues) => schoolApi.createUser(values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: schoolKeys.all }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, values }: { id: string; values: Partial<EditUserValues> & { is_active?: boolean } }) =>
      schoolApi.updateUser(id, values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: schoolKeys.all }),
  });
}
