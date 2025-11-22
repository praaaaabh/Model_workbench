import { useEffect, useMemo, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Grid,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateDatasetMapping } from "../api/datasets";
import { ColumnSchema, DatasetResponse } from "../types/datasets";

interface MappingEditorProps {
  datasetId: string;
  columns: ColumnSchema[];
  mapping: Record<string, string>;
  suggestions: Record<string, string>;
}

const DEFAULT_STANDARD_VARIABLES = [
  "age",
  "sex",
  "height",
  "weight",
  "bp_systolic",
  "bp_diastolic",
  "cholesterol",
  "glucose",
  "patient_id",
  "visit_date",
];

export const MappingEditor = ({ datasetId, columns, mapping, suggestions }: MappingEditorProps) => {
  const queryClient = useQueryClient();
  const [draftMapping, setDraftMapping] = useState<Record<string, string>>({});
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    const hydrated = columns.reduce<Record<string, string>>((acc, column) => {
      const existing = mapping[column.name] ?? suggestions[column.name] ?? "";
      acc[column.name] = existing;
      return acc;
    }, {});
    setDraftMapping(hydrated);
  }, [columns, mapping, suggestions]);

  const availableOptions = useMemo(() => {
    const collected = new Set(DEFAULT_STANDARD_VARIABLES);
    Object.values(suggestions).forEach((value) => collected.add(value));
    Object.values(mapping).forEach((value) => collected.add(value));
    return Array.from(collected);
  }, [mapping, suggestions]);

  const mutation = useMutation({
    mutationFn: (payload: Record<string, string>) => updateDatasetMapping(datasetId, payload),
    onSuccess: (data: DatasetResponse) => {
      queryClient.setQueryData(["dataset", datasetId], data);
      setStatusMessage("Mapping saved successfully.");
    },
  });

  const handleInputChange = (column: string, value: string) => {
    setDraftMapping((prev) => ({ ...prev, [column]: value }));
  };

  const applySuggestions = () => {
    setDraftMapping((prev) => ({ ...prev, ...suggestions }));
  };

  const handleSave = () => {
    setStatusMessage(null);
    mutation.mutate(draftMapping);
  };

  return (
    <Card sx={{ mt: 3 }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">Column Mapping</Typography>
          <Button variant="text" onClick={applySuggestions} disabled={Object.keys(suggestions).length === 0}>
            Use suggestions
          </Button>
        </Stack>
        {statusMessage && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {statusMessage}
          </Alert>
        )}
        <Grid container spacing={2}>
          {columns.map((column) => (
            <Grid item xs={12} md={6} key={column.name}>
              <Box
                sx={{
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 1,
                  p: 2,
                }}
              >
                <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="subtitle1">{column.name}</Typography>
                  {suggestions[column.name] ? (
                    <Chip size="small" color="primary" label={`Suggestion: ${suggestions[column.name]}`} />
                  ) : (
                    <Chip size="small" label="No suggestion" />
                  )}
                </Stack>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Inferred type: {column.inferred_type}
                </Typography>
                <TextField
                  fullWidth
                  select={false}
                  label="Mapped standard variable"
                  value={draftMapping[column.name] ?? ""}
                  onChange={(event) => handleInputChange(column.name, event.target.value)}
                  placeholder="Enter or paste a standard variable"
                  helperText={availableOptions.join(", ")}
                />
              </Box>
            </Grid>
          ))}
        </Grid>
      </CardContent>
      <CardActions>
        <Button variant="contained" onClick={handleSave} disabled={mutation.isPending}>
          Save mapping
        </Button>
      </CardActions>
    </Card>
  );
};
