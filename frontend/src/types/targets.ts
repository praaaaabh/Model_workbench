import { ColumnSchema } from "./datasets";

export interface Rule {
  column: string;
  operator: string;
  value: string;
}

export interface Recipe {
  target_name: string;
  rules: Rule[];
  filters?: Rule[];
}

export interface CreateTargetRequest {
  dataset_id: string;
  dataset_version: number;
  recipe: Recipe;
}

export interface TargetResponse {
  id: string;
  dataset_id: string;
  dataset_version: number;
  recipe: Recipe;
}

export interface MaterializeResponse {
  target_id: string;
  dataset_id: string;
  dataset_version: number;
  output_filename: string;
  row_count: number;
  preview: Array<Record<string, string>>;
}

export interface TargetBuilderDraft extends Rule {
  id: string;
}

export interface TargetBuilderState {
  targetName: string;
  rules: TargetBuilderDraft[];
  filters: TargetBuilderDraft[];
  selectedColumn?: ColumnSchema;
}
