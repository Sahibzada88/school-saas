import { apiFetch } from "@/lib/api-client";
import type { LoginValues, RegisterPayload } from "@/schemas/auth";
import type { Me } from "@/types/auth";

export const authService = {
  getMe: () => apiFetch<Me>("/auth/me/"),
  login: (values: LoginValues) => apiFetch<Me>("/auth/login/", { method: "POST", body: values }),
  register: (values: RegisterPayload) => apiFetch<Me>("/auth/register/", { method: "POST", body: values }),
  logout: () => apiFetch<null>("/auth/logout/", { method: "POST" }),
  changePassword: (values: { current_password: string; new_password: string }) =>
    apiFetch<Me>("/auth/change-password/", { method: "POST", body: values }),
  requestPasswordReset: (email: string) =>
    apiFetch<null>("/auth/password-reset/request/", { method: "POST", body: { email } }),
  confirmPasswordReset: (values: { token: string; new_password: string }) =>
    apiFetch<null>("/auth/password-reset/confirm/", { method: "POST", body: values }),
};
