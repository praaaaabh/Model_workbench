import { useMemo, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Divider,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";

import { createTarget, materializeTarget } from "../api/targets";
import { DatasetResponse } from "../types/datasets";
import { CreateTargetRequest, MaterializeResponse, TargetBuilderDraft } from "../types/targets";

interface TargetBuilderProps {
  dataset: DatasetResponse;
}

const operatorOptions = [
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Not equals" },
  { value: "gt", label: "Greater than" },
  { value: "gte", label: "Greater or equal" },
  { value: "lt", label: "Less than" },
  { value: "lte", label: "Less or equal" },
  { value: "contains", label: "Contains" },
  { value: "exists", label: "Exists" },
];

const ruleTemplates = [
  { label: "Is present", operator: "exists", value: "" },
  { label: ">= 0", operator: "gte", value: "0" },
  { label: "Equals 1", operator: "equals", value: "1" },
  { label: "Contains 'yes'", operator: "contains", value: "yes" },
];

const newDraftRule = (fallbackColumn?: string): TargetBuilderDraft => ({
  id: crypto.randomUUID(),
  column: fallbackColumn ?? "",
  operator: "equals",
  value: "",
});

const ruleRequiresValue = (operator: string) => operator !== "exists";

const renderRuleRows = (
  rules: TargetBuilderDraft[],
  dataset: DatasetResponse,
  onChange: (id: string, patch: Partial<TargetBuilderDraft>) => void,
  onRemove: (id: string) => void,
) =>
  rules.map((rule) => (
    <Grid item xs={12} key={rule.id}>
      <Box
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          p: 2,
        }}
      >
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
            <TextField
              label="Column"
              select
              fullWidth
              value={rule.column}
              onChange={(event) => onChange(rule.id, { column: event.target.value })}
              SelectProps={{ native: true }}
            >
              <option value="" disabled>
                Select a column
              </option>
              {dataset.columns.map((col) => (
                <option value={col.name} key={col.name}>
                  {col.name}
                </option>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} md={3}>
            <TextField
              label="Operator"
              select
              fullWidth
              value={rule.operator}
              onChange={(event) => onChange(rule.id, { operator: event.target.value })}
              SelectProps={{ native: true }}
            >
              {operatorOptions.map((option) => (
                <option value={option.value} key={option.value}>
                  {option.label}
                </option>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              label="Value"
              fullWidth
              disabled={!ruleRequiresValue(rule.operator)}
              value={rule.value}
              onChange={(event) => onChange(rule.id, { value: event.target.value })}
              placeholder="Enter a comparison value"
            />
            <Stack direction="row" spacing={1} mt={1} flexWrap="wrap" rowGap={1}>
              {ruleTemplates.map((template) => (
                <Chip
                  key={template.label}
                  size="small"
                  label={template.label}
                  onClick={() =>
                    onChange(rule.id, { operator: template.operator, value: template.value })
                  }
                />
              ))}
            </Stack>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button color="secondary" onClick={() => onRemove(rule.id)} fullWidth>
              Remove
            </Button>
          </Grid>
        </Grid>
      </Box>
    </Grid>
  ));

export const TargetBuilder = ({ dataset }: TargetBuilderProps) => {
  const [targetName, setTargetName] = useState("target");
  const [rules, setRules] = useState<TargetBuilderDraft[]>([
    newDraftRule(dataset.columns[0]?.name ?? ""),
  ]);
  const [filters, setFilters] = useState<TargetBuilderDraft[]>([]);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<MaterializeResponse | null>(null);

  const createMutation = useMutation({
    mutationFn: (payload: CreateTargetRequest) => createTarget(payload),
    onSuccess: (data) => {
      setStatusMessage(`Target saved (version ${data.dataset_version}).`);
      setErrorMessage(null);
    },
    onError: (err: unknown) => setErrorMessage((err as Error).message),
  });

  const previewMutation = useMutation({
    mutationFn: (targetId: string) => materializeTarget(targetId),
    onSuccess: (data) => {
      setPreview(data);
      setStatusMessage("Preview generated using the latest recipe.");
      setErrorMessage(null);
    },
    onError: (err: unknown) => setErrorMessage((err as Error).message),
  });

  const addRule = () => setRules((prev) => [...prev, newDraftRule(dataset.columns[0]?.name ?? "")]);
  const addFilter = () =>
    setFilters((prev) => [...prev, newDraftRule(dataset.columns[0]?.name ?? "")]);

  const updateRule = (id: string, patch: Partial<TargetBuilderDraft>) => {
    setRules((prev) => prev.map((rule) => (rule.id === id ? { ...rule, ...patch } : rule)));
  };

  const updateFilter = (id: string, patch: Partial<TargetBuilderDraft>) => {
    setFilters((prev) => prev.map((rule) => (rule.id === id ? { ...rule, ...patch } : rule)));
  };

  const removeRule = (id: string) => setRules((prev) => prev.filter((rule) => rule.id != id));
  const removeFilter = (id: string) =>
    setFilters((prev) => prev.filter((rule) => rule.id != id));

  const recipePayload = useMemo(() => ({
    target_name: targetName.trim(),
    rules: rules.map(({ column, operator, value }) => ({ column, operator, value })),
    filters: filters.map(({ column, operator, value }) => ({ column, operator, value })),
  }), [targetName, rules, filters]);

  const validateRecipe = () => {
    if (!recipePayload.target_name) {
      setErrorMessage("Target name is required.");
      return false;
    }

    const hasIncompleteRule = recipePayload.rules.some(
      (rule) => !rule.column || !rule.operator || (ruleRequiresValue(rule.operator) && !rule.value),
    );

    if (hasIncompleteRule) {
      setErrorMessage("Each rule needs a column, operator, and value.");
      return false;
    }

    return true;
  };

  const buildRequest = (): CreateTargetRequest => ({
    dataset_id: dataset.id,
    dataset_version: dataset.version,
    recipe: recipePayload,
  });

  const handleSave = async () => {
    if (!validateRecipe()) return;
    setPreview(null);
    await createMutation.mutateAsync(buildRequest());
  };

  const handlePreview = async () => {
    if (!validateRecipe()) return;
    try {
      const target = await createMutation.mutateAsync(buildRequest());
      await previewMutation.mutateAsync(target.id);
    } catch (err) {
      setErrorMessage((err as Error).message);
    }
  };

  const renderPreview = () => {
    if (!preview) return null;
    const rows = preview.preview;
    const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

    return (
      <Box mt={2}>
        <Typography variant="subtitle1" gutterBottom>
          Preview ({rows.length} rows shown)
        </Typography>
        {rows.length === 0 ? (
          <Alert severity="info">No rows available in preview.</Alert>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                {columns.map((name) => (
                  <TableCell key={name}>{name}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row, index) => (
                <TableRow key={`${row[columns[0]]}-${index}`}>
                  {columns.map((name) => (
                    <TableCell key={`${name}-${index}`}>{row[name]}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Box>
    );
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Box>
            <Typography variant="h6">Target builder</Typography>
            <Typography variant="body2" color="text.secondary">
              Create labeling rules for this dataset version and preview the resulting target column.
            </Typography>
          </Box>
          {statusMessage && <Alert severity="success">{statusMessage}</Alert>}
          {errorMessage && <Alert severity="error">{errorMessage}</Alert>}
          <TextField
            label="Target column name"
            value={targetName}
            onChange={(event) => setTargetName(event.target.value)}
            fullWidth
          />
          <Divider textAlign="left">Rules</Divider>
          <Grid container spacing={2}>
            {renderRuleRows(rules, dataset, updateRule, removeRule)}
            <Grid item xs={12}>
              <Button variant="outlined" onClick={addRule}>
                Add rule
              </Button>
            </Grid>
          </Grid>
          <Divider textAlign="left">Filters (optional)</Divider>
          <Grid container spacing={2}>
            {renderRuleRows(filters, dataset, updateFilter, removeFilter)}
            <Grid item xs={12}>
              <Button variant="text" onClick={addFilter}>
                Add filter
              </Button>
            </Grid>
          </Grid>
          {renderPreview()}
        </Stack>
      </CardContent>
      <CardActions>
        <Button variant="contained" onClick={handleSave} disabled={createMutation.isPending}>
          Save target
        </Button>
        <Button
          variant="outlined"
          onClick={handlePreview}
          disabled={createMutation.isPending || previewMutation.isPending}
        >
          Preview sample
        </Button>
      </CardActions>
    </Card>
  );
};
