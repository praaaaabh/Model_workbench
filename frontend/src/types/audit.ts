export interface AuditLogEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  status: string;
  message?: string | null;
  retries: number;
  timestamp: string;
}
