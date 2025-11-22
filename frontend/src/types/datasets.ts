export interface ColumnSchema {
  name: string;
  inferred_type: string;
}

export interface DatasetResponse {
  id: string;
  filename: string;
  version: number;
  columns: ColumnSchema[];
  mapping: Record<string, string>;
  suggestions: Record<string, string>;
}
