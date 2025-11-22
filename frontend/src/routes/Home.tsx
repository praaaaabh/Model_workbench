import { useState } from "react";

import { Alert, Box, Stack, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getDatasetMapping } from "../api/datasets";
import { fetchAuditLogs, fetchJobs, retryJob } from "../api/operations";
import { DatasetUploadCard } from "../components/DatasetUploadCard";
import { MappingEditor } from "../components/MappingEditor";
import { ActivityFeed } from "../components/ActivityFeed";
import { JobStatusList } from "../components/JobStatusList";
import { OperationsPanel } from "../components/OperationsPanel";
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

  const auditLogsQuery = useQuery({
    queryKey: ["audit-logs"],
    queryFn: fetchAuditLogs,
    enabled: Boolean(datasetId),
    refetchInterval: 5000,
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: fetchJobs,
    enabled: Boolean(datasetId),
    refetchInterval: 4000,
  });

  const retryMutation = useMutation({
    mutationFn: retryJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const handleUploadSuccess = (dataset: DatasetResponse) => {
    setDatasetId(dataset.id);
    queryClient.setQueryData(["dataset", dataset.id], dataset);
  };

  return (
    <Box>
      <Stack spacing={3}>
        <DatasetUploadCard onUploadSuccess={handleUploadSuccess} />
        {mappingQuery.isError && (
          <Alert severity="error">Unable to load dataset mapping. Please try again.</Alert>
        )}
        {mappingQuery.data && (
          <Stack spacing={3}>
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
            </Box>
            <OperationsPanel datasetId={mappingQuery.data.id} columns={mappingQuery.data.columns} />
            <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
              <Box flex={1}>
                <JobStatusList
                  jobs={jobsQuery.data ?? []}
                  isError={jobsQuery.isError}
                  onRetry={(jobId) => retryMutation.mutate(jobId)}
                />
              </Box>
              <Box flex={1}>
                <ActivityFeed entries={auditLogsQuery.data ?? []} />
              </Box>
            </Stack>
          </Stack>
        )}
      </Stack>
    </Box>
  );
};
