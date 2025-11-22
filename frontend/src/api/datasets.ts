import { DatasetResponse } from "../types/datasets";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const uploadDataset = (
  file: File,
  onProgress?: (progress: number) => void,
): Promise<DatasetResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/datasets`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(xhr.responseText || "Failed to upload dataset"));
      }
    };

    xhr.onerror = () => reject(new Error("Network error while uploading dataset"));
    xhr.send(formData);
  });
};

export const getDatasetMapping = async (datasetId: string): Promise<DatasetResponse> => {
  const response = await fetch(`${API_BASE_URL}/datasets/${datasetId}/mapping`);
  if (!response.ok) {
    throw new Error("Failed to fetch mapping");
  }

  return response.json();
};

export const updateDatasetMapping = async (
  datasetId: string,
  mapping: Record<string, string>,
): Promise<DatasetResponse> => {
  const response = await fetch(`${API_BASE_URL}/datasets/${datasetId}/mapping`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to update mapping");
  }

  return response.json();
};
