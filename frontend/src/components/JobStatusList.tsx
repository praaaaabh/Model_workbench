import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";

import { JobRecord } from "../types/jobs";

const statusColor: Record<string, "default" | "primary" | "success" | "error"> = {
  pending: "primary",
  running: "primary",
  succeeded: "success",
  failed: "error",
};

interface JobStatusListProps {
  jobs: JobRecord[];
  isError?: boolean;
  onRetry?: (jobId: string) => void;
}

export const JobStatusList = ({ jobs, isError, onRetry }: JobStatusListProps) => {
  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">Job Status</Typography>
          <Chip label={`${jobs.length} job${jobs.length === 1 ? "" : "s"}`} size="small" />
        </Stack>
        {isError && <Alert severity="error">Unable to load jobs. Please try again.</Alert>}
        {!isError && jobs.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No jobs have been created yet.
          </Typography>
        )}
        <List>
          {jobs.map((job) => (
            <ListItem key={job.id} divider alignItems="flex-start">
              <ListItemText
                primary={
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip size="small" color={statusColor[job.status] ?? "default"} label={job.status} />
                    <Typography variant="subtitle2">{job.name}</Typography>
                  </Stack>
                }
                secondary={
                  <Stack spacing={0.5} mt={0.5}>
                    <Typography variant="body2" color="text.primary">
                      {job.error_message || `Entity: ${job.entity_type} (${job.entity_id})`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Last updated at {new Date(job.updated_at).toLocaleString()} | Retries: {job.retries}
                    </Typography>
                  </Stack>
                }
              />
              {job.status === "failed" && onRetry && (
                <ListItemSecondaryAction>
                  <Button size="small" variant="outlined" onClick={() => onRetry(job.id)}>
                    Retry
                  </Button>
                </ListItemSecondaryAction>
              )}
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );
};
