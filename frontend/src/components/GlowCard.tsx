import { ReactNode } from 'react';
import { Card, CardContent, Box, Typography, alpha } from '@mui/material';

interface GlowCardProps {
  children: ReactNode;
  glow?: string;
  onClick?: () => void;
  sx?: object;
}

export default function GlowCard({ children, glow = '#8B5CF6', onClick, sx }: GlowCardProps) {
  return (
    <Card
      onClick={onClick}
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.25s ease',
        '&:hover': {
          borderColor: alpha(glow, 0.3),
          boxShadow: `0 0 24px ${alpha(glow, 0.08)}, 0 0 48px ${alpha(glow, 0.04)}`,
          transform: onClick ? 'translateY(-2px)' : 'none',
        },
        ...sx,
      }}
    >
      {children}
    </Card>
  );
}

interface StatCardProps {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  color?: string;
  subtitle?: string;
}

export function StatCard({ label, value, icon, color = '#8B5CF6', subtitle }: StatCardProps) {
  return (
    <GlowCard glow={color}>
      <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'lowercase', letterSpacing: '0.08em', fontWeight: 600 }}>
              {label}
            </Typography>
            <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: 'text.primary', display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" sx={{ color: alpha(color, 0.8), mt: 0.5, display: 'block' }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box sx={{
            p: 1.2,
            borderRadius: 2.5,
            bgcolor: alpha(color, 0.1),
            color: color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {icon}
          </Box>
        </Box>
      </CardContent>
    </GlowCard>
  );
}

interface StatusDotProps {
  status: 'running' | 'stopped' | 'error' | 'reconnecting' | 'initializing';
  size?: number;
}

export function StatusDot({ status, size = 8 }: StatusDotProps) {
  const colorMap: Record<string, string> = {
    running: '#22C55E',
    stopped: '#707070',
    error: '#EF4444',
    reconnecting: '#F59E0B',
    initializing: '#3B82F6',
  };
  const color = colorMap[status] || '#707070';

  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: '50%',
        bgcolor: color,
        boxShadow: status === 'running' || status === 'error' || status === 'reconnecting'
          ? `0 0 ${size}px ${alpha(color, 0.6)}`
          : 'none',
        animation: status === 'reconnecting' || status === 'initializing'
          ? 'pulse 1.5s ease-in-out infinite'
          : 'none',
        '@keyframes pulse': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.4 },
        },
      }}
    />
  );
}

export function stateToStatus(state: string): StatusDotProps['status'] {
  const s = state.toLowerCase();
  if (s === 'running') return 'running';
  if (s === 'error') return 'error';
  if (s === 'reconnecting') return 'reconnecting';
  if (s === 'initializing' || s === 'created' || s === 'ready') return 'initializing';
  return 'stopped';
}
