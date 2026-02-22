import { useState, useEffect } from 'react';
import {
  Button, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Switch, FormControlLabel, Accordion, AccordionSummary, AccordionDetails,
  Box, Typography,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { accountsApi, AccountConfig } from '../api/client';

// ─── Shared Styles & Types ───────────────────────────

export const accordionSx = {
  bgcolor: 'transparent', backgroundImage: 'none',
  border: '1px solid rgba(255,255,255,0.06)', borderRadius: 2,
  mb: 1, boxShadow: 'none', '&:before': { display: 'none' },
} as const;

export interface AntiDetectForm {
  startup_delay_min: number;
  startup_delay_max: number;
  shutdown_delay_min: number;
  shutdown_delay_max: number;
  runner_delay_min: number;
  runner_delay_max: number;
  session_refresh_interval: number;
  session_refresh_jitter: number;
}

export const DEFAULT_AD: AntiDetectForm = {
  startup_delay_min: 0,
  startup_delay_max: 0,
  shutdown_delay_min: 0,
  shutdown_delay_max: 0,
  runner_delay_min: 4,
  runner_delay_max: 8,
  session_refresh_interval: 2400,
  session_refresh_jitter: 600,
};

// ─── Anti-Detect Accordions ──────────────────────────

export function AntiDetectAccordions({ ad, setAd, defaultExpanded }: {
  ad: AntiDetectForm;
  setAd: (v: AntiDetectForm) => void;
  defaultExpanded?: boolean;
}) {
  const f = (label: string, key: keyof AntiDetectForm, unit = 'сек') => (
    <TextField
      size="small"
      label={`${label} (${unit})`}
      type="number"
      value={ad[key]}
      onChange={e => setAd({ ...ad, [key]: parseFloat(e.target.value) || 0 })}
      inputProps={{ min: 0, step: 0.5 }}
      sx={{ flex: 1, minWidth: 120 }}
    />
  );

  return (
    <>
      <Accordion defaultExpanded={defaultExpanded} sx={accordionSx}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2 }}>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>polling interval</Typography>
            <Typography variant="caption" color="text.secondary">how often the bot polls funpay</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails sx={{ px: 2, pb: 2 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            random delay from min to max seconds between requests.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {f('Min', 'runner_delay_min')}
            {f('Max', 'runner_delay_max')}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            recommended: 4-8 sec. too frequent requests may cause a ban.
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion sx={accordionSx}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2 }}>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>startup / shutdown delay</Typography>
            <Typography variant="caption" color="text.secondary">delay before start and stop</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails sx={{ px: 2, pb: 2 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            useful so multi-accounts don't log in simultaneously.
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 500, mb: 1, mt: 1 }}>startup delay</Typography>
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            {f('Min', 'startup_delay_min')}
            {f('Max', 'startup_delay_max')}
          </Box>
          <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>shutdown delay</Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {f('Min', 'shutdown_delay_min')}
            {f('Max', 'shutdown_delay_max')}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            set 0/0 to disable.
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion sx={accordionSx}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2 }}>
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>session refresh</Typography>
            <Typography variant="caption" color="text.secondary">PHPSESSID refresh</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails sx={{ px: 2, pb: 2 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            auto session refresh to mimic a real user.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {f('Интервал', 'session_refresh_interval')}
            {f('Jitter ±', 'session_refresh_jitter')}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            default: ~40 min (2400) ± 10 min (600)
          </Typography>
        </AccordionDetails>
      </Accordion>
    </>
  );
}

// ─── Add Account Dialog ──────────────────────────────

