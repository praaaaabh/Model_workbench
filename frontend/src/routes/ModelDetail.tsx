import { useMemo, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  Link,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { getArtifactUrl, getModel, getRuns, startTraining } from "../api/models";
import { ModelRun, ModelResponse, RunListResponse } from "../types/models";

const MetricGrid = ({ metrics }: { metrics: Record<string, number> }) => {
  const entries = Object.entries(metrics);
  return (
    <Grid container spacing={2} sx={{ mt: 1 }}>
      {entries.map(([key, value]) => (
        <Grid item xs={12} sm={6} md={4} key={key}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="overline" display="block">
                {key.replace(/_/g, " ")}
              </Typography>
              <Typography variant="h5">{value}</Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
};

const MetricSparkline = ({ metrics }: { metrics: Record<string, number> }) => {
  const points = Object.values(metrics);
  const labels = Object.keys(metrics);

  const normalized = useMemo(() => {
    const max = Math.max(...points, 0.0001);
    return points.map((value) => Math.max(0, (value / max) * 80));
  }, [points]);

  const path = normalized
    .map((value, index) => `${(index / Math.max(normalized.length - 1, 1)) * 100},${100 - value}`)
    .join(" ");

  return (
    <Box sx={{ mt: 2 }}>
      <svg viewBox="0 0 100 100" height={80} width="100%" preserveAspectRatio="none">
        <polyline fill="none" stroke="#1976d2" strokeWidth="2" points={path} />
      </svg>
      <Stack direction="row" flexWrap="wrap" gap={1}>
        {labels.map((label) => (
          <Chip key={label} size="small" label={label} />
        ))}
      </Stack>
    </Box>
  );
};

export const ModelDetail = () => {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const [learningRate, setLearningRate] = useState("0.01");
  const [epochs, setEpochs] = useState("5");

  const modelQuery = useQuery<ModelResponse>({
    queryKey: ["model", id],
    queryFn: () => getModel(id!),
    enabled: Boolean(id),
  });

  const runsQuery = useQuery<RunListResponse>({
    queryKey: ["model", id, "runs"],
    queryFn: () => getRuns(id!),
    enabled: Boolean(id),
    refetchInterval: 750,
  });

  const trainMutation = useMutation({
    mutationFn: () => startTraining(id!, { learning_rate: Number(learningRate), epochs: Number(epochs) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model", id, "runs"] });
    },
  });

  const latestRun = useMemo(() => runsQuery.data?.runs[runsQuery.data.runs.length - 1], [runsQuery.data]);

  return (
    <Stack spacing={3}>
      {modelQuery.data && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h4">{modelQuery.data.name}</Typography>
            <Typography color="text.secondary">{modelQuery.data.description}</Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1 }}>
              Task: {modelQuery.data.task_type}
            </Typography>
          </CardContent>
        </Card>
      )}

      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6">Launch a training run</Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 2 }}>
            <TextField
              label="Learning rate"
              value={learningRate}
              onChange={(event) => setLearningRate(event.target.value)}
            />
            <TextField label="Epochs" value={epochs} onChange={(event) => setEpochs(event.target.value)} />
            <Button
              variant="contained"
              onClick={() => trainMutation.mutate()}
              disabled={trainMutation.isPending || !id}
            >
              {trainMutation.isPending ? "Starting..." : "Train"}
            </Button>
          </Stack>
          {trainMutation.isError && (
            <Alert sx={{ mt: 2 }} severity="error">
              Unable to start training.
            </Alert>
          )}
        </CardContent>
      </Card>

      {runsQuery.isFetching && <LinearProgress />}

      {latestRun && (
        <Card variant="outlined">
          <CardContent>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="h6">Latest run</Typography>
              <Chip label={latestRun.status} color={latestRun.status === "succeeded" ? "success" : "default"} />
            </Stack>
            {latestRun.metrics && <MetricGrid metrics={latestRun.metrics} />}
            {latestRun.metrics && <MetricSparkline metrics={latestRun.metrics} />}
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle1">Artifacts</Typography>
            {latestRun.artifacts.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                Artifacts will appear after the run finishes.
              </Typography>
            )}
            <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 1 }}>
              {latestRun.artifacts.map((artifact) => (
                <Link key={artifact} href={getArtifactUrl(latestRun.model_id, latestRun.id, artifact)} target="_blank">
                  {artifact}
                </Link>
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      {runsQuery.data && runsQuery.data.runs.length === 0 && (
        <Alert severity="info">Train the model to see metrics and download artifacts.</Alert>
      )}
    </Stack>
  );
};
