import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { Outlet, useNavigate, useLocation, Link, matchPath } from 'react-router-dom';
import { usePolling } from '../hooks/usePolling';
import {
  Box, Drawer, Typography, List, ListItem, ListItemButton, ListItemIcon,
  ListItemText, Divider, Select, MenuItem, FormControl, InputLabel,
  alpha, Snackbar, Alert, IconButton, Tooltip,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Chat as ChatIcon,
  ShoppingCart as OrdersIcon,
  ChevronLeft as CollapseIcon,
  ChevronRight as ExpandIcon,
  Logout as LogoutIcon,
} from '@mui/icons-material';
import { AccountInfo, accountsApi } from '../api/client';
import { getModuleManifests } from '../modules';
import { useAuth } from '../auth/AuthContext';

const DRAWER_OPEN = 220;
const DRAWER_CLOSED = 56;

// ─── Layout Context ──────────────────────────────────

interface LayoutContextType {
  accounts: AccountInfo[];
  selectedAccount: AccountInfo | null;
  accountId: string | null;
  refetch: () => void;
  notify: (msg: string, severity?: 'success' | 'error' | 'info' | 'warning') => void;
}

const LayoutContext = createContext<LayoutContextType>({
  accounts: [],
  selectedAccount: null,
  accountId: null,
  refetch: () => {},
  notify: () => {},
});

export const useLayout = () => useContext(LayoutContext);

