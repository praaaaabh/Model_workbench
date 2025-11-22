export interface ArtifactInfo {
  name: string;
  kind: string;
  url: string;
}

export interface ModelArtifactsResponse {
  id: string;
  name: string;
  artifacts: ArtifactInfo[];
}

export interface ScoreResponse {
  model_id: string;
  dataset_id: string;
  scored_filename: string;
  scored_file_url: string;
}
