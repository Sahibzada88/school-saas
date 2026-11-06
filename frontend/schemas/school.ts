import { z } from "zod";

const phone = z
  .string()
  .trim()
  .regex(/^$|^\+?[0-9 ()-]{7,20}$/, "Enter a valid phone number");

export const profileSchema = z.object({
  name: z.string().trim().min(2, "School name is required").max(200),
  email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
  phone,
  country: z.string().trim().min(2, "Country is required").max(100),
  city: z.string().trim().min(2, "City is required").max(100),
  address: z.string().trim().max(255),
  timezone: z.string().trim().min(1, "Time zone is required").max(64),
});
export type ProfileValues = z.infer<typeof profileSchema>;

const ROLES = ["SCHOOL_ADMIN", "TEACHER", "ACCOUNTANT", "RECEPTIONIST", "PARENT", "STUDENT"] as const;

export const createUserSchema = z.object({
  email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
  first_name: z.string().trim().min(1, "First name is required").max(100),
  last_name: z.string().trim().max(100),
  phone,
  role: z.enum(ROLES, { message: "Choose a role" }),
  password: z.string().min(10, "Use at least 10 characters").max(128),
});
export type CreateUserValues = z.infer<typeof createUserSchema>;

export const editUserSchema = z.object({
  first_name: z.string().trim().min(1, "First name is required").max(100),
  last_name: z.string().trim().max(100),
  phone,
  role: z.enum(ROLES, { message: "Choose a role" }),
});
export type EditUserValues = z.infer<typeof editUserSchema>;
