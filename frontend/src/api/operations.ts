import { AuditLogEntry } from "../types/audit";
import { JobRecord } from "../types/jobs";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const fetchAuditLogs = async (): Promise<AuditLogEntry[]> => {
  const response = await fetch(`${API_BASE_URL}/audit/logs`);
  if (!response.ok) {
    throw new Error("Failed to load audit logs");
  }
  return response.json();
};

export const fetchJobs = async (): Promise<JobRecord[]> => {
  const response = await fetch(`${API_BASE_URL}/jobs`);
  if (!response.ok) {
    throw new Error("Failed to load jobs");
  }
  return response.json();
};

export const setTarget = async (datasetId: string, target: string): Promise<JobRecord> => {
  const response = await fetch(`${API_BASE_URL}/targets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, target }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to set target");
  }

  return response.json();
};

export const trainModel = async (
  datasetId: string,
  target: string,
  forceError = false,
): Promise<JobRecord> => {
  const response = await fetch(`${API_BASE_URL}/models/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, target, force_error: forceError }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to train model");
  }

  return response.json();
};

export const retryJob = async (jobId: string): Promise<JobRecord> => {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/retry`, {
    method: "POST",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to retry job");
  }

  return response.json();
};
