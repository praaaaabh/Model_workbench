import { useState } from "react";

import { Alert, Box, Button, Card, CardActions, CardContent, Stack, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getDatasetMapping } from "../api/datasets";
import { getModelArtifacts, scoreDataset } from "../api/models";
import { DatasetUploadCard } from "../components/DatasetUploadCard";
import { MappingEditor } from "../components/MappingEditor";
import { SchemaPreviewTable } from "../components/SchemaPreviewTable";
import { DatasetResponse } from "../types/datasets";
import { ModelArtifactsResponse, ScoreResponse } from "../types/models";
import { API_BASE_URL } from "../api/config";

export const Home = () => {
  const queryClient = useQueryClient();
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [scoreResult, setScoreResult] = useState<ScoreResponse | null>(null);
  const [scoreError, setScoreError] = useState<string | null>(null);

  const defaultModelId = "demo-model";

  const mappingQuery = useQuery<DatasetResponse | undefined>({
    queryKey: ["dataset", datasetId],
    queryFn: () => getDatasetMapping(datasetId!),
    enabled: Boolean(datasetId),
    initialData: datasetId
      ? (queryClient.getQueryData(["dataset", datasetId]) as DatasetResponse | undefined)
      : undefined,
  });

  const artifactsQuery = useQuery<ModelArtifactsResponse>({
    queryKey: ["model-artifacts", defaultModelId],
    queryFn: () => getModelArtifacts(defaultModelId),
  });

  const scoreMutation = useMutation({
    mutationFn: () => scoreDataset(defaultModelId, datasetId!),
    onSuccess: (payload: ScoreResponse) => {
      setScoreError(null);
      setScoreResult(payload);
    },
    onError: (error: unknown) => {
      setScoreResult(null);
      setScoreError((error as Error).message);
    },
  });

  const handleUploadSuccess = (dataset: DatasetResponse) => {
    setDatasetId(dataset.id);
    queryClient.setQueryData(["dataset", dataset.id], dataset);
  };

  const scoredFileDownloadUrl = scoreResult
    ? `${API_BASE_URL}${scoreResult.scored_file_url}`
    : null;

  const modelBinaryArtifact = artifactsQuery.data?.artifacts.find(
    (artifact) => artifact.kind === "model_binary" || artifact.name.endsWith(".bin"),
  );

  const modelDownloadUrl = modelBinaryArtifact ? `${API_BASE_URL}${modelBinaryArtifact.url}` : null;

  return (
    <Box>
      <Stack spacing={3}>
        <DatasetUploadCard onUploadSuccess={handleUploadSuccess} />
        {mappingQuery.isError && (
          <Alert severity="error">Unable to load dataset mapping. Please try again.</Alert>
        )}
        {mappingQuery.data && (
          <Box>
            <Typography variant="h5" gutterBottom>
              {mappingQuery.data.filename}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Columns and inferred schema preview
            </Typography>
            <SchemaPreviewTable columns={mappingQuery.data.columns} />
            <MappingEditor
              datasetId={mappingQuery.data.id}
              columns={mappingQuery.data.columns}
              mapping={mappingQuery.data.mapping}
              suggestions={mappingQuery.data.suggestions}
            />
            <Card sx={{ mt: 3 }}>
              <CardContent>
                <Stack spacing={1}>
                  <Typography variant="h6">Score dataset</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Run the demo model to generate a scored CSV and download model artifacts.
                  </Typography>
                  {scoreError && (
                    <Alert severity="error" onClose={() => setScoreError(null)}>
                      {scoreError}
                    </Alert>
                  )}
                  {scoreResult && (
                    <Alert severity="success">Dataset scored successfully.</Alert>
                  )}
                  {artifactsQuery.isError && (
                    <Alert severity="error">Unable to load model artifacts.</Alert>
                  )}
                </Stack>
              </CardContent>
              <CardActions>
                <Button
                  variant="contained"
                  onClick={() => scoreMutation.mutate()}
                  disabled={!datasetId || scoreMutation.isPending}
                >
                  {scoreMutation.isPending ? "Scoring..." : "Score dataset"}
                </Button>
                {scoredFileDownloadUrl && (
                  <Button
                    variant="outlined"
                    component="a"
                    href={scoredFileDownloadUrl}
                    download
                    disabled={scoreMutation.isPending}
                  >
                    Download scored CSV
                  </Button>
                )}
                {modelDownloadUrl && (
                  <Button variant="outlined" component="a" href={modelDownloadUrl} download>
                    Download model file
                  </Button>
                )}
              </CardActions>
            </Card>
          </Box>
        )}
      </Stack>
    </Box>
  );
};
