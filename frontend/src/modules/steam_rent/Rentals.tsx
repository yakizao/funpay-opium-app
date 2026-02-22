import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Chip, alpha, Tooltip, IconButton, Stack,
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField,
  ToggleButtonGroup, ToggleButton,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { useLayout } from '../../components/Layout';
import { PageHeader } from '../../components/PageHeader';
import { DataTable, type Column, type FilterGroup } from '../../components/DataTable';
import { useCountdown } from '../../hooks/useCountdown';
import { usePolling } from '../../hooks/usePolling';
import { steamRentApi, Rental, SteamGame } from './api';

const statusColors: Record<string, string> = {
  active: '#22C55E', expired: '#707070', revoked: '#EF4444',
};

export default function RentalsPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const { formatRemaining, isExpiringSoon } = useCountdown();
  const [rentals, setRentals] = useState<Rental[]>([]);
  const [games, setGames] = useState<SteamGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('active');
  const [filterGame, setFilterGame] = useState('all');

  // Dialogs
  const [timeDialogOpen, setTimeDialogOpen] = useState(false);
  const [timeTarget, setTimeTarget] = useState<Rental | null>(null);
  const [timeDirection, setTimeDirection] = useState<'add' | 'remove'>('add');
  const [timeHours, setTimeHours] = useState('1');
  const [timeMinutes, setTimeMinutes] = useState('0');
  const [terminateTarget, setTerminateTarget] = useState<Rental | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => { load(); }, [accountId]);

  const load = async (silent = false) => {
    if (!accountId) return;
    try {
      const [res, gr] = await Promise.all([
        steamRentApi.getRentals(accountId),
        steamRentApi.getGames(accountId),
      ]);
      setRentals(res.data);
      setGames(gr.data);
    } catch { if (!silent) notify('failed to load rentals', 'error'); }
    finally { setLoading(false); }
  };
  usePolling(() => load(true), 15000, !!accountId);

  const openTimeDialog = (rental: Rental, direction: 'add' | 'remove') => {
    setTimeTarget(rental);
    setTimeDirection(direction);
    setTimeHours('1');
    setTimeMinutes('0');
    setTimeDialogOpen(true);
  };

  const handleModifyTime = async () => {
    if (!accountId || !timeTarget) return;
    const totalMinutes = (parseInt(timeHours) || 0) * 60 + (parseInt(timeMinutes) || 0);
    if (totalMinutes <= 0) { notify('enter a valid time', 'error'); return; }
    const minutes = timeDirection === 'add' ? totalMinutes : -totalMinutes;
    setActionLoading(true);
    try {
      await steamRentApi.modifyRentalTime(accountId, timeTarget.rental_id, minutes);
      notify(`${timeDirection === 'add' ? 'added' : 'removed'} ${totalMinutes} minutes`, 'success');
      setTimeDialogOpen(false);
      load();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      notify(detail || 'failed to modify time', 'error');
    } finally { setActionLoading(false); }
  };

  const handleTerminate = async () => {
    if (!accountId || !terminateTarget) return;
    setActionLoading(true);
    try {
      await steamRentApi.terminateRental(accountId, terminateTarget.rental_id);
      notify('rental terminated', 'success');
      setTerminateTarget(null);
      load();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      notify(detail || 'failed to terminate rental', 'error');
    } finally { setActionLoading(false); }
  };

  const gameFiltered = useMemo(() =>
    filterGame === 'all' ? rentals : rentals.filter(r => r.game_id === filterGame),
  [rentals, filterGame]);

  const active = useMemo(() => gameFiltered.filter(r => r.status === 'active'), [gameFiltered]);
  const history = useMemo(() => gameFiltered.filter(r => r.status !== 'active'), [gameFiltered]);
  const displayed = filterStatus === 'active' ? active : history;
  const showActions = filterStatus === 'active';

  const columns: Column<Rental>[] = useMemo(() => [
    {
      id: 'order', label: 'order', sortable: true, width: 90,
      sortValue: r => r.order_id,
      searchValue: r => r.order_id,
      render: r => (
        <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace', color: 'text.primary' }}>
          #{r.order_id}
        </Typography>
      ),
    },
    {
      id: 'buyer', label: 'buyer', sortable: true,
      sortValue: r => r.buyer_username,
      searchValue: r => `${r.buyer_username} ${r.buyer_id}`,
      render: r => (
        <Box>
          <Typography variant="body2">{r.buyer_username}</Typography>
          <Typography variant="caption" color="text.secondary">ID: {r.buyer_id}</Typography>
        </Box>
      ),
    },
    {
      id: 'game', label: 'game', sortable: true, width: 100,
      sortValue: r => r.game_id,
      render: r => <Chip size="small" label={r.game_id} sx={{ bgcolor: alpha('#06B6D4', 0.1), color: '#22D3EE' }} />,
    },
    {
      id: 'account', label: 'account', sortable: true,
      sortValue: r => r.steam_account_id,
      searchValue: r => r.steam_account_id,
      render: r => <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{r.steam_account_id}</Typography>,
    },
    {
      id: 'credentials', label: 'login / pass',
      searchValue: r => r.delivered_login,
      render: r => (
        <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
          {r.delivered_login} / {r.delivered_password}
        </Typography>
      ),
    },
    {
      id: 'start', label: 'start', sortable: true, width: 140,
      sortValue: r => new Date(r.start_time).getTime(),
      render: r => <Typography variant="caption" color="text.secondary">{new Date(r.start_time).toLocaleString()}</Typography>,
    },
    ...(showActions ? [{
      id: 'remaining', label: 'remaining', sortable: true, width: 110,
      sortValue: (r: Rental) => new Date(r.end_time).getTime(),
      render: (r: Rental) => {
        const timeLeft = formatRemaining(r.end_time);
        const expiring = timeLeft !== 'expired' && isExpiringSoon(r.end_time);
        return (
          <Typography variant="body2" sx={{
            fontWeight: 700, fontFamily: 'monospace',
            color: timeLeft === 'expired' ? 'error.main' : expiring ? 'warning.main' : 'success.main',
          }}>
            {timeLeft}
          </Typography>
        );
      },
    }] as Column<Rental>[] : [{
      id: 'end', label: 'end', sortable: true, width: 140,
      sortValue: (r: Rental) => new Date(r.end_time).getTime(),
      render: (r: Rental) => <Typography variant="caption" color="text.secondary">{new Date(r.end_time).toLocaleString()}</Typography>,
    }] as Column<Rental>[]),
    {
      id: 'bonus', label: 'bonus', sortable: true, width: 70,
      sortValue: r => r.bonus_minutes,
      render: r => r.bonus_minutes > 0
        ? <Chip size="small" label={`+${r.bonus_minutes}m`} sx={{ bgcolor: alpha('#22C55E', 0.1), color: '#22C55E', fontWeight: 600 }} />
        : <Typography variant="caption" color="text.disabled">-</Typography>,
    },
    {
      id: 'status', label: 'status', sortable: true, width: 90,
      sortValue: r => r.status,
      render: r => (
        <Chip size="small" label={r.status} sx={{
          bgcolor: alpha(statusColors[r.status] || '#707070', 0.12),
          color: statusColors[r.status] || '#a0a0a0', fontWeight: 600,
        }} />
      ),
    },
    ...(showActions ? [{
      id: 'actions', label: '', align: 'right' as const, width: 110,
      render: (r: Rental) => (
        <Stack direction="row" spacing={0.5} justifyContent="flex-end">
          <Tooltip title="add time">
            <IconButton size="small" onClick={() => openTimeDialog(r, 'add')} sx={{ color: '#22C55E' }}>
              <AddIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="remove time">
            <IconButton size="small" onClick={() => openTimeDialog(r, 'remove')} sx={{ color: '#F59E0B' }}>
              <RemoveIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="terminate">
            <IconButton size="small" onClick={() => setTerminateTarget(r)} sx={{ color: '#EF4444' }}>
              <StopIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      ),
    }] as Column<Rental>[] : []),
  ], [showActions, formatRemaining, isExpiringSoon]);

  const filterGroups: FilterGroup[] = useMemo(() => {
    const groups: FilterGroup[] = [];
    if (games.length > 0) {
      groups.push({
        label: 'game', value: filterGame, onChange: setFilterGame,
        options: [
          { label: 'all', value: 'all' },
          ...games.map(g => ({ label: g.game_id, value: g.game_id, color: '#06B6D4' })),
        ],
      });
    }
    groups.push({
      label: 'status', value: filterStatus, onChange: setFilterStatus,
      options: [
        { label: 'active', value: 'active', count: active.length, color: '#22C55E' },
        { label: 'history', value: 'history', count: history.length, color: '#707070' },
      ],
    });
    return groups;
  }, [games, filterGame, filterStatus, active.length, history.length]);

  return (
    <Box>
      <PageHeader
        title="rentals"
        subtitle={`${active.length} active · ${history.length} completed`}
        onRefresh={load}
      />

      <DataTable
        columns={columns}
        rows={displayed}
        rowKey={r => r.rental_id}
        loading={loading}
        emptyMessage={filterStatus === 'active' ? 'no active rentals' : 'no rental history'}
        filters={filterGroups}
        searchPlaceholder="search rentals..."
        defaultSortColumn={showActions ? 'remaining' : 'start'}
        defaultSortDirection={showActions ? 'asc' : 'desc'}
      />

      {/* Time Modification Dialog */}
      <Dialog open={timeDialogOpen} onClose={() => setTimeDialogOpen(false)} maxWidth="xs" fullWidth
        PaperProps={{ sx: { bgcolor: '#141414', border: '1px solid rgba(255,255,255,0.1)' } }}>
        <DialogTitle>{timeDirection === 'add' ? 'add time' : 'remove time'}</DialogTitle>
        <DialogContent>
          {timeTarget && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Rental #{timeTarget.order_id} · {timeTarget.game_id} · {timeTarget.buyer_username}
            </Typography>
          )}
          <ToggleButtonGroup
            value={timeDirection} exclusive
            onChange={(_, v) => v && setTimeDirection(v)}
            size="small" sx={{ mb: 2, width: '100%' }}
          >
            <ToggleButton value="add" sx={{ flex: 1, color: '#22C55E', '&.Mui-selected': { bgcolor: alpha('#22C55E', 0.12), color: '#22C55E' } }}>+ add</ToggleButton>
            <ToggleButton value="remove" sx={{ flex: 1, color: '#F59E0B', '&.Mui-selected': { bgcolor: alpha('#F59E0B', 0.12), color: '#F59E0B' } }}>− remove</ToggleButton>
          </ToggleButtonGroup>
          <Stack direction="row" spacing={2}>
            <TextField label="Hours" type="number" size="small" fullWidth value={timeHours} onChange={e => setTimeHours(e.target.value)} inputProps={{ min: 0 }} />
            <TextField label="Minutes" type="number" size="small" fullWidth value={timeMinutes} onChange={e => setTimeMinutes(e.target.value)} inputProps={{ min: 0, max: 59 }} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTimeDialogOpen(false)}>cancel</Button>
          <Button onClick={handleModifyTime} disabled={actionLoading} variant="contained" color={timeDirection === 'add' ? 'success' : 'warning'}>
            {actionLoading ? 'saving...' : timeDirection === 'add' ? 'add time' : 'remove time'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Terminate Confirmation */}
      <Dialog open={!!terminateTarget} onClose={() => setTerminateTarget(null)} maxWidth="xs" fullWidth
        PaperProps={{ sx: { bgcolor: '#141414', border: '1px solid rgba(255,255,255,0.1)' } }}>
        <DialogTitle>terminate rental</DialogTitle>
        <DialogContent>
          {terminateTarget && (
            <Typography variant="body2" color="text.secondary">
              are you sure you want to terminate rental #{terminateTarget.order_id} for{' '}
              <strong>{terminateTarget.buyer_username}</strong> ({terminateTarget.game_id})?
              the steam account will be freed immediately.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTerminateTarget(null)}>cancel</Button>
          <Button onClick={handleTerminate} disabled={actionLoading} variant="contained" color="error">
            {actionLoading ? 'terminating...' : 'terminate'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
