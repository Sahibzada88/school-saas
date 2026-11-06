"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import { ApiError } from "@/lib/api-client";
import { hasSessionHint } from "@/lib/session";
import type { LoginValues, RegisterPayload } from "@/schemas/auth";
import { authService } from "@/services/auth";
import type { AuthSchool, AuthUser, Me } from "@/types/auth";

export const ME_QUERY_KEY = ["auth", "me"] as const;

interface AuthContextValue {
  me: Me | null;
  user: AuthUser | null;
  school: AuthSchool | null;
  permissions: ReadonlySet<string>;
  isLoading: boolean;
  isError: boolean;
  can: (permission: string) => boolean;
  login: (values: LoginValues) => Promise<Me>;
  register: (values: RegisterPayload) => Promise<Me>;
  logout: () => Promise<void>;
  changePassword: (values: { current_password: string; new_password: string }) => Promise<Me>;
  reload: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const EMPTY_PERMISSIONS: ReadonlySet<string> = new Set();

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const router = useRouter();

  const query = useQuery<Me | null>({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      if (!hasSessionHint()) return null; // nothing to restore: skip a pointless 401 round trip
      try {
        return await authService.getMe();
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });

  const me = query.data ?? null;

  const startSession = useCallback(
    (next: Me) => {
      queryClient.clear(); // never leak the previous user's cached data
      queryClient.setQueryData(ME_QUERY_KEY, next);
      return next;
    },
    [queryClient],
  );

  const login = useCallback((values: LoginValues) => authService.login(values).then(startSession), [startSession]);
  const register = useCallback(
    (values: RegisterPayload) => authService.register(values).then(startSession),
    [startSession],
  );
  const changePassword = useCallback(
    (values: { current_password: string; new_password: string }) =>
      authService.changePassword(values).then((next) => {
        queryClient.setQueryData(ME_QUERY_KEY, next);
        return next;
      }),
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      queryClient.clear();
      queryClient.setQueryData(ME_QUERY_KEY, null);
      router.replace("/login");
    }
  }, [queryClient, router]);

  const reload = useCallback(() => {
    void query.refetch();
  }, [query]);

  const permissions = useMemo<ReadonlySet<string>>(
    () => (me ? new Set(me.permissions) : EMPTY_PERMISSIONS),
    [me],
  );
  const can = useCallback((permission: string) => permissions.has(permission), [permissions]);

  const value = useMemo<AuthContextValue>(
    () => ({
      me,
      user: me?.user ?? null,
      school: me?.school ?? null,
      permissions,
      isLoading: query.isLoading,
      isError: query.isError,
      can,
      login,
      register,
      logout,
      changePassword,
      reload,
    }),
    [me, permissions, query.isLoading, query.isError, can, login, register, logout, changePassword, reload],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>.");
  return context;
}
