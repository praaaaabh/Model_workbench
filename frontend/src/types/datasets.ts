export interface ColumnSchema {
  name: string;
  inferred_type: string;
}

export type ColumnType = "string" | "integer" | "float";

export interface ErrorSample {
  row: number;
  column: string;
  value: string;
  error: string;
}

export interface StandardizationStatus {
  status: string;
  progress: number;
  message?: string | null;
  rows_total: number;
  rows_processed: number;
  rows_with_errors: number;
  error_samples: ErrorSample[];
  output_filename?: string | null;
  audit_log: string[];
}

export interface DatasetResponse {
  id: string;
  filename: string;
  columns: ColumnSchema[];
  mapping: Record<string, string>;
  suggestions: Record<string, string>;
  column_types: Record<string, ColumnType>;
  standardization_status: StandardizationStatus | null;
}
