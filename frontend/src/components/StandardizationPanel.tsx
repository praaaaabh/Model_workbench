import { useEffect, useMemo, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchStandardizationStatus, standardizeDataset } from "../api/datasets";
import { ColumnSchema, ColumnType, DatasetResponse, StandardizationStatus } from "../types/datasets";

interface StandardizationPanelProps {
  datasetId: string;
  columns: ColumnSchema[];
  columnTypes: Record<string, ColumnType>;
  standardizationStatus: StandardizationStatus | null;
}

const TYPE_OPTIONS: ColumnType[] = ["string", "integer", "float"];

export const StandardizationPanel = ({
  datasetId,
  columns,
  columnTypes,
  standardizationStatus,
}: StandardizationPanelProps) => {
  const queryClient = useQueryClient();
  const [draftTypes, setDraftTypes] = useState<Record<string, ColumnType>>(columnTypes);

  useEffect(() => {
    setDraftTypes(columnTypes);
  }, [columnTypes, datasetId]);

  const statusQuery = useQuery<StandardizationStatus | null>({
    queryKey: ["dataset", datasetId, "standardization-status"],
    queryFn: () => fetchStandardizationStatus(datasetId),
    enabled: Boolean(datasetId),
    initialData: standardizationStatus ?? undefined,
  });

  const standardizeMutation = useMutation({
    mutationFn: () => standardizeDataset(datasetId, draftTypes),
    onSuccess: (statusData: StandardizationStatus) => {
      queryClient.setQueryData(["dataset", datasetId], (prev) => {
        if (!prev) return prev;
        const typed = prev as DatasetResponse;
        return {
          ...typed,
          column_types: draftTypes,
          standardization_status: statusData,
        };
      });
      queryClient.setQueryData(["dataset", datasetId, "standardization-status"], statusData);
    },
  });

  const handleTypeChange = (column: string, type: ColumnType) => {
    setDraftTypes((prev) => ({ ...prev, [column]: type }));
  };

  const statusData = useMemo(() => statusQuery.data, [statusQuery.data]);

  return (
    <Card sx={{ mt: 3 }}>
      <CardContent>
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
          <Typography variant="h6">Type standardization</Typography>
          <Button
            variant="contained"
            onClick={() => standardizeMutation.mutate()}
            disabled={standardizeMutation.isPending}
          >
            {statusData ? "Re-run" : "Run"} standardization
          </Button>
        </Stack>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Confirm or edit the target type for each column, then run standardization to convert values
          and capture an audit log.
        </Typography>
        {standardizeMutation.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {(standardizeMutation.error as Error).message}
          </Alert>
        )}
        <Box sx={{ overflowX: "auto", mt: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Column</TableCell>
                <TableCell>Inferred type</TableCell>
                <TableCell>Target type</TableCell>
                <TableCell>Suggestion</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {columns.map((column) => (
                <TableRow key={column.name}>
                  <TableCell>{column.name}</TableCell>
                  <TableCell>{column.inferred_type}</TableCell>
                  <TableCell>
                    <Select
                      size="small"
                      value={draftTypes[column.name] ?? (column.inferred_type as ColumnType)}
                      onChange={(event) => handleTypeChange(column.name, event.target.value as ColumnType)}
                    >
                      {TYPE_OPTIONS.map((option) => (
                        <MenuItem key={option} value={option}>
                          {option}
                        </MenuItem>
                      ))}
                    </Select>
                  </TableCell>
                  <TableCell>
                    {draftTypes[column.name] !== column.inferred_type ? (
                      <Chip label="Custom" color="primary" size="small" />
                    ) : (
                      <Chip label="Inferred" size="small" />
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
        <Divider sx={{ my: 2 }} />
        {statusQuery.isError && <Alert severity="error">Unable to load status.</Alert>}
        {statusData && (
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Stack spacing={1}>
                <Typography variant="subtitle2" color="text.secondary">
                  Status
                </Typography>
                <Chip label={statusData.status} color={statusData.status === "completed" ? "success" : "default"} />
                {statusData.message && (
                  <Typography variant="body2" color="text.secondary">
                    {statusData.message}
                  </Typography>
                )}
              </Stack>
            </Grid>
            <Grid item xs={12} md={8}>
              <Grid container spacing={2}>
                <Grid item xs={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Rows processed
                  </Typography>
                  <Typography>{statusData.rows_processed}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Rows with errors
                  </Typography>
                  <Typography>{statusData.rows_with_errors}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Output file
                  </Typography>
                  <Typography>{statusData.output_filename ?? "Pending"}</Typography>
                </Grid>
              </Grid>
            </Grid>
            {statusData.error_samples.length > 0 && (
              <Grid item xs={12}>
                <Typography variant="subtitle1" gutterBottom>
                  Error samples
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Row</TableCell>
                      <TableCell>Column</TableCell>
                      <TableCell>Value</TableCell>
                      <TableCell>Error</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {statusData.error_samples.map((sample) => (
                      <TableRow key={`${sample.row}-${sample.column}`}>
                        <TableCell>{sample.row}</TableCell>
                        <TableCell>{sample.column}</TableCell>
                        <TableCell>{sample.value}</TableCell>
                        <TableCell>{sample.error}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Grid>
            )}
            {statusData.audit_log.length > 0 && (
              <Grid item xs={12}>
                <Typography variant="subtitle1">Audit log</Typography>
                <Stack spacing={0.5} mt={1}>
                  {statusData.audit_log.map((line, index) => (
                    <Typography key={`${line}-${index}`} variant="body2" color="text.secondary">
                      {line}
                    </Typography>
                  ))}
                </Stack>
              </Grid>
            )}
          </Grid>
        )}
      </CardContent>
    </Card>
  );
};
