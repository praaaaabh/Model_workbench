export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export interface JobRecord {
  id: string;
  name: string;
  entity_type: string;
  entity_id: string;
  status: JobStatus;
  retries: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}
