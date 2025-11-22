import { API_BASE_URL } from "./datasets";
import { CreateTargetRequest, MaterializeResponse, TargetResponse } from "../types/targets";

export const createTarget = async (payload: CreateTargetRequest): Promise<TargetResponse> => {
  const response = await fetch(`${API_BASE_URL}/targets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to create target");
  }

  return response.json();
};

export const materializeTarget = async (targetId: string): Promise<MaterializeResponse> => {
  const response = await fetch(`${API_BASE_URL}/targets/${targetId}/materialize`, {
    method: "POST",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to materialize target");
  }

  return response.json();
};
