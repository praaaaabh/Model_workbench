export type TaskType = "classification" | "regression";

export interface ModelResponse {
  id: string;
  name: string;
  description?: string | null;
  task_type: TaskType;
  created_at: string;
  latest_run_id?: string | null;
}

export interface ModelRun {
  id: string;
  model_id: string;
  status: "pending" | "running" | "succeeded" | "failed";
  created_at: string;
  hyperparameters: Record<string, unknown>;
  metrics?: Record<string, number>;
  artifacts: string[];
  message?: string | null;
}

export interface RunListResponse {
  runs: ModelRun[];
}
