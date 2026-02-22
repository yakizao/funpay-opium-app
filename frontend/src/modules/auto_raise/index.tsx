import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Switch, Button, TextField, Chip, alpha,
  Table, TableHead, TableBody, TableRow, TableCell,
  CircularProgress, Tooltip, IconButton,
} from '@mui/material';
import Grid from '@mui/material/Grid2';
import {
  TrendingUp as RaiseIcon,
  Delete as DeleteIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  PlayArrow as ActiveIcon,
  Timer as TimerIcon,
} from '@mui/icons-material';
import { StatCard } from '../../components/GlowCard';
import { PageHeader } from '../../components/PageHeader';
import { TablePaper } from '../../components/TablePaper';
import { DataTable, type Column } from '../../components/DataTable';
import { useLayout } from '../../components/Layout';
import { usePolling } from '../../hooks/usePolling';
import api from '../../api/client';
import type { ModuleManifest } from '../index';

/* ─── Types ──────────────────────────────────────────── */

interface AutoRaiseConfig {
  enabled: boolean;
  delay_range_minutes: number;
}

interface CategoryResult {
  category_name: string;
  success: boolean;
  skipped?: boolean;
  error?: string;
  wait_seconds?: number | null;
}

interface NextRaiseInfo {
  next_raise_in: number;
  next_raise_at: number;
}

interface AutoRaiseStatus {
  active: boolean;
  raising: boolean;
  enabled: boolean;
  next_raises: Record<string, NextRaiseInfo>;
  last_results: Record<string, CategoryResult>;
}

interface LogEntry {
  timestamp: string;
  category_id: number;
  category_name: string;
  success: boolean;
  error: string | null;
}

/* ─── API helpers ────────────────────────────────────── */

function arApi(accountId: string) {
  const base = `/accounts/${accountId}/modules/auto_raise`;
  return {
    getConfig: () => api.get<AutoRaiseConfig>(`${base}/config`),
    updateConfig: (data: Partial<AutoRaiseConfig>) => api.patch(`${base}/config`, data),
    getStatus: () => api.get<AutoRaiseStatus>(`${base}/status`),
    raiseNow: () => api.post(`${base}/raise`),
    getLog: (limit = 50) => api.get<LogEntry[]>(`${base}/log`, { params: { limit } }),
    clearLog: () => api.delete(`${base}/log`),
  };
}

/* ─── Helpers ────────────────────────────────────────── */

