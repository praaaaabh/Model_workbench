import { Card, CardContent, Chip, List, ListItem, ListItemText, Stack, Typography } from "@mui/material";
import { formatDistanceToNow } from "date-fns";

import { AuditLogEntry } from "../types/audit";

const statusColor: Record<string, "success" | "error" | "default"> = {
  completed: "success",
  failed: "error",
};

export const ActivityFeed = ({ entries }: { entries: AuditLogEntry[] }) => {
  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">Recent Activity</Typography>
          <Chip
            label={`${entries.length} event${entries.length === 1 ? "" : "s"}`}
            size="small"
            color="default"
          />
        </Stack>
        {entries.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No audit activity captured yet.
          </Typography>
        ) : (
          <List>
            {entries.map((entry) => (
              <ListItem key={entry.id} disableGutters divider>
                <ListItemText
                  primary={
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip
                        size="small"
                        label={entry.status}
                        color={statusColor[entry.status] ?? "default"}
                      />
                      <Typography variant="subtitle2">
                        {`${entry.action.replace("_", " ")} (${entry.entity_type})`}
                      </Typography>
                    </Stack>
                  }
                  secondary={
                    <Stack spacing={0.5} mt={0.5}>
                      <Typography variant="body2" color="text.primary">
                        {entry.message || "No details provided"}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
                      </Typography>
                    </Stack>
                  }
                />
                {entry.retries > 0 && <Chip label={`${entry.retries} retr${entry.retries > 1 ? "ies" : "y"}`} size="small" />}
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};
