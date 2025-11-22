import { useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { trainModel, setTarget } from "../api/operations";
import { ColumnSchema } from "../types/datasets";
import { JobRecord } from "../types/jobs";

interface OperationsPanelProps {
  datasetId: string;
  columns: ColumnSchema[];
}

export const OperationsPanel = ({ datasetId, columns }: OperationsPanelProps) => {
  const queryClient = useQueryClient();
  const [target, setTargetColumn] = useState<string>("");
  const [forceError, setForceError] = useState(false);

  const invalidateMonitoringQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
  };

  const targetMutation = useMutation<JobRecord, Error, string>({
    mutationFn: (targetValue) => setTarget(datasetId, targetValue),
    onSuccess: invalidateMonitoringQueries,
  });

  const modelMutation = useMutation<JobRecord, Error, { target: string; forceError: boolean }>({
    mutationFn: ({ target, forceError }) => trainModel(datasetId, target, forceError),
    onSuccess: invalidateMonitoringQueries,
  });

  const handleTargetSave = () => {
    if (!target) return;
    targetMutation.mutate(target);
  };

  const handleModelTrain = () => {
    if (!target) return;
    modelMutation.mutate({ target, forceError });
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6">Targets & Models</Typography>
          <FormControl fullWidth>
            <InputLabel id="target-select-label">Target Column</InputLabel>
            <Select
              labelId="target-select-label"
              value={target}
              label="Target Column"
              onChange={(event) => setTargetColumn(event.target.value as string)}
            >
              {columns.map((column) => (
                <MenuItem key={column.name} value={column.name}>
                  {column.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <Button
              variant="contained"
              onClick={handleTargetSave}
              disabled={!target || targetMutation.isPending}
            >
              Save Target
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              onClick={() => setForceError((prev) => !prev)}
            >
              {forceError ? "Simulate Success" : "Simulate Error"}
            </Button>
            <Button
              variant="contained"
              color="success"
              onClick={handleModelTrain}
              disabled={!target || modelMutation.isPending}
            >
              Train Model
            </Button>
          </Stack>
          {(targetMutation.error || modelMutation.error) && (
            <Alert severity="error">{targetMutation.error?.message || modelMutation.error?.message}</Alert>
          )}
          {(targetMutation.data || modelMutation.data) && (
            <Box>
              <Typography variant="subtitle2">Latest job</Typography>
              <Typography variant="body2" color="text.secondary">
                {(targetMutation.data || modelMutation.data)?.status}
              </Typography>
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};