// ─── Layout Component ────────────────────────────────

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, authDisabled, logout } = useAuth();
  const [accounts, setAccounts] = useState<AccountInfo[]>([]);
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('nav_collapsed') === '1'; } catch { return false; }
  });
  const [snack, setSnack] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' | 'info' | 'warning' }>({
    open: false, msg: '', severity: 'info',
  });

  const drawerWidth = collapsed ? DRAWER_CLOSED : DRAWER_OPEN;

  const toggleCollapsed = useCallback(() => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('nav_collapsed', next ? '1' : '0'); } catch {}
      return next;
    });
  }, []);

  // Extract accountId from URL
  const match = matchPath('/accounts/:accountId/*', location.pathname);
  const accountId = match?.params?.accountId ?? null;
  const selectedAccount = accounts.find(a => a.account_id === accountId) ?? null;

  const loadAccounts = useCallback(async () => {
    try {
      const res = await accountsApi.list();
      setAccounts(res.data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);
  usePolling(loadAccounts, 8000);

  const notify = useCallback((msg: string, severity: 'success' | 'error' | 'info' | 'warning' = 'info') => {
    setSnack({ open: true, msg, severity });
  }, []);

  const moduleManifests = getModuleManifests();
  const enabledModules = selectedAccount?.modules ?? [];

  return (
    <LayoutContext.Provider value={{ accounts, selectedAccount, accountId, refetch: loadAccounts, notify }}>
      <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>

        {/* ─── Sidebar ─────────────────────────── */}
        <Drawer
          variant="permanent"
          sx={{
            width: drawerWidth,
            flexShrink: 0,
            transition: 'width 0.2s ease',
            '& .MuiDrawer-paper': {
              width: drawerWidth,
              boxSizing: 'border-box',
              overflowX: 'hidden',
              transition: 'width 0.2s ease',
              borderRight: '1px solid rgba(255,255,255,0.06)',
            },
          }}
        >
          {/* Logo + collapse */}
          <Box sx={{
            px: collapsed ? 0 : 2, py: 1.5,
            display: 'flex', alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
            minHeight: 48,
          }}>
            {!collapsed && (
              <Typography
                variant="h6"
                component={Link}
                to="/"
                sx={{
                  fontWeight: 800, fontSize: '1.1rem',
                  letterSpacing: '0.06em',
                  color: '#fff',
                  textDecoration: 'none',
                  userSelect: 'none',
                }}
              >
                opium
              </Typography>
            )}
            <Tooltip title={collapsed ? 'expand' : 'collapse'} placement="right">
              <IconButton size="small" onClick={toggleCollapsed} sx={{ color: 'text.secondary' }}>
                {collapsed ? <ExpandIcon fontSize="small" /> : <CollapseIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          </Box>

          <Divider sx={{ mx: collapsed ? 0.5 : 1 }} />

          {/* Account selector */}
          {!collapsed && (
            <Box sx={{ px: 1, py: 1 }}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ fontSize: '0.8rem' }}>account</InputLabel>
                <Select
                  value={accountId ?? ''}
                  label="account"
                  onChange={e => {
                    const v = e.target.value as string;
                    if (v) {
                      const acc = accounts.find(a => a.account_id === v);
                      const mods = acc?.modules ?? [];
                      const firstMod = moduleManifests.find(m => mods.includes(m.name));
                      if (firstMod && firstMod.navigation.length > 0) {
                        navigate(`/accounts/${v}/modules/${firstMod.name}/${firstMod.navigation[0].path}`);
                      } else {
                        navigate(`/accounts/${v}/chats`);
                      }
                    } else {
                      navigate('/');
                    }
                  }}
                  sx={{ borderRadius: 2, fontSize: '0.82rem' }}
                >
                  <MenuItem value=""><em>all accounts</em></MenuItem>
                  {accounts.map(acc => (
                    <MenuItem key={acc.account_id} value={acc.account_id}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{
                          width: 6, height: 6, borderRadius: '50%',
                          bgcolor: acc.is_running ? 'success.main' : acc.state === 'error' ? 'error.main' : '#525252',
                          boxShadow: acc.is_running ? '0 0 6px rgba(34,197,94,0.5)' : 'none',
                        }} />
                        <Typography variant="body2" sx={{ color: 'text.primary' }}>
                          {acc.username || acc.account_id}
                        </Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          )}

          {/* Global nav */}
          <List sx={{ px: 0.5, py: 0.5 }}>
            <NavLink to="/" icon={<DashboardIcon fontSize="small" />} label="dashboard" collapsed={collapsed} />
          </List>

          {/* Per-account nav */}
          {accountId && (
            <>
              <Divider sx={{ mx: collapsed ? 0.5 : 1, my: 0.5 }} />
              {!collapsed && (
                <Typography variant="caption" sx={{
                  px: 2, py: 0.5, display: 'block', color: 'text.secondary',
                  textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600,
                  fontSize: '0.65rem',
                }}>
                  {selectedAccount?.username || accountId}
                </Typography>
              )}
              <List sx={{ px: 0.5, pt: 0 }}>
                <NavLink to={`/accounts/${accountId}/chats`} icon={<ChatIcon fontSize="small" />} label="chats" collapsed={collapsed} />
                <NavLink to={`/accounts/${accountId}/orders`} icon={<OrdersIcon fontSize="small" />} label="orders" collapsed={collapsed} />
              </List>

              {/* Module nav sections */}
              {moduleManifests
                .filter(m => enabledModules.includes(m.name))
                .map(m => (
                  <Box key={m.name}>
                    <Divider sx={{ mx: collapsed ? 0.5 : 1, my: 0.5 }} />
                    {!collapsed && (
                      <Typography variant="caption" sx={{
                        px: 2, py: 0.5, display: 'block', color: 'text.secondary',
                        textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600,
                        fontSize: '0.65rem',
                      }}>
                        {m.displayName}
                      </Typography>
                    )}
                    <List sx={{ px: 0.5, pt: 0 }}>
                      {m.navigation.map(nav => (
                        <NavLink
                          key={nav.path}
                          to={`/accounts/${accountId}/modules/${m.name}/${nav.path}`}
                          icon={nav.icon}
                          label={nav.label}
                          collapsed={collapsed}
                        />
                      ))}
                    </List>
                  </Box>
                ))}
            </>
          )}

          {/* Bottom */}
          <Box sx={{ flexGrow: 1 }} />

          {/* Logout button (only when auth is enabled) */}
          {!authDisabled && user && (
            <Box sx={{ px: 0.5, pb: 0.5 }}>
              <Tooltip title={collapsed ? 'Logout' : ''} placement="right">
                <ListItemButton
                  onClick={logout}
                  sx={{
                    borderRadius: 2,
                    minHeight: 40,
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    px: collapsed ? 1 : 1.5,
                    color: '#707070',
                    '&:hover': { color: '#EF4444', bgcolor: 'rgba(239,68,68,0.08)' },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: collapsed ? 0 : 36, color: 'inherit' }}>
                    <LogoutIcon fontSize="small" />
                  </ListItemIcon>
                  {!collapsed && (
                    <ListItemText
                      primary={user.username}
                      primaryTypographyProps={{ fontSize: '0.8rem', fontWeight: 500 }}
                    />
                  )}
                </ListItemButton>
              </Tooltip>
            </Box>
          )}

          {!collapsed && (
            <Box sx={{ px: 2, py: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" sx={{ color: '#525252', fontSize: '0.65rem' }}>
                vibecode ui
              </Typography>
            </Box>
          )}
        </Drawer>

        {/* ─── Main Content ────────────────────── */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            minHeight: '100vh',
            p: { xs: 1.5, sm: 2.5 },
            maxWidth: `calc(100vw - ${drawerWidth}px)`,
            transition: 'max-width 0.2s ease',
          }}
        >
          <Outlet />
        </Box>
      </Box>

      {/* ─── Global Snackbar ──────────────────── */}
      <Snackbar
        open={snack.open}
        autoHideDuration={4000}
        onClose={() => setSnack(s => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setSnack(s => ({ ...s, open: false }))}
          severity={snack.severity}
          variant="filled"
          sx={{ borderRadius: 2.5 }}
        >
          {snack.msg}
        </Alert>
      </Snackbar>
    </LayoutContext.Provider>
  );
}

// ─── Nav Link ─────────────────────────────────────────

function NavLink({ to, icon, label, collapsed }: { to: string; icon: React.ReactNode; label: string; collapsed: boolean }) {
  const location = useLocation();
  const active = to === '/'
    ? location.pathname === '/'
    : location.pathname.startsWith(to);

  return (
    <ListItem disablePadding sx={{ mb: 0.2 }}>
      <Tooltip title={collapsed ? label : ''} placement="right" arrow>
        <ListItemButton
          component={Link}
          to={to}
          selected={active}
          sx={{
            borderRadius: 2,
            py: 0.7,
            px: collapsed ? 0 : 1.5,
            minHeight: 36,
            justifyContent: collapsed ? 'center' : 'flex-start',
            '&.Mui-selected': {
              bgcolor: alpha('#8B5CF6', 0.12),
              '&:hover': { bgcolor: alpha('#8B5CF6', 0.16) },
              '& .MuiListItemIcon-root': { color: '#8B5CF6' },
              '& .MuiListItemText-primary': { color: '#8B5CF6', fontWeight: 600 },
            },
          }}
        >
          <ListItemIcon sx={{ minWidth: collapsed ? 'auto' : 30, color: 'text.secondary', justifyContent: 'center' }}>
            {icon}
          </ListItemIcon>
          {!collapsed && (
            <ListItemText
              primary={label}
              primaryTypographyProps={{ fontSize: '0.82rem', fontWeight: 500 }}
            />
          )}
        </ListItemButton>
      </Tooltip>
    </ListItem>
  );
}
