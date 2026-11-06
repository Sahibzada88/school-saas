/** Platform rows carry every field; school-level rows omit actor_email, school_*, ip and metadata. */
export interface AuditLogEntry {
  id: string;
  created_at: string;
  action: string;
  description: string;
  entity_type: string;
  entity_id: string;
  actor_name: string | null;
  actor_email?: string | null;
  actor_role?: string;
  school_id?: string | null;
  school_name?: string | null;
  ip?: string | null;
}
