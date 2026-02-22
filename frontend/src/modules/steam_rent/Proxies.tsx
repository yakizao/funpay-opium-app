import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Button, IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
  DialogActions, TextField, Paper, Chip, alpha, Switch, FormControlLabel, Select,
  MenuItem, FormControl, InputLabel, Divider, CircularProgress, InputAdornment,
  List, ListItem, ListItemText, ListItemSecondaryAction,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Refresh as RefreshIcon,
  CheckCircle as HealthyIcon,
  Cancel as UnhealthyIcon,
  PlaylistAdd as ListAddIcon,
  Visibility,
  VisibilityOff,
} from '@mui/icons-material';
import { useLayout } from '../../components/Layout';
import { PageHeader } from '../../components/PageHeader';
import { DataTable, type Column, type FilterGroup } from '../../components/DataTable';
import { usePolling } from '../../hooks/usePolling';
import { steamRentApi, Proxy, ProxyList } from './api';

type HealthMap = Record<string, 'checking' | 'healthy' | 'unhealthy'>;

export default function ProxiesPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [proxyLists, setProxyLists] = useState<ProxyList[]>([]);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<HealthMap>({});
  const [filterType, setFilterType] = useState('all');
  const [filterEnabled, setFilterEnabled] = useState('all');

  // Dialogs
  const [formOpen, setFormOpen] = useState(false);
  const [editProxy, setEditProxy] = useState<Proxy | null>(null);
  const [listFormOpen, setListFormOpen] = useState(false);
  const [manageList, setManageList] = useState<ProxyList | null>(null);

  useEffect(() => { load(); }, [accountId]);

  const load = async (silent = false) => {
    if (!accountId) return;
    try {
      const [pRes, plRes] = await Promise.all([
        steamRentApi.getProxies(accountId),
        steamRentApi.getProxyLists(accountId),
      ]);
      setProxies(pRes.data);
      setProxyLists(plRes.data);
    } catch { if (!silent) notify('failed to load proxies', 'error'); }
    finally { setLoading(false); }
  };
  usePolling(() => load(true), 30000, !!accountId);

  const handleDelete = async (proxyId: string) => {
    if (!accountId || !confirm('Delete this proxy?')) return;
    try {
      await steamRentApi.deleteProxy(accountId, proxyId);
      notify('proxy deleted', 'success');
      load();
    } catch { notify('failed to delete proxy', 'error'); }
  };

  const handleHealthCheck = async (proxyId: string) => {
    if (!accountId) return;
    setHealth(h => ({ ...h, [proxyId]: 'checking' }));
    try {
      const res = await steamRentApi.checkProxyHealth(accountId, proxyId);
      setHealth(h => ({ ...h, [proxyId]: res.data.healthy ? 'healthy' : 'unhealthy' }));
    } catch {
      setHealth(h => ({ ...h, [proxyId]: 'unhealthy' }));
    }
  };

  const handleDeleteList = async (listId: string) => {
    if (!accountId || !confirm('Delete this proxy list?')) return;
    try {
      await steamRentApi.deleteProxyList(accountId, listId);
      notify('proxy list deleted', 'success');
      load();
    } catch { notify('failed to delete', 'error'); }
  };

  const filtered = useMemo(() => {
    return proxies.filter(p => {
      if (filterType !== 'all' && p.proxy_type !== filterType) return false;
      if (filterEnabled === 'on' && !p.enabled) return false;
      if (filterEnabled === 'off' && p.enabled) return false;
      return true;
    });
  }, [proxies, filterType, filterEnabled]);

  const columns: Column<Proxy>[] = useMemo(() => [
    {
      id: 'name', label: 'name', sortable: true,
      sortValue: p => p.name || p.proxy_id,
      searchValue: p => `${p.name} ${p.proxy_id}`,
      render: p => (
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>{p.name || '-'}</Typography>
          <Typography variant="caption" sx={{ color: '#525252', fontFamily: 'monospace' }}>{p.proxy_id}</Typography>
        </Box>
      ),
    },
    {
      id: 'address', label: 'address', sortable: true,
      sortValue: p => `${p.host}:${p.port}`,
      searchValue: p => `${p.host}:${p.port}`,
      render: p => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{p.host}:{p.port}</Typography>
      ),
    },
    {
      id: 'type', label: 'type', sortable: true, width: 90,
      sortValue: p => p.proxy_type,
      render: p => (
        <Chip size="small" label={p.proxy_type.toUpperCase()} sx={{ bgcolor: alpha('#3B82F6', 0.1), color: '#60A5FA', fontWeight: 600 }} />
      ),
    },
    {
      id: 'auth', label: 'auth', width: 70,
      sortValue: p => p.username ? 1 : 0,
      sortable: true,
      render: p => (
        <Chip size="small" label={p.username ? 'Yes' : 'No'} sx={{
          bgcolor: alpha(p.username ? '#22C55E' : '#707070', 0.12),
          color: p.username ? '#22C55E' : '#a0a0a0',
        }} />
      ),
    },
    {
      id: 'enabled', label: 'enabled', width: 80,
      sortValue: p => p.enabled ? 1 : 0,
      sortable: true,
      render: p => (
        <Chip size="small" label={p.enabled ? 'On' : 'Off'} sx={{
          bgcolor: alpha(p.enabled ? '#22C55E' : '#707070', 0.12),
          color: p.enabled ? '#22C55E' : '#a0a0a0',
        }} />
      ),
    },
    {
      id: 'health', label: 'health', width: 70,
      render: p => <HealthIndicator status={health[p.proxy_id]} />,
    },
    {
      id: 'actions', label: '', align: 'right', width: 110,
      render: p => (
        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
          <Tooltip title="check health">
            <IconButton size="small" onClick={() => handleHealthCheck(p.proxy_id)} disabled={health[p.proxy_id] === 'checking'}>
              <RefreshIcon fontSize="small" sx={{ color: '#06B6D4' }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="edit">
            <IconButton size="small" onClick={() => { setEditProxy(p); setFormOpen(true); }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="delete">
            <IconButton size="small" onClick={() => handleDelete(p.proxy_id)} color="error">
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ], [health]);

  const proxyTypes = useMemo(() => [...new Set(proxies.map(p => p.proxy_type))], [proxies]);

  const filterGroups: FilterGroup[] = useMemo(() => {
    const groups: FilterGroup[] = [];
    if (proxyTypes.length > 1) {
      groups.push({
        label: 'type', value: filterType, onChange: setFilterType,
        options: [
          { label: 'all', value: 'all', count: proxies.length },
          ...proxyTypes.map(t => ({ label: t.toUpperCase(), value: t, count: proxies.filter(p => p.proxy_type === t).length, color: '#3B82F6' })),
        ],
      });
    }
    groups.push({
      label: 'status', value: filterEnabled, onChange: setFilterEnabled,
      options: [
        { label: 'all', value: 'all', count: proxies.length },
        { label: 'enabled', value: 'on', count: proxies.filter(p => p.enabled).length, color: '#22C55E' },
        { label: 'disabled', value: 'off', count: proxies.filter(p => !p.enabled).length, color: '#707070' },
      ],
    });
    return groups;
  }, [proxies, proxyTypes, filterType, filterEnabled]);

  return (
    <Box>
      <PageHeader
        title="proxies"
        subtitle={`${proxies.length} proxies · ${proxyLists.length} lists`}
        onRefresh={load}
        actions={
          <>
            <Button variant="outlined" startIcon={<ListAddIcon />} onClick={() => setListFormOpen(true)}>new list</Button>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditProxy(null); setFormOpen(true); }}>add proxy</Button>
          </>
        }
      />

      {/* ─── Proxies Table ─── */}
      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={p => p.proxy_id}
        loading={loading}
        emptyMessage="no proxies configured. add one to start."
        filters={filterGroups}
        searchPlaceholder="search proxies..."
        defaultSortColumn="name"
        sx={{ mb: 4 }}
      />

      {/* ─── Proxy Lists ─── */}
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>proxy lists</Typography>
      {proxyLists.length === 0 ? (
        <Paper sx={{ bgcolor: '#141414', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 2, p: 4, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">no proxy lists. create one to group proxies.</Typography>
        </Paper>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {proxyLists.map(pl => (
            <Paper key={pl.list_id} sx={{ bgcolor: '#141414', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 2, p: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Box>
                  <Typography variant="body1" sx={{ fontWeight: 600 }}>{pl.name}</Typography>
                  <Typography variant="caption" sx={{ color: '#525252' }}>{pl.proxy_ids.length} proxies · ID: {pl.list_id}</Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  <Tooltip title="manage proxies"><IconButton size="small" onClick={() => setManageList(pl)}><EditIcon fontSize="small" /></IconButton></Tooltip>
                  <Tooltip title="delete list"><IconButton size="small" color="error" onClick={() => handleDeleteList(pl.list_id)}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
                </Box>
              </Box>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {pl.proxy_ids.length > 0 ? pl.proxy_ids.map(pid => {
                  const px = proxies.find(p => p.proxy_id === pid);
                  return <Chip key={pid} size="small" label={px ? (px.name || `${px.host}:${px.port}`) : pid} sx={{ bgcolor: alpha('#8B5CF6', 0.1), color: '#A78BFA', fontSize: '0.72rem' }} />;
                }) : <Typography variant="caption" color="text.secondary">empty list</Typography>}
              </Box>
            </Paper>
          ))}
        </Box>
      )}

      {/* ─── Dialogs ─── */}
      <ProxyFormDialog
        open={formOpen} proxy={editProxy} accountId={accountId!}
        onClose={() => { setFormOpen(false); setEditProxy(null); }}
        onSuccess={() => { load(); notify(editProxy ? 'proxy updated' : 'proxy created', 'success'); setFormOpen(false); setEditProxy(null); }}
      />
      <ProxyListFormDialog
        open={listFormOpen} accountId={accountId!} proxies={proxies}
        onClose={() => setListFormOpen(false)}
        onSuccess={() => { load(); notify('proxy list created', 'success'); setListFormOpen(false); }}
      />
      <ManageListDialog
        open={!!manageList} proxyList={manageList} accountId={accountId!} proxies={proxies}
        onClose={() => setManageList(null)} onChanged={() => load()} notify={notify}
      />
    </Box>
  );
}

// ─── Health Indicator ────────────────────────────────

function HealthIndicator({ status }: { status?: 'checking' | 'healthy' | 'unhealthy' }) {
  if (!status) return <Typography variant="caption" color="text.secondary">-</Typography>;
  if (status === 'checking') return <CircularProgress size={16} sx={{ color: '#F59E0B' }} />;
  if (status === 'healthy') return <HealthyIcon fontSize="small" sx={{ color: '#22C55E' }} />;
  return <UnhealthyIcon fontSize="small" sx={{ color: '#EF4444' }} />;
}

// ─── Proxy Form Dialog ──────────────────────────────

function ProxyFormDialog({ open, proxy, accountId, onClose, onSuccess }: {
  open: boolean; proxy: Proxy | null; accountId: string;
  onClose: () => void; onSuccess: () => void;
}) {
  const { notify } = useLayout();
  const [form, setForm] = useState({
    host: '', port: '', proxy_type: 'http' as string,
    username: '', password: '', name: '', enabled: true, url: '',
  });
  const [useUrl, setUseUrl] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (proxy) {
      setForm({
        host: proxy.host, port: String(proxy.port), proxy_type: proxy.proxy_type,
        username: proxy.username, password: '', name: proxy.name, enabled: proxy.enabled, url: '',
      });
      setUseUrl(false);
    } else {
      setForm({ host: '', port: '', proxy_type: 'http', username: '', password: '', name: '', enabled: true, url: '' });
      setUseUrl(false);
    }
    setShowPassword(false);
  }, [proxy, open]);

  const handleSubmit = async () => {
    try {
      if (proxy) {
        const data: Record<string, unknown> = {};
        if (form.host && form.host !== proxy.host) data.host = form.host;
        if (form.port && Number(form.port) !== proxy.port) data.port = Number(form.port);
        if (form.proxy_type !== proxy.proxy_type) data.proxy_type = form.proxy_type;
        if (form.username !== proxy.username) data.username = form.username;
        if (form.password) data.password = form.password;
        if (form.name !== proxy.name) data.name = form.name;
        if (form.enabled !== proxy.enabled) data.enabled = form.enabled;
        await steamRentApi.updateProxy(accountId, proxy.proxy_id, data);
      } else if (useUrl) {
        await steamRentApi.createProxy(accountId, { url: form.url, name: form.name, enabled: form.enabled } as any);
      } else {
        await steamRentApi.createProxy(accountId, {
          host: form.host, port: Number(form.port), proxy_type: form.proxy_type as any,
          username: form.username, password: form.password, name: form.name, enabled: form.enabled,
        });
      }
      onSuccess();
    } catch { notify('failed to save proxy', 'error'); }
  };

  const canSubmit = proxy ? true : useUrl ? !!form.url.trim() : (!!form.host.trim() && !!form.port);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{proxy ? 'edit proxy' : 'add proxy'}</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        {!proxy && (
          <FormControlLabel control={<Switch checked={useUrl} onChange={(_, v) => setUseUrl(v)} />} label="import from URL" sx={{ mb: 2 }} />
        )}
        {useUrl && !proxy ? (
          <TextField fullWidth label="proxy URL" value={form.url} onChange={e => setForm({ ...form, url: e.target.value })}
            placeholder="http://user:pass@host:port" helperText="format: type://username:password@host:port" sx={{ mb: 2 }} />
        ) : (
          <>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <TextField fullWidth label="Host" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} placeholder="1.2.3.4" />
              <TextField label="Port" value={form.port} type="number" onChange={e => setForm({ ...form, port: e.target.value })} sx={{ width: 120 }} />
            </Box>
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Type</InputLabel>
              <Select value={form.proxy_type} label="Type" onChange={e => setForm({ ...form, proxy_type: e.target.value })}>
                <MenuItem value="http">HTTP</MenuItem>
                <MenuItem value="https">HTTPS</MenuItem>
                <MenuItem value="socks5">SOCKS5</MenuItem>
              </Select>
            </FormControl>
            <TextField fullWidth label="Username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} sx={{ mb: 2 }} />
            <TextField fullWidth label="Password" type={showPassword ? 'text' : 'password'} value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              placeholder={proxy ? '(leave empty to keep current)' : ''} sx={{ mb: 2 }}
              slotProps={{
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton edge="end" size="small" tabIndex={-1} onClick={() => setShowPassword(!showPassword)}>
                        {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                      </IconButton>
                    </InputAdornment>
                  ),
                },
              }}
            />
          </>
        )}
        <TextField fullWidth label="name (optional)" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
          helperText="display name for easier identification" sx={{ mb: 2 }} />
        <FormControlLabel control={<Switch checked={form.enabled} onChange={(_, v) => setForm({ ...form, enabled: v })} />} label="enabled" />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!canSubmit}>{proxy ? 'save' : 'create'}</Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Proxy List Form Dialog ─────────────────────────

