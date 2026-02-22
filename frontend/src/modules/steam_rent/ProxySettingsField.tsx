import { useState, useEffect } from 'react';
import {
  Box, Typography, FormControl, InputLabel, Select, MenuItem, alpha,
} from '@mui/material';
import { steamRentApi, Proxy, ProxyList, ProxySettings } from './api';

export const DEFAULT_PROXY_SETTINGS: ProxySettings = {
  mode: 'direct',
  fixed_proxy_id: null,
  proxy_list_id: null,
  fallback: 'try-all',
};

interface ProxySettingsFieldProps {
  value: ProxySettings;
  onChange: (settings: ProxySettings) => void;
  accountId: string;
  /** Optional label above the section */
  label?: string;
}

/**
 * Reusable ProxySettings form section for Game and SteamAccount dialogs.
 * Fetches proxies and proxy lists on mount.
 */
export function ProxySettingsField({ value, onChange, accountId, label }: ProxySettingsFieldProps) {
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [proxyLists, setProxyLists] = useState<ProxyList[]>([]);

  useEffect(() => {
    if (!accountId) return;
    Promise.all([
      steamRentApi.getProxies(accountId),
      steamRentApi.getProxyLists(accountId),
    ]).then(([pRes, plRes]) => {
      setProxies(pRes.data);
      setProxyLists(plRes.data);
    }).catch(() => {});
  }, [accountId]);

  const enabledProxies = proxies.filter(p => p.enabled);

  return (
    <Box sx={{
      mt: 2, p: 2,
      bgcolor: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 2,
    }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5, color: '#a0a0a0' }}>
        {label || 'proxy settings'}
      </Typography>

      {/* Mode */}
      <FormControl fullWidth size="small" sx={{ mb: 2 }}>
        <InputLabel>Mode</InputLabel>
        <Select value={value.mode} label="Mode"
          onChange={e => onChange({ ...value, mode: e.target.value as ProxySettings['mode'] })}>
          <MenuItem value="direct">direct (no proxy)</MenuItem>
          <MenuItem value="fixed">fixed proxy</MenuItem>
          <MenuItem value="mix">mix (random from all)</MenuItem>
          <MenuItem value="mix-list">mix from list</MenuItem>
        </Select>
      </FormControl>

      {/* Fixed Proxy - only when mode=fixed */}
      {value.mode === 'fixed' && (
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel>Proxy</InputLabel>
          <Select
            value={value.fixed_proxy_id || ''} label="Proxy"
            onChange={e => onChange({ ...value, fixed_proxy_id: e.target.value || null })}
          >
            <MenuItem value=""><em>- select proxy -</em></MenuItem>
            {enabledProxies.map(p => (
              <MenuItem key={p.proxy_id} value={p.proxy_id}>
                {p.name || `${p.host}:${p.port}`}
                <Typography component="span" variant="caption" sx={{ ml: 1, color: '#707070' }}>
                  ({p.proxy_type})
                </Typography>
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {/* Proxy List - only when mode=mix-list */}
      {value.mode === 'mix-list' && (
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel>Proxy List</InputLabel>
          <Select
            value={value.proxy_list_id || ''} label="Proxy List"
            onChange={e => onChange({ ...value, proxy_list_id: e.target.value || null })}
          >
            <MenuItem value=""><em>- select list -</em></MenuItem>
            {proxyLists.map(pl => (
              <MenuItem key={pl.list_id} value={pl.list_id}>
                {pl.name}
                <Typography component="span" variant="caption" sx={{ ml: 1, color: '#707070' }}>
                  ({pl.proxy_ids.length} proxies)
                </Typography>
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {/* Fallback - when not direct */}
      {value.mode !== 'direct' && (
        <FormControl fullWidth size="small">
          <InputLabel>Fallback</InputLabel>
          <Select value={value.fallback} label="Fallback"
            onChange={e => onChange({ ...value, fallback: e.target.value as ProxySettings['fallback'] })}>
            <MenuItem value="try-all">try all proxies, then direct</MenuItem>
            <MenuItem value="direct">go direct immediately</MenuItem>
          </Select>
        </FormControl>
      )}
    </Box>
  );
}
