import { Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";

import { ColumnSchema } from "../types/datasets";

interface SchemaPreviewTableProps {
  columns: ColumnSchema[];
}

export const SchemaPreviewTable = ({ columns }: SchemaPreviewTableProps) => {
  if (columns.length === 0) {
    return <Typography variant="body2">No columns detected.</Typography>;
  }

  return (
    <TableContainer component={Paper} sx={{ mt: 2 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Column</TableCell>
            <TableCell>Inferred Type</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {columns.map((column) => (
            <TableRow key={column.name}>
              <TableCell>{column.name}</TableCell>
              <TableCell>{column.inferred_type}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};
