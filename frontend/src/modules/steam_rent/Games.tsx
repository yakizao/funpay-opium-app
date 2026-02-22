import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Button, IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
  DialogActions, TextField, Chip, alpha,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  AcUnit as FreezeIcon,
} from '@mui/icons-material';
import { useLayout } from '../../components/Layout';
import { PageHeader } from '../../components/PageHeader';
import { DataTable, type Column, type FilterGroup } from '../../components/DataTable';
import { usePolling } from '../../hooks/usePolling';
import { steamRentApi, SteamGame } from './api';
import { ProxySettingsField, DEFAULT_PROXY_SETTINGS } from './ProxySettingsField';
import type { ProxySettings } from './api';

export default function GamesPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [games, setGames] = useState<SteamGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editGame, setEditGame] = useState<SteamGame | null>(null);
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => { load(); }, [accountId]);

  const load = async (silent = false) => {
    if (!accountId) return;
    try {
      const res = await steamRentApi.getGames(accountId);
      setGames(res.data);
    } catch { if (!silent) notify('failed to load games', 'error'); }
    finally { setLoading(false); }
  };
  usePolling(() => load(true), 30000, !!accountId);

  const handleDelete = async (gameId: string) => {
    if (!accountId || !confirm(`Delete game "${gameId}"?`)) return;
    try {
      await steamRentApi.deleteGame(accountId, gameId);
      notify('game deleted', 'success');
      load();
    } catch { notify('failed to delete', 'error'); }
  };

  const handleFreeze = async (gameId: string) => {
    if (!accountId) return;
    try {
      const res = await steamRentApi.freezeGame(accountId, gameId);
      notify(res.data.frozen ? 'game frozen' : 'game unfrozen', 'success');
      load();
    } catch { notify('failed to toggle freeze', 'error'); }
  };

  const filtered = useMemo(() => {
    if (filterStatus === 'all') return games;
    if (filterStatus === 'active') return games.filter(g => !g.frozen);
    return games.filter(g => g.frozen);
  }, [games, filterStatus]);

  const columns: Column<SteamGame>[] = useMemo(() => [
    {
      id: 'game_id', label: 'game ID', sortable: true,
      sortValue: g => g.game_id,
      searchValue: g => g.game_id,
      render: g => (
        <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>{g.game_id}</Typography>
      ),
    },
    {
      id: 'aliases', label: 'aliases', sortable: true,
      sortValue: g => g.aliases.join(', '),
      searchValue: g => g.aliases.join(' '),
      render: g => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {g.aliases.length > 0 ? g.aliases.map((alias, i) => (
            <Chip key={i} size="small" label={alias} sx={{ fontSize: '0.72rem', bgcolor: alpha('#06B6D4', 0.1), color: '#22D3EE' }} />
          )) : (
            <Typography variant="caption" color="text.secondary">no aliases</Typography>
          )}
        </Box>
      ),
    },
    {
      id: 'status', label: 'status', sortable: true, width: 100,
      sortValue: g => g.frozen ? 1 : 0,
      render: g => (
        <Chip size="small" label={g.frozen ? 'frozen' : 'active'} sx={{
          bgcolor: alpha(g.frozen ? '#06B6D4' : '#22C55E', 0.12),
          color: g.frozen ? '#06B6D4' : '#22C55E',
          fontWeight: 600,
        }} />
      ),
    },
    {
      id: 'actions', label: '', align: 'right', width: 120,
      render: g => (
        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
          <Tooltip title="edit"><IconButton size="small" onClick={() => { setEditGame(g); setFormOpen(true); }}><EditIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title={g.frozen ? 'unfreeze' : 'freeze'}><IconButton size="small" onClick={() => handleFreeze(g.game_id)}><FreezeIcon fontSize="small" sx={{ color: g.frozen ? '#06B6D4' : undefined }} /></IconButton></Tooltip>
          <Tooltip title="delete"><IconButton size="small" onClick={() => handleDelete(g.game_id)} color="error"><DeleteIcon fontSize="small" /></IconButton></Tooltip>
        </Box>
      ),
    },
  ], []);

  const filterGroups: FilterGroup[] = useMemo(() => [{
    label: 'status', value: filterStatus, onChange: setFilterStatus,
    options: [
      { label: 'all', value: 'all', count: games.length },
      { label: 'active', value: 'active', count: games.filter(g => !g.frozen).length, color: '#22C55E' },
      { label: 'frozen', value: 'frozen', count: games.filter(g => g.frozen).length, color: '#06B6D4' },
    ],
  }], [games, filterStatus]);

  return (
    <Box>
      <PageHeader
        title="games"
        subtitle={`${games.length} games configured`}
        onRefresh={load}
        actions={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditGame(null); setFormOpen(true); }}>add game</Button>
        }
      />

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={g => g.game_id}
        loading={loading}
        emptyMessage="no games configured. add a game to start."
        filters={filterGroups}
        searchPlaceholder="search games..."
        defaultSortColumn="game_id"
      />

      <GameFormDialog
        open={formOpen}
        game={editGame}
        accountId={accountId!}
        onClose={() => { setFormOpen(false); setEditGame(null); }}
        onSuccess={() => { load(); notify(editGame ? 'game updated' : 'game created', 'success'); setFormOpen(false); setEditGame(null); }}
      />
    </Box>
  );
}

function GameFormDialog({ open, game, accountId, onClose, onSuccess }: {
  open: boolean; game: SteamGame | null; accountId: string;
  onClose: () => void; onSuccess: () => void;
}) {
  const { notify } = useLayout();
  const [gameId, setGameId] = useState('');
  const [aliases, setAliases] = useState('');
  const [proxySettings, setProxySettings] = useState<ProxySettings>(DEFAULT_PROXY_SETTINGS);

  useEffect(() => {
    if (game) {
      setGameId(game.game_id);
      setAliases(game.aliases.join(', '));
      setProxySettings(
        game.proxy_settings
          ? { ...DEFAULT_PROXY_SETTINGS, ...(game.proxy_settings as unknown as ProxySettings) }
          : DEFAULT_PROXY_SETTINGS
      );
    } else {
      setGameId('');
      setAliases('');
      setProxySettings(DEFAULT_PROXY_SETTINGS);
    }
  }, [game, open]);

  const handleSubmit = async () => {
    try {
      const payload = {
        game_id: gameId.trim(),
        aliases: aliases.split(',').map(s => s.trim()).filter(Boolean),
        proxy_settings: (proxySettings.mode === 'direct' ? null : proxySettings) as Record<string, unknown> | null,
      };
      if (game) {
        await steamRentApi.updateGame(accountId, game.game_id, payload);
      } else {
        await steamRentApi.createGame(accountId, payload as SteamGame);
      }
      onSuccess();
    } catch { notify('failed to save game', 'error'); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{game ? 'edit game' : 'add game'}</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <TextField
          fullWidth label="game ID" value={gameId}
          onChange={e => setGameId(e.target.value)}
          disabled={!!game}
          sx={{ mb: 2 }}
          helperText="unique identifier (e.g. cs2, rust)"
        />
        <TextField
          fullWidth label="aliases" value={aliases}
          onChange={e => setAliases(e.target.value)}
          helperText="comma-separated alternative names (e.g. Counter-Strike 2, CS:GO)"
        />
        <ProxySettingsField
          value={proxySettings}
          onChange={setProxySettings}
          accountId={accountId}
          label="proxy settings (overrides account-level)"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!gameId.trim()}>{game ? 'save' : 'create'}</Button>
      </DialogActions>
    </Dialog>
  );
}
