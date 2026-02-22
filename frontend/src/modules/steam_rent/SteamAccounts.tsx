import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Button, IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
  DialogActions, TextField, Chip, alpha, Menu, MenuItem, ListItemIcon, ListItemText,
  Switch, FormControlLabel, Select, InputLabel, FormControl,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  MoreVert as MoreIcon,
  VpnKey as GuardIcon,
  LockReset as PasswordIcon,
  PhonelinkErase as KickIcon,
  FileUpload as ImportIcon,
  ContentCopy as CopyIcon,
  AcUnit as FreezeIcon,
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import { useLayout } from '../../components/Layout';
import { PageHeader } from '../../components/PageHeader';
import { DataTable, type Column, type FilterGroup } from '../../components/DataTable';
import { usePolling } from '../../hooks/usePolling';
import { steamRentApi, SteamAccount, SteamGame } from './api';
import { ProxySettingsField, DEFAULT_PROXY_SETTINGS } from './ProxySettingsField';
import type { ProxySettings } from './api';

export default function SteamAccountsPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [accounts, setAccounts] = useState<SteamAccount[]>([]);
  const [games, setGames] = useState<SteamGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [editAccount, setEditAccount] = useState<SteamAccount | null>(null);
  const [guardDialog, setGuardDialog] = useState<{ open: boolean; steamId: string; code: string }>({ open: false, steamId: '', code: '' });
  const [passwordDialog, setPasswordDialog] = useState<{ open: boolean; steamId: string }>({ open: false, steamId: '' });
  const [showPassDialog, setShowPassDialog] = useState<{ open: boolean; steamId: string; password: string; visible: boolean; loading: boolean }>({ open: false, steamId: '', password: '', visible: false, loading: false });
  const [mafileDialog, setMafileDialog] = useState<{ open: boolean; steamId: string }>({ open: false, steamId: '' });
  const [menuAnchor, setMenuAnchor] = useState<{ el: HTMLElement | null; steamId: string }>({ el: null, steamId: '' });
  const [filterGame, setFilterGame] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => { load(); }, [accountId]);

  const load = async (silent = false) => {
    if (!accountId) return;
    try {
      const [accRes, gamesRes] = await Promise.all([
        steamRentApi.getSteamAccounts(accountId),
        steamRentApi.getGames(accountId),
      ]);
      setAccounts(accRes.data);
      setGames(gamesRes.data);
    } catch { if (!silent) notify('failed to load steam accounts', 'error'); }
    finally { setLoading(false); }
  };
  usePolling(() => load(true), 30000, !!accountId);

  const handleDelete = async (steamId: string) => {
    if (!accountId || !confirm(`Delete steam account "${steamId}"?`)) return;
    try {
      await steamRentApi.deleteSteamAccount(accountId, steamId);
      notify('steam account deleted', 'success');
      load();
    } catch { notify('failed to delete', 'error'); }
  };

  const handleGuardCode = async (steamId: string) => {
    if (!accountId) return;
    try {
      const res = await steamRentApi.getGuardCode(accountId, steamId);
      setGuardDialog({ open: true, steamId, code: res.data.code });
    } catch { notify('failed to generate guard code', 'error'); }
    setMenuAnchor({ el: null, steamId: '' });
  };

  const handleKick = async (steamId: string) => {
    if (!accountId) return;
    try {
      await steamRentApi.kickSessions(accountId, steamId);
      notify('sessions kicked', 'success');
    } catch { notify('failed to kick sessions', 'error'); }
    setMenuAnchor({ el: null, steamId: '' });
  };

  const handleFreeze = async (steamId: string) => {
    if (!accountId) return;
    try {
      const res = await steamRentApi.freezeSteamAccount(accountId, steamId);
      notify(res.data.frozen ? 'account frozen' : 'account unfrozen', 'success');
      load();
    } catch { notify('failed to toggle freeze', 'error'); }
  };

  const filtered = useMemo(() => {
    return accounts.filter(acc => {
      if (filterGame !== 'all' && !acc.game_ids.includes(filterGame)) return false;
      if (filterStatus === 'free' && (acc.status !== 'free' || acc.frozen)) return false;
      if (filterStatus === 'rented' && (acc.status !== 'rented' && !acc.frozen)) return false;
      if (filterStatus === 'frozen' && !acc.frozen) return false;
      return true;
    });
  }, [accounts, filterGame, filterStatus]);

  const columns: Column<SteamAccount>[] = useMemo(() => [
    {
      id: 'login', label: 'login', sortable: true,
      sortValue: a => a.login,
      searchValue: a => a.login,
      render: a => (
        <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary', fontFamily: 'monospace' }}>
          {a.login}
        </Typography>
      ),
    },
    {
      id: 'game', label: 'game', sortable: true,
      sortValue: a => a.game_ids.join(','),
      searchValue: a => a.game_ids.join(' '),
      render: a => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {a.game_ids.map(gid => (
            <Chip key={gid} size="small" label={gid} sx={{ bgcolor: alpha('#06B6D4', 0.1), color: '#22D3EE' }} />
          ))}
        </Box>
      ),
    },
    {
      id: 'status', label: 'status', sortable: true, width: 100,
      sortValue: a => a.frozen ? 'frozen' : a.status,
      render: a => (
        <Chip size="small" label={a.frozen ? 'frozen' : a.status} sx={{
          bgcolor: alpha(a.frozen ? '#06B6D4' : a.status === 'free' ? '#22C55E' : '#F59E0B', 0.12),
          color: a.frozen ? '#06B6D4' : a.status === 'free' ? '#22C55E' : '#F59E0B',
          fontWeight: 600,
        }} />
      ),
    },
    {
      id: 'mafile', label: 'mafile', width: 80,
      sortValue: a => a.has_mafile ? 1 : 0,
      sortable: true,
      render: a => (
        <Chip size="small" label={a.has_mafile ? 'Yes' : 'No'} sx={{
          bgcolor: alpha(a.has_mafile ? '#22C55E' : '#707070', 0.12),
          color: a.has_mafile ? '#22C55E' : '#a0a0a0',
        }} />
      ),
    },
    {
      id: 'change_pwd', label: 'chg pwd', width: 80,
      render: a => (
        <Chip size="small" label={a.change_password_on_rent ? 'On' : 'Off'} sx={{
          bgcolor: alpha(a.change_password_on_rent ? '#8B5CF6' : '#707070', 0.12),
          color: a.change_password_on_rent ? '#A78BFA' : '#a0a0a0',
        }} />
      ),
    },
    {
      id: 'kick', label: 'kick', width: 80,
      render: a => (
        <Chip size="small" label={a.kick_devices_on_rent ? 'On' : 'Off'} sx={{
          bgcolor: alpha(a.kick_devices_on_rent ? '#8B5CF6' : '#707070', 0.12),
          color: a.kick_devices_on_rent ? '#A78BFA' : '#a0a0a0',
        }} />
      ),
    },
    {
      id: 'actions', label: '', align: 'right', width: 80,
      render: a => (
        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
          <Tooltip title="edit">
            <IconButton size="small" onClick={() => setEditAccount(a)}><EditIcon fontSize="small" /></IconButton>
          </Tooltip>
          <IconButton size="small" onClick={e => setMenuAnchor({ el: e.currentTarget, steamId: a.id })}>
            <MoreIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ], []);

  const filterGroups: FilterGroup[] = useMemo(() => {
    const groups: FilterGroup[] = [];
    if (games.length > 0) {
      groups.push({
        label: 'game', value: filterGame, onChange: setFilterGame,
        options: [
          { label: 'all', value: 'all', count: accounts.length },
          ...games.map(g => ({
            label: g.game_id, value: g.game_id,
            count: accounts.filter(a => a.game_ids.includes(g.game_id)).length,
            color: '#06B6D4',
          })),
        ],
      });
    }
    groups.push({
      label: 'status', value: filterStatus, onChange: setFilterStatus,
      options: [
        { label: 'all', value: 'all', count: accounts.length },
        { label: 'free', value: 'free', count: accounts.filter(a => a.status === 'free' && !a.frozen).length, color: '#22C55E' },
        { label: 'rented', value: 'rented', count: accounts.filter(a => a.status === 'rented').length, color: '#F59E0B' },
        { label: 'frozen', value: 'frozen', count: accounts.filter(a => a.frozen).length, color: '#06B6D4' },
      ],
    });
    return groups;
  }, [games, filterGame, filterStatus, accounts]);

  return (
    <Box>
      <PageHeader
        title="steam accounts"
        subtitle={`${accounts.length} accounts configured`}
        onRefresh={load}
        actions={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>add account</Button>
        }
      />

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={a => a.id}
        loading={loading}
        emptyMessage="no steam accounts. add one to start renting."
        filters={filterGroups}
        searchPlaceholder="search accounts..."
        defaultSortColumn="login"
      />

      {/* Actions Menu */}
      <Menu
        anchorEl={menuAnchor.el}
        open={!!menuAnchor.el}
        onClose={() => setMenuAnchor({ el: null, steamId: '' })}
        PaperProps={{ sx: { bgcolor: '#262626', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 2 } }}
      >
        <MenuItem onClick={() => handleGuardCode(menuAnchor.steamId)}>
          <ListItemIcon><GuardIcon fontSize="small" sx={{ color: '#F59E0B' }} /></ListItemIcon>
          <ListItemText>guard code</ListItemText>
        </MenuItem>
        <MenuItem onClick={async () => {
          const sid = menuAnchor.steamId;
          setMenuAnchor({ el: null, steamId: '' });
          setShowPassDialog({ open: true, steamId: sid, password: '', visible: false, loading: true });
          try {
            const res = await steamRentApi.getPassword(accountId!, sid);
            setShowPassDialog(prev => ({ ...prev, password: res.data.password, loading: false }));
          } catch { notify('failed to load password', 'error'); setShowPassDialog(prev => ({ ...prev, loading: false })); }
        }}>
          <ListItemIcon><VisibilityIcon fontSize="small" sx={{ color: '#A78BFA' }} /></ListItemIcon>
          <ListItemText>show password</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { setPasswordDialog({ open: true, steamId: menuAnchor.steamId }); setMenuAnchor({ el: null, steamId: '' }); }}>
          <ListItemIcon><PasswordIcon fontSize="small" sx={{ color: '#8B5CF6' }} /></ListItemIcon>
          <ListItemText>change password</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleKick(menuAnchor.steamId)}>
          <ListItemIcon><KickIcon fontSize="small" sx={{ color: '#06B6D4' }} /></ListItemIcon>
          <ListItemText>kick sessions</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { setMafileDialog({ open: true, steamId: menuAnchor.steamId }); setMenuAnchor({ el: null, steamId: '' }); }}>
          <ListItemIcon><ImportIcon fontSize="small" sx={{ color: '#22C55E' }} /></ListItemIcon>
          <ListItemText>import mafile</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { handleFreeze(menuAnchor.steamId); setMenuAnchor({ el: null, steamId: '' }); }}>
          <ListItemIcon><FreezeIcon fontSize="small" sx={{ color: '#06B6D4' }} /></ListItemIcon>
          <ListItemText>{accounts.find(a => a.id === menuAnchor.steamId)?.frozen ? 'unfreeze' : 'freeze'}</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { handleDelete(menuAnchor.steamId); setMenuAnchor({ el: null, steamId: '' }); }}>
          <ListItemIcon><DeleteIcon fontSize="small" sx={{ color: '#EF4444' }} /></ListItemIcon>
          <ListItemText sx={{ color: '#EF4444' }}>delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Guard Code Dialog */}
      <Dialog open={guardDialog.open} onClose={() => setGuardDialog({ open: false, steamId: '', code: '' })} maxWidth="xs" fullWidth>
        <DialogTitle>steam guard code</DialogTitle>
        <DialogContent>
          <Box sx={{ py: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 2, my: 1 }}>
            <Typography variant="h3" sx={{ fontFamily: 'monospace', fontWeight: 800, letterSpacing: '0.15em', color: '#8B5CF6' }}>
              {guardDialog.code}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, mt: 2 }}>
            <Button startIcon={<CopyIcon />} onClick={() => { navigator.clipboard.writeText(guardDialog.code); notify('copied!', 'success'); }}>copy</Button>
            <Button onClick={() => handleGuardCode(guardDialog.steamId)}><RefreshIcon sx={{ mr: 0.5 }} /> refresh</Button>
          </Box>
        </DialogContent>
        <DialogActions><Button onClick={() => setGuardDialog({ open: false, steamId: '', code: '' })}>close</Button></DialogActions>
      </Dialog>

      {/* Show Password Dialog */}
      <Dialog open={showPassDialog.open} onClose={() => setShowPassDialog({ open: false, steamId: '', password: '', visible: false, loading: false })} maxWidth="xs" fullWidth>
        <DialogTitle>password — {showPassDialog.steamId}</DialogTitle>
        <DialogContent>
          <Box sx={{ py: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 2, my: 1 }}>
            {showPassDialog.loading ? (
              <Typography variant="h4" sx={{ color: 'text.secondary' }}>loading...</Typography>
            ) : (
              <Typography variant="h4" sx={{ fontFamily: 'monospace', fontWeight: 800, letterSpacing: '0.08em', color: '#A78BFA', wordBreak: 'break-all' }}>
                {showPassDialog.visible ? showPassDialog.password : '•'.repeat(showPassDialog.password.length || 8)}
              </Typography>
            )}
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, mt: 2 }}>
            <Button startIcon={showPassDialog.visible ? <VisibilityOffIcon /> : <VisibilityIcon />} onClick={() => setShowPassDialog(p => ({ ...p, visible: !p.visible }))} disabled={showPassDialog.loading}>
              {showPassDialog.visible ? 'hide' : 'show'}
            </Button>
            <Button startIcon={<CopyIcon />} onClick={() => { navigator.clipboard.writeText(showPassDialog.password); notify('copied!', 'success'); }} disabled={showPassDialog.loading}>copy</Button>
          </Box>
        </DialogContent>
        <DialogActions><Button onClick={() => setShowPassDialog({ open: false, steamId: '', password: '', visible: false, loading: false })}>close</Button></DialogActions>
      </Dialog>

      <ChangePasswordDialog open={passwordDialog.open} steamId={passwordDialog.steamId} accountId={accountId!}
        onClose={() => setPasswordDialog({ open: false, steamId: '' })}
        onSuccess={() => { load(); notify('password changed', 'success'); setPasswordDialog({ open: false, steamId: '' }); }} />
      <ImportMafileDialog open={mafileDialog.open} steamId={mafileDialog.steamId} accountId={accountId!}
        onClose={() => setMafileDialog({ open: false, steamId: '' })}
        onSuccess={() => { load(); notify('mafile imported', 'success'); setMafileDialog({ open: false, steamId: '' }); }} />
      <SteamAccountFormDialog open={addOpen || !!editAccount} account={editAccount} accountId={accountId!} games={games}
        onClose={() => { setAddOpen(false); setEditAccount(null); }}
        onSuccess={() => { load(); notify(editAccount ? 'account updated' : 'account created', 'success'); setAddOpen(false); setEditAccount(null); }} />
    </Box>
  );
}

