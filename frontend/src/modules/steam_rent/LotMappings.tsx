import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Button, IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
  DialogActions, TextField, Chip, alpha, Select, MenuItem, FormControl, InputLabel,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { useLayout } from '../../components/Layout';
import { PageHeader } from '../../components/PageHeader';
import { DataTable, type Column, type FilterGroup } from '../../components/DataTable';
import { usePolling } from '../../hooks/usePolling';
import { steamRentApi, LotMapping, SteamGame } from './api';

const fmtMin = (m: number) => {
  if (!m) return '0m';
  const h = Math.floor(m / 60);
  const min = m % 60;
  if (h && min) return `${h}h ${min}m`;
  if (h) return `${h}h`;
  return `${min}m`;
};

export default function LotMappingsPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [mappings, setMappings] = useState<LotMapping[]>([]);
  const [games, setGames] = useState<SteamGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [filterGame, setFilterGame] = useState<string>('all');

  useEffect(() => { load(); }, [accountId]);

  const load = async (silent = false) => {
    if (!accountId) return;
    try {
      const [mr, gr] = await Promise.all([
        steamRentApi.getLotMappings(accountId),
        steamRentApi.getGames(accountId),
      ]);
      setMappings(mr.data);
      setGames(gr.data);
    } catch { if (!silent) notify('failed to load lot mappings', 'error'); }
    finally { setLoading(false); }
  };
  usePolling(() => load(true), 30000, !!accountId);

  const handleDelete = async (index: number) => {
    if (!accountId || !confirm('Delete this lot mapping?')) return;
    try {
      await steamRentApi.deleteLotMapping(accountId, index);
      notify('lot mapping deleted', 'success');
      load();
    } catch { notify('failed to delete', 'error'); }
  };

  const filtered = useMemo(() => {
    if (filterGame === 'all') return mappings;
    return mappings.filter(m => m.game_id === filterGame);
  }, [mappings, filterGame]);

  // We need the original index for edit/delete ops so attach it
  type IndexedMapping = LotMapping & { _idx: number };
  const indexedFiltered: IndexedMapping[] = useMemo(() =>
    filtered.map(m => ({ ...m, _idx: mappings.indexOf(m) })),
  [filtered, mappings]);

  const columns: Column<IndexedMapping>[] = useMemo(() => [
    {
      id: 'idx', label: '#', width: 50,
      sortable: true,
      sortValue: m => m._idx,
      render: m => <Typography variant="caption" color="text.secondary">{m._idx + 1}</Typography>,
    },
    {
      id: 'lot_pattern', label: 'lot name', sortable: true,
      sortValue: m => m.lot_pattern,
      searchValue: m => m.lot_pattern,
      render: m => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.primary', fontWeight: 500 }}>
          {m.lot_pattern}
        </Typography>
      ),
    },
    {
      id: 'game_id', label: 'game', sortable: true, width: 110,
      sortValue: m => m.game_id,
      searchValue: m => m.game_id,
      render: m => (
        <Chip size="small" label={m.game_id} sx={{ bgcolor: alpha('#06B6D4', 0.1), color: '#22D3EE', fontWeight: 500 }} />
      ),
    },
    {
      id: 'rent_time', label: 'rent time', sortable: true, width: 100,
      sortValue: m => m.rent_minutes,
      render: m => (
        <Typography variant="body2" sx={{ fontWeight: 600, color: '#8B5CF6' }}>
          {fmtMin(m.rent_minutes)}
        </Typography>
      ),
    },
    {
      id: 'bonus_time', label: 'bonus', sortable: true, width: 100,
      sortValue: m => m.bonus_minutes,
      render: m => (
        <Typography variant="body2" sx={{ fontWeight: 600, color: '#22C55E' }}>
          {fmtMin(m.bonus_minutes)}
        </Typography>
      ),
    },
    {
      id: 'min_rating', label: 'min rating', sortable: true, width: 90,
      sortValue: m => m.min_rating_for_bonus || 0,
      render: m => (
        <Typography variant="body2" color="text.secondary">
          {m.min_rating_for_bonus || '-'}
        </Typography>
      ),
    },
    {
      id: 'actions', label: '', align: 'right', width: 90,
      render: m => (
        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
          <Tooltip title="edit"><IconButton size="small" onClick={() => { setEditIndex(m._idx); setFormOpen(true); }}><EditIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="delete"><IconButton size="small" onClick={() => handleDelete(m._idx)} color="error"><DeleteIcon fontSize="small" /></IconButton></Tooltip>
        </Box>
      ),
    },
  ], []);

  const filterGroups: FilterGroup[] = useMemo(() => {
    if (games.length === 0) return [];
    return [{
      label: 'game', value: filterGame, onChange: setFilterGame,
      options: [
        { label: 'all', value: 'all', count: mappings.length },
        ...games.map(g => ({
          label: g.game_id, value: g.game_id,
          count: mappings.filter(m => m.game_id === g.game_id).length,
          color: '#06B6D4',
        })),
      ],
    }];
  }, [games, filterGame, mappings]);

  return (
    <Box>
      <PageHeader
        title="lot mappings"
        subtitle={`${mappings.length} mappings configured`}
        onRefresh={load}
        actions={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditIndex(null); setFormOpen(true); }}>add mapping</Button>
        }
      />

      <DataTable
        columns={columns}
        rows={indexedFiltered}
        rowKey={m => `${m._idx}-${m.lot_pattern}`}
        loading={loading}
        emptyMessage="no lot mappings. add one to link funpay lots to games."
        filters={filterGroups}
        searchPlaceholder="search lot mappings..."
        defaultSortColumn="idx"
      />

      <LotMappingFormDialog
        open={formOpen}
        mapping={editIndex !== null ? mappings[editIndex] : null}
        editIndex={editIndex}
        games={games}
        accountId={accountId!}
        onClose={() => { setFormOpen(false); setEditIndex(null); }}
        onSuccess={() => { load(); notify(editIndex !== null ? 'mapping updated' : 'mapping created', 'success'); setFormOpen(false); setEditIndex(null); }}
      />
    </Box>
  );
}

