import { ReactNode } from 'react';
import { Paper, type SxProps, type Theme } from '@mui/material';

interface TablePaperProps {
  children: ReactNode;
  sx?: SxProps<Theme>;
}

/**
 * Standard dark paper wrapper for tables.
 * Eliminates the repeated `bgcolor: '#141414', border: '1px solid rgba(255,255,255,0.06)'...` pattern.
 */
export function TablePaper({ children, sx }: TablePaperProps) {
  return (
    <Paper
      sx={{
        bgcolor: '#141414',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 2,
        overflow: 'hidden',
        ...sx,
      }}
    >
      {children}
    </Paper>
  );
}
