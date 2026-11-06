export type NotificationSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  severity: NotificationSeverity;
  data: Record<string, unknown>;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}