export function AddAccountDialog({ open, onClose, onSuccess }: {
  open: boolean; onClose: () => void; onSuccess: () => void;
}) {
  const [form, setForm] = useState<AccountConfig>({
    account_id: '', golden_key: '', user_agent: '', proxy: '',
    disable_messages: false, disable_orders: false, anti_detect: null,
  });
  const [ad, setAd] = useState<AntiDetectForm>({ ...DEFAULT_AD });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!form.account_id || !form.golden_key) return;
    setLoading(true);
    try {
      const hasCustomAd = Object.entries(ad).some(([k, v]) => v !== (DEFAULT_AD as any)[k]);
      await accountsApi.create({ ...form, proxy: form.proxy || null, anti_detect: hasCustomAd ? ad : null });
      onSuccess();
      setForm({ account_id: '', golden_key: '', user_agent: '', proxy: '', disable_messages: false, disable_orders: false, anti_detect: null });
      setAd({ ...DEFAULT_AD });
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(detail || 'failed to create account');
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>add account</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        <TextField fullWidth label="account id" placeholder="e.g. my_shop"
          value={form.account_id} onChange={e => setForm({ ...form, account_id: e.target.value })}
          sx={{ mb: 2 }} helperText="unique folder name for this account" />
        <TextField fullWidth label="golden key" type="password"
          value={form.golden_key} onChange={e => setForm({ ...form, golden_key: e.target.value })}
          sx={{ mb: 2 }} helperText="funpay auth token from cookies" />
        <TextField fullWidth label="user agent"
          value={form.user_agent} onChange={e => setForm({ ...form, user_agent: e.target.value })}
          sx={{ mb: 2 }} helperText="browser user-agent string" />

        <Accordion sx={accordionSx}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.secondary' }}>proxy settings</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ px: 2, pb: 2 }}>
            <TextField fullWidth label="proxy" placeholder="socks5://user:pass@host:port"
              value={form.proxy || ''} onChange={e => setForm({ ...form, proxy: e.target.value })}
              helperText="leave empty for direct connection" />
          </AccordionDetails>
        </Accordion>

        <Accordion sx={accordionSx}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.secondary' }}>advanced</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ px: 2, pb: 2 }}>
            <FormControlLabel
              control={<Switch checked={form.disable_messages} onChange={e => setForm({ ...form, disable_messages: e.target.checked })} />}
              label="disable messages processing" sx={{ mb: 1 }} />
            <FormControlLabel
              control={<Switch checked={form.disable_orders} onChange={e => setForm({ ...form, disable_orders: e.target.checked })} />}
              label="disable orders processing" />
          </AccordionDetails>
        </Accordion>

        <AntiDetectAccordions ad={ad} setAd={setAd} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={loading || !form.account_id || !form.golden_key}>create</Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Account Settings Dialog ─────────────────────────

export function AccountSettingsDialog({ open, accountId, onClose, onSave }: {
  open: boolean; accountId: string; onClose: () => void; onSave: () => void;
}) {
  const [ad, setAd] = useState<AntiDetectForm>({ ...DEFAULT_AD });
  const [goldenKey, setGoldenKey] = useState('');
  const [userAgent, setUserAgent] = useState('');
  const [proxy, setProxy] = useState('');
  const [disableMessages, setDisableMessages] = useState(false);
  const [disableOrders, setDisableOrders] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !accountId) return;
    setLoading(true);
    accountsApi.getConfig(accountId)
      .then(r => {
        const d = r.data as any;
        setAd({ ...DEFAULT_AD, ...(d.anti_detect ?? {}) });
        setGoldenKey(d.golden_key ?? '');
        setUserAgent(d.user_agent ?? '');
        setProxy(d.proxy ?? '');
        setDisableMessages(d.disable_messages ?? false);
        setDisableOrders(d.disable_orders ?? false);
      })
      .catch(() => {
        setAd({ ...DEFAULT_AD });
        setGoldenKey(''); setUserAgent(''); setProxy('');
        setDisableMessages(false); setDisableOrders(false);
      })
      .finally(() => setLoading(false));
  }, [open, accountId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await accountsApi.updateConfig(accountId, {
        golden_key: goldenKey, user_agent: userAgent,
        proxy: proxy || null, disable_messages: disableMessages,
        disable_orders: disableOrders, anti_detect: ad,
      });
      onSave(); onClose();
    } catch { alert('Failed to save settings'); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>⚙️ settings - {accountId}</DialogTitle>
      <DialogContent sx={{ pt: '16px !important' }}>
        {loading ? (
          <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>loading...</Typography>
        ) : (
          <>
            <TextField fullWidth label="Golden Key" type="password"
              value={goldenKey} onChange={e => setGoldenKey(e.target.value)}
              sx={{ mb: 2 }} helperText="FunPay auth token from cookies" />
            <TextField fullWidth label="User Agent"
              value={userAgent} onChange={e => setUserAgent(e.target.value)}
              sx={{ mb: 2 }} helperText="Browser User-Agent string" />

            <Accordion sx={accordionSx}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2 }}>
                <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.secondary' }}>Proxy Settings</Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ px: 2, pb: 2 }}>
                <TextField fullWidth label="Proxy" placeholder="socks5://user:pass@host:port"
                  value={proxy} onChange={e => setProxy(e.target.value)}
                  helperText="Leave empty for direct connection" />
              </AccordionDetails>
            </Accordion>

            <Accordion sx={accordionSx}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2 }}>
                <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.secondary' }}>Advanced</Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ px: 2, pb: 2 }}>
                <FormControlLabel
                  control={<Switch checked={disableMessages} onChange={e => setDisableMessages(e.target.checked)} />}
                  label="Disable messages processing" sx={{ mb: 1 }} />
                <FormControlLabel
                  control={<Switch checked={disableOrders} onChange={e => setDisableOrders(e.target.checked)} />}
                  label="Disable orders processing" />
              </AccordionDetails>
            </Accordion>

            <AntiDetectAccordions ad={ad} setAd={setAd} defaultExpanded />
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving || loading}>Save</Button>
      </DialogActions>
    </Dialog>
  );
}
