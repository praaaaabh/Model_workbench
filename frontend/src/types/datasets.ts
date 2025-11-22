export interface ColumnSchema {
  name: string;
  inferred_type: string;
}

export interface DatasetResponse {
  id: string;
  filename: string;
  columns: ColumnSchema[];
  mapping: Record<string, string>;
  suggestions: Record<string, string>;
}

export type ProfileStatus = "pending" | "completed" | "failed";

export interface ColumnProfile {
  name: string;
  inferred_type: string;
  non_nulls: number;
  missing: number;
  sample_values: string[];
}

export interface DatasetProfileResponse {
  status: ProfileStatus;
  row_count: number | null;
  column_count: number | null;
  columns: ColumnProfile[];
  artifact_url: string | null;
  updated_at: string;
  message?: string | null;
}
