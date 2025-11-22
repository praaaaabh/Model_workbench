import { ModelResponse, ModelRun, RunListResponse } from "../types/models";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const listModels = async (): Promise<ModelResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/models`);
  if (!response.ok) {
    throw new Error("Failed to load models");
  }
  return response.json();
};

export const createModel = async (
  payload: Pick<ModelResponse, "name" | "description" | "task_type">
): Promise<ModelResponse> => {
  const response = await fetch(`${API_BASE_URL}/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Unable to create model");
  }

  return response.json();
};

export const getModel = async (modelId: string): Promise<ModelResponse> => {
  const response = await fetch(`${API_BASE_URL}/models/${modelId}`);
  if (!response.ok) {
    throw new Error("Model not found");
  }
  return response.json();
};

export const startTraining = async (
  modelId: string,
  hyperparameters: Record<string, unknown>
): Promise<ModelRun> => {
  const response = await fetch(`${API_BASE_URL}/models/${modelId}/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hyperparameters }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to start training");
  }

  return response.json();
};

export const getRuns = async (modelId: string): Promise<RunListResponse> => {
  const response = await fetch(`${API_BASE_URL}/models/${modelId}/runs`);
  if (!response.ok) {
    throw new Error("Unable to fetch runs");
  }
  return response.json();
};

export const getArtifactUrl = (modelId: string, runId: string, artifactName: string) =>
  `${API_BASE_URL}/models/${modelId}/runs/${runId}/artifacts/${artifactName}`;
