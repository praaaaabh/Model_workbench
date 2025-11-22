import { useState } from "react";

import { Alert, Box, Stack, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { downloadDatasetProfile, getDatasetMapping, getDatasetProfile, requestDatasetProfile } from "../api/datasets";
import { DatasetUploadCard } from "../components/DatasetUploadCard";
import { MappingEditor } from "../components/MappingEditor";
import { ProfileDashboard } from "../components/ProfileDashboard";
import { SchemaPreviewTable } from "../components/SchemaPreviewTable";
import { DatasetResponse } from "../types/datasets";

export const Home = () => {
  const queryClient = useQueryClient();
  const [datasetId, setDatasetId] = useState<string | null>(null);

  const mappingQuery = useQuery<DatasetResponse | undefined>({
    queryKey: ["dataset", datasetId],
    queryFn: () => getDatasetMapping(datasetId!),
    enabled: Boolean(datasetId),
    initialData: datasetId
      ? (queryClient.getQueryData(["dataset", datasetId]) as DatasetResponse | undefined)
      : undefined,
  });

  const profileQuery = useQuery({
    queryKey: ["dataset-profile", datasetId],
    queryFn: () => getDatasetProfile(datasetId!),
    enabled: Boolean(datasetId),
    refetchInterval: (data) => (data?.status === "pending" ? 1000 : false),
  });

  const profileMutation = useMutation({
    mutationFn: () => requestDatasetProfile(datasetId!),
    onSuccess: (data) => {
      queryClient.setQueryData(["dataset-profile", datasetId], data);
    },
  });

  const handleUploadSuccess = (dataset: DatasetResponse) => {
    setDatasetId(dataset.id);
    queryClient.setQueryData(["dataset", dataset.id], dataset);
    queryClient.removeQueries({ queryKey: ["dataset-profile", dataset.id] });
  };

  const handleDownloadReport = async () => {
    if (!datasetId || !profileQuery.data?.artifact_url) return;
    const blob = await downloadDatasetProfile(datasetId);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${datasetId}_profile.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

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
            <Box sx={{ mt: 3 }}>
              <ProfileDashboard
                profile={profileQuery.data}
                isLoading={profileMutation.isPending || profileQuery.isFetching}
                onRunProfile={() => profileMutation.mutate()}
                onDownloadReport={handleDownloadReport}
              />
            </Box>
          </Box>
        )}
      </Stack>
    </Box>
  );
};
