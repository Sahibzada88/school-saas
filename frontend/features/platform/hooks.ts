"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { platformApi, type PlanInput, type RecordPaymentBody, type SubscriptionActionBody } from "./api";
import type {
  AuditListParams,
  LifecycleAction,
  PaymentListParams,
  SchoolListParams,
  SubscriptionAction,
  SubscriptionListParams,
} from "./types";

export const platformKeys = {
  all: ["platform"] as const,
  dashboard: () => ["platform", "dashboard"] as const,
  schools: (params: SchoolListParams) => ["platform", "schools", params] as const,
  school: (id: string) => ["platform", "school", id] as const,
  users: (id: string, page: number) => ["platform", "school", id, "users", page] as const,
  activity: (id: string, page: number) => ["platform", "school", id, "activity", page] as const,
  audit: (params: AuditListParams) => ["platform", "audit", params] as const,
  auditActions: () => ["platform", "audit-actions"] as const,
  plans: () => ["platform", "plans"] as const,
  subscriptions: (params: SubscriptionListParams) => ["platform", "subscriptions", params] as const,
  events: (id: string) => ["platform", "subscription-events", id] as const,
  payments: (params: PaymentListParams) => ["platform", "payments", params] as const,
  settings: () => ["platform", "settings"] as const,
};

export const usePlatformDashboard = () => useQuery({ queryKey: platformKeys.dashboard(), queryFn: platformApi.dashboard });

export const usePlatformSchools = (params: SchoolListParams) =>
  useQuery({ queryKey: platformKeys.schools(params), queryFn: () => platformApi.schools(params), placeholderData: keepPreviousData });

export const usePlatformSchool = (id: string) =>
  useQuery({ queryKey: platformKeys.school(id), queryFn: () => platformApi.school(id) });

export const useSchoolUsers = (id: string, page: number, enabled: boolean) =>
  useQuery({ queryKey: platformKeys.users(id, page), queryFn: () => platformApi.schoolUsers(id, page), enabled, placeholderData: keepPreviousData });

export const useSchoolActivity = (id: string, page: number, enabled: boolean) =>
  useQuery({ queryKey: platformKeys.activity(id, page), queryFn: () => platformApi.schoolActivity(id, page), enabled, placeholderData: keepPreviousData });

export const usePlatformAuditLogs = (params: AuditListParams) =>
  useQuery({ queryKey: platformKeys.audit(params), queryFn: () => platformApi.auditLogs(params), placeholderData: keepPreviousData });

export const useAuditActions = () =>
  useQuery({ queryKey: platformKeys.auditActions(), queryFn: platformApi.auditActions, staleTime: Infinity });

export const usePlans = () => useQuery({ queryKey: platformKeys.plans(), queryFn: platformApi.plans });

export const usePlatformSubscriptions = (params: SubscriptionListParams) =>
  useQuery({ queryKey: platformKeys.subscriptions(params), queryFn: () => platformApi.subscriptions(params), placeholderData: keepPreviousData });

export const useSubscriptionEvents = (id: string | undefined) =>
  useQuery({ queryKey: platformKeys.events(id ?? ""), queryFn: () => platformApi.subscriptionEvents(id as string), enabled: Boolean(id) });

export const usePlatformPayments = (params: PaymentListParams) =>
  useQuery({ queryKey: platformKeys.payments(params), queryFn: () => platformApi.payments(params), placeholderData: keepPreviousData });

export const usePlatformSettings = () => useQuery({ queryKey: platformKeys.settings(), queryFn: platformApi.settings });

/** Every billing/lifecycle mutation refreshes all platform data (counts, states and lists change together). */
function useInvalidatingMutation<TVars, TData>(fn: (vars: TVars) => Promise<TData>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => queryClient.invalidateQueries({ queryKey: platformKeys.all }) });
}

export const useSchoolTransition = (id: string) =>
  useInvalidatingMutation(({ action, reason }: { action: LifecycleAction; reason: string }) => platformApi.transition(id, action, reason));

export const useSubscriptionAction = (subscriptionId: string) =>
  useInvalidatingMutation(({ action, body }: { action: SubscriptionAction; body: SubscriptionActionBody }) =>
    platformApi.subscriptionAction(subscriptionId, action, body),
  );

export const useRecordPayment = () => useInvalidatingMutation((body: RecordPaymentBody) => platformApi.recordPayment(body));
export const useCreatePlan = () => useInvalidatingMutation((body: PlanInput) => platformApi.createPlan(body));
export const useUpdatePlan = () => useInvalidatingMutation(({ id, body }: { id: string; body: PlanInput }) => platformApi.updatePlan(id, body));
export const useUpdateSettings = () => useInvalidatingMutation((values: Record<string, string | number>) => platformApi.updateSettings(values));
export const useNotifySchool = (id: string) =>
  useInvalidatingMutation((body: { title: string; body: string; severity: string }) => platformApi.notify(id, body));