function ProxyListFormDialog({ open, accountId, proxies, onClose, onSuccess }: {
  open: boolean; accountId: string; proxies: Proxy[];
  onClose: () => void; onSuccess: () => void;
}) {
  const { notify } = useLayout();
  const [name, setName] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  useEffect(() => { setName(''); setSelectedIds([]); }, [open]);

  const handleSubmit = async () => {
    try {
      await steamRentApi.createProxyList(accountId, { name, proxy_ids: selectedIds });
      onSuccess();
    } catch { notify('failed to create proxy list', 'error'); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>new proxy list</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <TextField fullWidth label="list name" value={name} onChange={e => setName(e.target.value)} sx={{ mb: 2 }} />
        <Typography variant="body2" sx={{ mb: 1, color: 'text.secondary' }}>select proxies to include:</Typography>
        <FormControl fullWidth>
          <InputLabel>Proxies</InputLabel>
          <Select multiple value={selectedIds} label="Proxies"
            onChange={e => setSelectedIds(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value as string[])}
            renderValue={sel => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(sel as string[]).map(id => {
                  const px = proxies.find(p => p.proxy_id === id);
                  return <Chip key={id} size="small" label={px ? (px.name || `${px.host}:${px.port}`) : id} />;
                })}
              </Box>
            )}
          >
            {proxies.filter(p => p.enabled).map(p => (
              <MenuItem key={p.proxy_id} value={p.proxy_id}>{p.name || `${p.host}:${p.port}`} ({p.proxy_type})</MenuItem>
            ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!name.trim()}>create</Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Manage List Dialog ─────────────────────────────

function ManageListDialog({ open, proxyList, accountId, proxies, onClose, onChanged, notify }: {
  open: boolean; proxyList: ProxyList | null; accountId: string; proxies: Proxy[];
  onClose: () => void; onChanged: () => void;
  notify: (msg: string, severity?: 'success' | 'error' | 'info' | 'warning') => void;
}) {
  if (!proxyList) return null;

  const inList = proxies.filter(p => proxyList.proxy_ids.includes(p.proxy_id));
  const notInList = proxies.filter(p => p.enabled && !proxyList.proxy_ids.includes(p.proxy_id));

  const handleAdd = async (proxyId: string) => {
    try {
      await steamRentApi.addProxyToList(accountId, proxyList.list_id, proxyId);
      notify('proxy added to list', 'success');
      onChanged();
    } catch { notify('failed to add', 'error'); }
  };

  const handleRemove = async (proxyId: string) => {
    try {
      await steamRentApi.removeProxyFromList(accountId, proxyList.list_id, proxyId);
      notify('proxy removed from list', 'success');
      onChanged();
    } catch { notify('failed to remove', 'error'); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>manage: {proxyList.name}</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>in this list ({inList.length})</Typography>
        {inList.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>empty</Typography>
        ) : (
          <List dense sx={{ mb: 2 }}>
            {inList.map(p => (
              <ListItem key={p.proxy_id} sx={{ bgcolor: 'rgba(255,255,255,0.02)', borderRadius: 1, mb: 0.5 }}>
                <ListItemText primary={p.name || `${p.host}:${p.port}`} secondary={`${p.proxy_type} · ${p.proxy_id}`}
                  primaryTypographyProps={{ fontSize: '0.85rem' }} secondaryTypographyProps={{ fontSize: '0.7rem' }} />
                <ListItemSecondaryAction>
                  <IconButton size="small" color="error" onClick={() => handleRemove(p.proxy_id)}><DeleteIcon fontSize="small" /></IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
        <Divider sx={{ my: 1 }} />
        <Typography variant="subtitle2" sx={{ mb: 1, mt: 1 }}>available ({notInList.length})</Typography>
        {notInList.length === 0 ? (
          <Typography variant="body2" color="text.secondary">no available proxies</Typography>
        ) : (
          <List dense>
            {notInList.map(p => (
              <ListItem key={p.proxy_id} sx={{ bgcolor: 'rgba(255,255,255,0.02)', borderRadius: 1, mb: 0.5 }}>
                <ListItemText primary={p.name || `${p.host}:${p.port}`} secondary={`${p.proxy_type} · ${p.proxy_id}`}
                  primaryTypographyProps={{ fontSize: '0.85rem' }} secondaryTypographyProps={{ fontSize: '0.7rem' }} />
                <ListItemSecondaryAction>
                  <IconButton size="small" sx={{ color: '#22C55E' }} onClick={() => handleAdd(p.proxy_id)}><AddIcon fontSize="small" /></IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>close</Button></DialogActions>
    </Dialog>
  );
}
