import { ChangeEvent, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";

import { uploadDataset } from "../api/datasets";
import { DatasetResponse } from "../types/datasets";

interface DatasetUploadCardProps {
  onUploadSuccess: (dataset: DatasetResponse) => void;
}

export const DatasetUploadCard = ({ onUploadSuccess }: DatasetUploadCardProps) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => uploadDataset(file, setProgress),
    onSuccess: (data) => {
      setError(null);
      setProgress(100);
      onUploadSuccess(data);
    },
    onError: (err: unknown) => {
      setError((err as Error).message);
      setProgress(0);
    },
  });

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setSelectedFile(event.target.files[0]);
      setProgress(0);
      setError(null);
    }
  };

  const handleUpload = () => {
    if (selectedFile) {
      mutation.mutate(selectedFile);
    }
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6">Upload a dataset</Typography>
          <Typography variant="body2" color="text.secondary">
            Upload a CSV file to infer its schema and configure mappings to standard variables.
          </Typography>
          <Box>
            <Button variant="outlined" component="label">
              Choose file
              <input type="file" hidden accept=".csv,text/csv" onChange={handleFileChange} />
            </Button>
            <Typography variant="body2" sx={{ mt: 1 }}>
              {selectedFile ? selectedFile.name : "No file selected"}
            </Typography>
          </Box>
          {mutation.isPending && <LinearProgress variant="determinate" value={progress} />}
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
        </Stack>
      </CardContent>
      <CardActions>
        <Button variant="contained" onClick={handleUpload} disabled={!selectedFile || mutation.isPending}>
          {mutation.isPending ? "Uploading..." : "Upload"}
        </Button>
      </CardActions>
    </Card>
  );
};
