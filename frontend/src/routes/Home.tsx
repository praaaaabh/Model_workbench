import { useState } from "react";

import { Alert, Box, Stack, Typography } from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getDatasetMapping } from "../api/datasets";
import { DatasetUploadCard } from "../components/DatasetUploadCard";
import { MappingEditor } from "../components/MappingEditor";
import { SchemaPreviewTable } from "../components/SchemaPreviewTable";
import { TargetBuilder } from "../components/TargetBuilder";
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
            <TargetBuilder dataset={mappingQuery.data} />
          </Box>
        )}
      </Stack>
    </Box>
  );
};