// ─── Steam Account Form Dialog ───────────────────────

function SteamAccountFormDialog({ open, account, accountId, games, onClose, onSuccess }: {
  open: boolean; account: SteamAccount | null; accountId: string; games: SteamGame[];
  onClose: () => void; onSuccess: () => void;
}) {
  const { notify } = useLayout();
  const [form, setForm] = useState({
    login: '', password: '', game_ids: [] as string[],
    change_password_on_rent: false, kick_devices_on_rent: true,
  });
  const [proxySettings, setProxySettings] = useState<ProxySettings>(DEFAULT_PROXY_SETTINGS);

  useEffect(() => {
    if (account) {
      setForm({ login: account.login, password: account.password, game_ids: account.game_ids || [], change_password_on_rent: account.change_password_on_rent, kick_devices_on_rent: account.kick_devices_on_rent });
      setProxySettings(account.proxy_settings ? { ...DEFAULT_PROXY_SETTINGS, ...(account.proxy_settings as unknown as ProxySettings) } : DEFAULT_PROXY_SETTINGS);
    } else {
      setForm({ login: '', password: '', game_ids: [], change_password_on_rent: false, kick_devices_on_rent: true });
      setProxySettings(DEFAULT_PROXY_SETTINGS);
    }
  }, [account, open]);

  const handleSubmit = async () => {
    try {
      const payload = { ...form, proxy_settings: proxySettings.mode === 'direct' ? null : proxySettings };
      if (account) { await steamRentApi.updateSteamAccount(accountId, account.id, payload as Partial<SteamAccount>); }
      else { await steamRentApi.createSteamAccount(accountId, { ...payload, id: form.login } as Partial<SteamAccount>); }
      onSuccess();
    } catch { notify('failed to save steam account', 'error'); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{account ? 'edit steam account' : 'add steam account'}</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <TextField fullWidth label="login" value={form.login} onChange={e => setForm({ ...form, login: e.target.value })} sx={{ mb: 2 }} />
        <TextField fullWidth label="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} sx={{ mb: 2 }} />
        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel>Games</InputLabel>
          <Select multiple value={form.game_ids} label="Games"
            onChange={e => setForm({ ...form, game_ids: (typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value) as string[] })}
            renderValue={selected => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(selected as string[]).map(v => <Chip key={v} size="small" label={v} />)}
              </Box>
            )}
          >
            {games.map(g => <MenuItem key={g.game_id} value={g.game_id}>{g.game_id}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControlLabel control={<Switch checked={form.change_password_on_rent} onChange={e => setForm({ ...form, change_password_on_rent: e.target.checked })} />} label="change password after rent" sx={{ mb: 1 }} />
        <FormControlLabel control={<Switch checked={form.kick_devices_on_rent} onChange={e => setForm({ ...form, kick_devices_on_rent: e.target.checked })} />} label="kick devices after rent" />
        <ProxySettingsField value={proxySettings} onChange={setProxySettings} accountId={accountId} label="proxy settings" />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!form.login || form.game_ids.length === 0}>{account ? 'save' : 'create'}</Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Change Password Dialog ──────────────────────────

function ChangePasswordDialog({ open, steamId, accountId, onClose, onSuccess }: {
  open: boolean; steamId: string; accountId: string; onClose: () => void; onSuccess: () => void;
}) {
  const { notify } = useLayout();
  const [newPass, setNewPass] = useState('');
  const [loading, setLoading] = useState(false);
  const handleSubmit = async () => {
    setLoading(true);
    try { await steamRentApi.changePassword(accountId, steamId, newPass || undefined); onSuccess(); }
    catch { notify('failed to change password', 'error'); }
    finally { setLoading(false); }
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>change password</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>leave empty to auto-generate a new password.</Typography>
        <TextField fullWidth label="new password (optional)" value={newPass} onChange={e => setNewPass(e.target.value)} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={loading}>change</Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Import Mafile Dialog ────────────────────────────

function ImportMafileDialog({ open, steamId, accountId, onClose, onSuccess }: {
  open: boolean; steamId: string; accountId: string; onClose: () => void; onSuccess: () => void;
}) {
  const { notify } = useLayout();
  const [json, setJson] = useState('');
  const [loading, setLoading] = useState(false);
  const handleSubmit = async () => {
    setLoading(true);
    try { JSON.parse(json); await steamRentApi.importMafile(accountId, steamId, json); onSuccess(); }
    catch (e: unknown) {
      const msg = (e as Error)?.message;
      notify(msg?.includes('JSON') ? 'invalid JSON format' : 'failed to import mafile', 'error');
    } finally { setLoading(false); }
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>import mafile</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>paste the mafile JSON content below.</Typography>
        <TextField fullWidth multiline rows={10} label="mafile JSON" value={json} onChange={e => setJson(e.target.value)} sx={{ fontFamily: 'monospace' }} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={loading || !json.trim()}>import</Button>
      </DialogActions>
    </Dialog>
  );
}
