import { FormEvent, useMemo, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";

import { createModel, listModels } from "../api/models";
import { ModelResponse, TaskType } from "../types/models";

const taskTypes: TaskType[] = ["classification", "regression"];

export const ModelLibrary = () => {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    description: "",
    task_type: "classification" as TaskType,
  });

  const modelsQuery = useQuery<ModelResponse[]>({
    queryKey: ["models"],
    queryFn: listModels,
  });

  const createMutation = useMutation({
    mutationFn: () => createModel(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      setForm({ name: "", description: "", task_type: "classification" });
    },
  });

  const orderedModels = useMemo(() => {
    return (modelsQuery.data ?? []).slice().sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  }, [modelsQuery.data]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate();
  };

  return (
    <Stack spacing={3}>
      <Box component="form" onSubmit={handleSubmit} sx={{ width: "100%" }}>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Register a new model
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                label="Name"
                value={form.name}
                required
                fullWidth
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              />
              <TextField
                select
                label="Task"
                value={form.task_type}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, task_type: event.target.value as TaskType }))
                }
              >
                {taskTypes.map((task) => (
                  <MenuItem key={task} value={task}>
                    {task}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            <TextField
              label="Description"
              fullWidth
              multiline
              minRows={2}
              sx={{ mt: 2 }}
              value={form.description}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
            />
            {createMutation.isError && (
              <Alert sx={{ mt: 2 }} severity="error">
                Unable to create model. Please try again.
              </Alert>
            )}
          </CardContent>
          <CardActions sx={{ px: 2, pb: 2 }}>
            <Button type="submit" variant="contained" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create model"}
            </Button>
          </CardActions>
        </Card>
      </Box>

      {modelsQuery.isLoading && <Typography>Loading models...</Typography>}
      {modelsQuery.isError && <Alert severity="error">Unable to load model library.</Alert>}

      <Grid container spacing={2}>
        {orderedModels.map((model) => (
          <Grid item xs={12} sm={6} md={4} key={model.id}>
            <Card variant="outlined" sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
              <CardContent sx={{ flexGrow: 1 }}>
                <Typography variant="h6">{model.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {model.description || "No description provided."}
                </Typography>
                <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                  Task: {model.task_type}
                </Typography>
              </CardContent>
              <CardActions>
                <Button component={RouterLink} size="small" to={`/models/${model.id}`}>
                  View details
                </Button>
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Stack>
  );
};
