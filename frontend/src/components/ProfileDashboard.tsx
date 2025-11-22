import { useMemo } from "react";

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
  Stack,
  Typography,
} from "@mui/material";

import { ColumnProfile, DatasetProfileResponse, ProfileStatus } from "../types/datasets";

interface ProfileDashboardProps {
  profile: DatasetProfileResponse | undefined;
  isLoading: boolean;
  onRunProfile: () => void;
  onDownloadReport: () => void;
}

const StatusChip = ({ status }: { status: ProfileStatus }) => {
  const color = status === "completed" ? "success" : status === "failed" ? "error" : "warning";
  const label = status === "pending" ? "Profiling" : status === "completed" ? "Ready" : "Failed";
  return <Chip label={label} color={color} size="small" />;
};

const StatCard = ({ title, value }: { title: string; value: string | number }) => (
  <Card variant="outlined">
    <CardContent>
      <Typography variant="overline" color="text.secondary">
        {title}
      </Typography>
      <Typography variant="h5">{value}</Typography>
    </CardContent>
  </Card>
);

const ColumnBar = ({ profile, max }: { profile: ColumnProfile; max: number }) => {
  const total = profile.non_nulls + profile.missing;
  const completeness = total === 0 ? 0 : Math.round((profile.non_nulls / total) * 100);

  return (
    <Box sx={{ mb: 1 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="body2" fontWeight={600}>
          {profile.name}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {profile.inferred_type}
        </Typography>
      </Stack>
      <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
        <Box sx={{ flexGrow: 1 }}>
          <LinearProgress
            variant="determinate"
            value={max === 0 ? 0 : Math.round((profile.non_nulls / max) * 100)}
            sx={{ height: 10, borderRadius: 5 }}
            color="success"
          />
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ width: 50, textAlign: "right" }}>
          {completeness}%
        </Typography>
      </Box>
      {profile.sample_values.length > 0 && (
        <Typography variant="caption" color="text.secondary">
          Examples: {profile.sample_values.join(", ")}
        </Typography>
      )}
    </Box>
  );
};

export const ProfileDashboard = ({
  profile,
  isLoading,
  onRunProfile,
  onDownloadReport,
}: ProfileDashboardProps) => {
  const maxRows = useMemo(() => {
    if (!profile || !profile.columns?.length) return 0;
    return Math.max(...profile.columns.map((column) => column.non_nulls + column.missing));
  }, [profile]);

  const hasProfile = Boolean(profile && profile.status !== "pending");

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2}>
            <Box>
              <Typography variant="h6">Exploratory data profile</Typography>
              <Typography variant="body2" color="text.secondary">
                Kick off a profiling job to summarize quality, completeness, and examples.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1}>
              {profile && <StatusChip status={profile.status} />}
              <Button variant="contained" onClick={onRunProfile} disabled={isLoading}>
                {isLoading ? "Running..." : "Run profiling"}
              </Button>
              <Button
                variant="outlined"
                onClick={onDownloadReport}
                disabled={!profile || profile.status !== "completed"}
              >
                Download DQ report
              </Button>
            </Stack>
          </Stack>

          {profile?.status === "failed" && profile.message && (
            <Alert severity="error">{profile.message}</Alert>
          )}

          {isLoading && <LinearProgress />}

          {hasProfile ? (
            <Box>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <StatCard title="Rows" value={profile?.row_count ?? 0} />
                </Grid>
                <Grid item xs={12} md={4}>
                  <StatCard title="Columns" value={profile?.column_count ?? 0} />
                </Grid>
                <Grid item xs={12} md={4}>
                  <StatCard
                    title="Last updated"
                    value={profile?.updated_at ? new Date(profile.updated_at).toLocaleString() : "--"}
                  />
                </Grid>
              </Grid>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle1" gutterBottom>
                Column completeness
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Bars represent non-null counts per column with quick sample values.
              </Typography>
              <Box>
                {profile?.columns?.map((column) => (
                  <ColumnBar key={column.name} profile={column} max={maxRows} />
                ))}
              </Box>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No profile yet. Run profiling to unlock EDA charts and download the data quality report.
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};
