import { API_BASE_URL } from "./config";
import { ModelArtifactsResponse, ScoreResponse } from "../types/models";

export const getModelArtifacts = async (modelId: string): Promise<ModelArtifactsResponse> => {
  const response = await fetch(`${API_BASE_URL}/models/${modelId}/artifacts`);
  if (!response.ok) {
    throw new Error("Failed to load model artifacts");
  }

  return response.json();
};

export const scoreDataset = async (
  modelId: string,
  datasetId: string,
): Promise<ScoreResponse> => {
  const response = await fetch(`${API_BASE_URL}/models/${modelId}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Unable to score dataset");
  }

  return response.json();
};