const fmtCountdown = (seconds: number) => {
  if (seconds <= 0) return 'ready';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

/* ─── Dashboard Page ─────────────────────────────────── */

function AutoRaiseDashboard() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [status, setStatus] = useState<AutoRaiseStatus | null>(null);
  const [config, setConfig] = useState<AutoRaiseConfig | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [raising, setRaising] = useState(false);
  const [delayInput, setDelayInput] = useState('');
  const [delayDirty, setDelayDirty] = useState(false);

  const aApi = arApi(accountId!);

  const fetchAll = useCallback(async (silent = false) => {
    if (!accountId) return;
    if (!silent) setLoading(true);
    try {
      const [statusRes, configRes, logRes] = await Promise.all([
        aApi.getStatus(),
        aApi.getConfig(),
        aApi.getLog(100),
      ]);
      setStatus(statusRes.data);
      setConfig(configRes.data);
      setLog(logRes.data);
      if (!delayDirty) {
        setDelayInput(String(configRes.data.delay_range_minutes));
      }
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [accountId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  usePolling(() => fetchAll(true), 5000);

  const handleToggle = async (enabled: boolean) => {
    try {
      await aApi.updateConfig({ enabled });
      await fetchAll(true);
      notify(enabled ? 'autoraise enabled' : 'autoraise disabled', 'success');
    } catch {
      notify('failed to update config', 'error');
    }
  };

  const handleDelaySave = async () => {
    const minutes = parseInt(delayInput, 10);
    if (isNaN(minutes) || minutes < 0) {
      notify('delay must be >= 0', 'error');
      return;
    }
    try {
      await aApi.updateConfig({ delay_range_minutes: minutes });
      setDelayDirty(false);
      await fetchAll(true);
      notify('delay updated', 'success');
    } catch {
      notify('failed to save', 'error');
    }
  };

  const handleRaiseNow = async () => {
    setRaising(true);
    try {
      await aApi.raiseNow();
      await fetchAll(true);
      notify('raise triggered', 'success');
    } catch {
      notify('raise failed', 'error');
    } finally {
      setRaising(false);
    }
  };

  const handleClearLog = async () => {
    try {
      await aApi.clearLog();
      setLog([]);
      notify('log cleared', 'success');
    } catch {
      notify('failed to clear log', 'error');
    }
  };

  /* ─── Derived data ───────────────────────────────── */

  const lastResults = status?.last_results ?? {};
  const nextRaises = status?.next_raises ?? {};
  const totalCategories = Object.keys(lastResults).length;
  const successCount = Object.values(lastResults).filter(r => r.success).length;
  const nextReadyIn = useMemo(() => {
    const values = Object.values(nextRaises);
    if (values.length === 0) return null;
    const min = Math.min(...values.map(v => v.next_raise_in));
    return min;
  }, [nextRaises]);

  /* ─── Log columns for DataTable ──────────────────── */

  const logReversed = useMemo(() => [...log].reverse(), [log]);

  const logColumns: Column<LogEntry>[] = useMemo(() => [
    {
      id: 'status', label: '', width: 30,
      render: (e) => e.success
        ? <SuccessIcon sx={{ fontSize: 14, color: '#22C55E' }} />
        : <ErrorIcon sx={{ fontSize: 14, color: '#EF4444' }} />,
    },
    {
      id: 'time', label: 'time', sortable: true, width: 80,
      sortValue: e => e.timestamp,
      render: (e) => (
        <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
          {e.timestamp?.slice(11, 19) ?? ''}
        </Typography>
      ),
    },
    {
      id: 'category', label: 'category', sortable: true,
      sortValue: e => e.category_name,
      searchValue: e => e.category_name,
      render: (e) => (
        <Typography variant="body2" sx={{ color: 'text.primary' }}>
          {e.category_name}
        </Typography>
      ),
    },
    {
      id: 'result', label: 'result', width: 200,
      render: (e) => (
        <Chip
          size="small"
          label={e.success ? 'raised' : (e.error?.slice(0, 40) ?? 'error')}
          sx={{
            height: 20, fontSize: '0.68rem', fontWeight: 600,
            bgcolor: alpha(e.success ? '#22C55E' : '#EF4444', 0.12),
            color: e.success ? '#22C55E' : '#EF4444',
          }}
        />
      ),
    },
  ], []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress sx={{ color: '#8B5CF6' }} />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="autoraise"
        subtitle={
          <>
            {config?.enabled ? 'active' : 'disabled'}
            {totalCategories > 0 && <span style={{ opacity: 0.5 }}> · {totalCategories} categories</span>}
          </>
        }
        onRefresh={() => fetchAll(true)}
        actions={
          <Button
            size="small"
            variant="contained"
            startIcon={raising ? <CircularProgress size={14} color="inherit" /> : <RaiseIcon />}
            onClick={handleRaiseNow}
            disabled={raising}
          >
            raise now
          </Button>
        }
      />

      {/* Stats */}
      <Grid container spacing={1.5} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            label="status"
            value={config?.enabled ? 'on' : 'off'}
            icon={<ActiveIcon />}
            color={config?.enabled ? '#22C55E' : '#707070'}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            label="categories"
            value={totalCategories}
            icon={<RaiseIcon />}
            color="#8B5CF6"
            subtitle={totalCategories > 0 ? `${successCount} raised` : undefined}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            label="next raise"
            value={nextReadyIn !== null ? fmtCountdown(nextReadyIn) : '-'}
            icon={<TimerIcon />}
            color="#06B6D4"
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            label="log entries"
            value={log.length}
            icon={<ScheduleIcon />}
            color="#F59E0B"
          />
        </Grid>
      </Grid>

      {/* Settings row */}
      <TablePaper sx={{ mb: 2 }}>
        <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>enabled</Typography>
            <Switch
              checked={config?.enabled ?? false}
              onChange={(_, v) => handleToggle(v)}
              sx={{
                '& .MuiSwitch-switchBase.Mui-checked': { color: '#8B5CF6' },
                '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: '#8B5CF6' },
              }}
            />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              label="+ random (min)"
              size="small"
              type="number"
              value={delayInput}
              onChange={e => { setDelayInput(e.target.value); setDelayDirty(true); }}
              sx={{
                width: 140,
                '& .MuiOutlinedInput-root': { bgcolor: 'rgba(255,255,255,0.03)' },
              }}
              slotProps={{ htmlInput: { min: 0 } }}
            />
            {delayDirty && (
              <Button size="small" variant="outlined" onClick={handleDelaySave}>
                save
              </Button>
            )}
          </Box>
        </Box>
      </TablePaper>

      {/* Category Status */}
      {totalCategories > 0 && (
        <TablePaper sx={{ mb: 2 }}>
          <Box sx={{ px: 2, pt: 1.5, pb: 0.5 }}>
            <Typography variant="subtitle2" sx={{
              fontWeight: 700, fontSize: '0.7rem', textTransform: 'uppercase',
              letterSpacing: '0.06em', color: 'text.secondary',
            }}>
              categories
            </Typography>
          </Box>
          <Table size="small">
            <TableHead>
              <TableRow sx={{
                '& .MuiTableCell-head': {
                  fontWeight: 700, fontSize: '0.7rem', textTransform: 'uppercase',
                  letterSpacing: '0.06em', color: 'text.secondary',
                  borderBottom: '1px solid rgba(255,255,255,0.06)', py: 1.2, whiteSpace: 'nowrap',
                },
              }}>
                <TableCell sx={{ width: 30 }}></TableCell>
                <TableCell>category</TableCell>
                <TableCell>status</TableCell>
                <TableCell>next raise</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(lastResults).map(([catId, result]) => {
                const next = nextRaises[catId];
                const nextIn = next ? next.next_raise_in : null;
                const statusColor = result.success ? '#22C55E' : result.skipped ? '#F59E0B' : '#EF4444';
                const statusLabel = result.success ? 'raised' : result.skipped ? 'cooldown' : 'error';
                return (
                  <TableRow
                    key={catId}
                    sx={{
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.02)' },
                      '& .MuiTableCell-root': {
                        borderBottom: '1px solid rgba(255,255,255,0.04)', py: 1.2, fontSize: '0.82rem',
                      },
                    }}
                  >
                    <TableCell>
                      {result.success
                        ? <SuccessIcon sx={{ fontSize: 16, color: '#22C55E' }} />
                        : result.skipped
                          ? <ScheduleIcon sx={{ fontSize: 16, color: '#F59E0B' }} />
                          : <ErrorIcon sx={{ fontSize: 16, color: '#EF4444' }} />}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>
                        {result.category_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                        #{catId}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={statusLabel}
                        sx={{
                          bgcolor: alpha(statusColor, 0.12),
                          color: statusColor,
                          fontWeight: 600, fontSize: '0.7rem', height: 22,
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{
                        color: nextIn !== null && nextIn !== undefined && nextIn <= 0 ? '#22C55E' : 'text.secondary',
                        fontWeight: nextIn !== null && nextIn !== undefined && nextIn <= 0 ? 600 : 400,
                      }}>
                        {nextIn !== null && nextIn !== undefined ? fmtCountdown(nextIn) : '-'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TablePaper>
      )}

      {/* Log */}
      <DataTable
        columns={logColumns}
        rows={logReversed}
        rowKey={(e, i) => `${e.timestamp}-${i}`}
        loading={false}
        emptyMessage="no raise events yet"
        searchPlaceholder="search log..."
        defaultSortColumn="time"
        defaultSortDirection="desc"
        toolbarExtra={
          log.length > 0 ? (
            <Tooltip title="clear log">
              <IconButton size="small" onClick={handleClearLog}>
                <DeleteIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          ) : undefined
        }
      />
    </Box>
  );
}

/* ─── Module Manifest ────────────────────────────────── */

export const autoRaiseManifest: ModuleManifest = {
  name: 'auto_raise',
  displayName: 'autoraise',
  description: 'automatic lot raising for all categories',
  navigation: [
    { label: 'autoraise', path: 'dashboard', icon: <RaiseIcon fontSize="small" /> },
  ],
  routes: [
    { path: 'dashboard', component: AutoRaiseDashboard },
  ],
};