function LotMappingFormDialog({ open, mapping, editIndex, games, accountId, onClose, onSuccess }: {
  open: boolean; mapping: LotMapping | null; editIndex: number | null;
  games: SteamGame[]; accountId: string;
  onClose: () => void; onSuccess: () => void;
}) {
  const { notify } = useLayout();
  const [form, setForm] = useState<LotMapping>({
    lot_pattern: '', game_id: '', rent_minutes: 0,
    bonus_minutes: 0, min_rating_for_bonus: 4,
  });

  useEffect(() => {
    if (mapping) {
      setForm({ ...mapping });
    } else {
      setForm({ lot_pattern: '', game_id: '', rent_minutes: 0, bonus_minutes: 0, min_rating_for_bonus: 4 });
    }
  }, [mapping, open]);

  const handleSubmit = async () => {
    try {
      if (editIndex !== null) {
        await steamRentApi.updateLotMapping(accountId, editIndex, form);
      } else {
        await steamRentApi.createLotMapping(accountId, form);
      }
      onSuccess();
    } catch { notify('failed to save mapping', 'error'); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{mapping ? 'edit lot mapping' : 'add lot mapping'}</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <TextField
          fullWidth label="lot name" value={form.lot_pattern}
          onChange={e => setForm({ ...form, lot_pattern: e.target.value })}
          sx={{ mb: 2 }}
          helperText="funpay lot name"
        />
        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel>game</InputLabel>
          <Select
            value={form.game_id}
            label="Game"
            onChange={e => setForm({ ...form, game_id: e.target.value as string })}
          >
            {games.map(g => (
              <MenuItem key={g.game_id} value={g.game_id}>{g.game_id}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.secondary' }}>rent duration</Typography>
        <Box sx={{ display: 'flex', gap: 1.5, mb: 2, alignItems: 'center' }}>
          <TextField
            label="hours" type="number" value={Math.floor(form.rent_minutes / 60)}
            onChange={e => setForm({ ...form, rent_minutes: (parseInt(e.target.value) || 0) * 60 + (form.rent_minutes % 60) })}
            inputProps={{ min: 0 }} sx={{ flex: 1 }}
          />
          <TextField
            label="minutes" type="number" value={form.rent_minutes % 60}
            onChange={e => setForm({ ...form, rent_minutes: Math.floor(form.rent_minutes / 60) * 60 + (parseInt(e.target.value) || 0) })}
            inputProps={{ min: 0, max: 59 }} sx={{ flex: 1 }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
            = {fmtMin(form.rent_minutes)}
          </Typography>
        </Box>

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.secondary' }}>bonus for review</Typography>
        <Box sx={{ display: 'flex', gap: 1.5, mb: 2, alignItems: 'center' }}>
          <TextField
            label="hours" type="number" value={Math.floor(form.bonus_minutes / 60)}
            onChange={e => setForm({ ...form, bonus_minutes: (parseInt(e.target.value) || 0) * 60 + (form.bonus_minutes % 60) })}
            inputProps={{ min: 0 }} sx={{ flex: 1 }}
          />
          <TextField
            label="minutes" type="number" value={form.bonus_minutes % 60}
            onChange={e => setForm({ ...form, bonus_minutes: Math.floor(form.bonus_minutes / 60) * 60 + (parseInt(e.target.value) || 0) })}
            inputProps={{ min: 0, max: 59 }} sx={{ flex: 1 }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
            = {fmtMin(form.bonus_minutes)}
          </Typography>
        </Box>

        <TextField
          fullWidth label="min rating for bonus" type="number"
          value={form.min_rating_for_bonus}
          onChange={e => setForm({ ...form, min_rating_for_bonus: parseInt(e.target.value) || 0 })}
          helperText="minimum buyer rating to receive review bonus. 0 = no restriction."
          inputProps={{ min: 0 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!form.lot_pattern || !form.game_id}>
          {mapping ? 'save' : 'create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
