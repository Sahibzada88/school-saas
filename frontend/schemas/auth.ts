import { z } from "zod";

const email = z.string().trim().min(1, "Email is required").email("Enter a valid email address");
const newPassword = z.string().min(10, "Use at least 10 characters").max(128, "Password is too long");
const phone = z
  .string()
  .trim()
  .regex(/^$|^\+?[0-9 ()-]{7,20}$/, "Enter a valid phone number");

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Password is required"),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    school_name: z.string().trim().min(2, "School name is required").max(200),
    admin_name: z.string().trim().min(2, "Your name is required").max(200),
    email,
    phone,
    country: z.string().trim().min(2, "Country is required").max(100),
    city: z.string().trim().min(2, "City is required").max(100),
    password: newPassword,
    confirm_password: z.string().min(1, "Confirm your password"),
  })
  .refine((values) => values.password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  });
export type RegisterValues = z.infer<typeof registerSchema>;
export type RegisterPayload = Omit<RegisterValues, "confirm_password">;

export const forgotPasswordSchema = z.object({ email });
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({ new_password: newPassword, confirm_password: z.string().min(1, "Confirm your password") })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  });
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: newPassword,
    confirm_password: z.string().min(1, "Confirm your password"),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  });
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;
