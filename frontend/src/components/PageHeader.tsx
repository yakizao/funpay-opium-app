import { ReactNode } from 'react';
import { Box, Typography, Tooltip, IconButton } from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  onRefresh?: () => void;
  actions?: ReactNode;
}

/**
 * Standard page header with title, optional subtitle, refresh button and custom actions.
 * Replaces the repeated Box+Typography pattern across all pages.
 */
export function PageHeader({ title, subtitle, onRefresh, actions }: PageHeaderProps) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>{title}</Typography>
        {subtitle && (
          <Typography variant="body2" sx={{ mt: 0.5 }}>{subtitle}</Typography>
        )}
      </Box>
      <Box sx={{ display: 'flex', gap: 1 }}>
        {onRefresh && (
          <Tooltip title="refresh">
            <IconButton onClick={onRefresh} sx={{ bgcolor: 'rgba(255,255,255,0.04)' }}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        )}
        {actions}
      </Box>
    </Box>
  );
}
