import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, TextField, Button, IconButton, Tooltip,
  Table, TableHead, TableBody, TableRow, TableCell,
  Checkbox, FormControlLabel, Paper, Divider, alpha,
  Dialog, DialogTitle, DialogContent, DialogActions, Chip,
  Accordion, AccordionSummary, AccordionDetails, Switch,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  ExpandMore as ExpandIcon,
  Refresh as RestartIcon,
  Visibility as ShowIcon,
  VisibilityOff as HideIcon,
  Save as SaveIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/PageHeader';
import { TablePaper } from '../../components/TablePaper';
import { useLayout } from '../../components/Layout';
import { telegramBotApi, TelegramBotConfig, WhitelistEntry, BotInfo, LogWatcher, BotButton } from './api';

export default function TelegramBotSettings() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();

  const [config, setConfig] = useState<TelegramBotConfig | null>(null);
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([]);
  const [botInfo, setBotInfo] = useState<BotInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // Token
  const [tokenInput, setTokenInput] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [tokenDirty, setTokenDirty] = useState(false);
  const [savingToken, setSavingToken] = useState(false);

  // Event filters
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [eventsDirty, setEventsDirty] = useState(false);
  const [savingEvents, setSavingEvents] = useState(false);

  // Add whitelist dialog
  const [addOpen, setAddOpen] = useState(false);
  const [newId, setNewId] = useState('');
  const [newLabel, setNewLabel] = useState('');

  // Log Watchers
  const [watchers, setWatchers] = useState<LogWatcher[]>([]);
  const [watcherDialogOpen, setWatcherDialogOpen] = useState(false);
  const [editingWatcher, setEditingWatcher] = useState<LogWatcher | null>(null);
  const [watcherPattern, setWatcherPattern] = useState('');
  const [watcherCustomMsg, setWatcherCustomMsg] = useState('');

  // Bot Buttons
  const [buttons, setButtons] = useState<BotButton[]>([]);
  const [buttonDialogOpen, setButtonDialogOpen] = useState(false);
  const [editingButton, setEditingButton] = useState<BotButton | null>(null);
  const [btnLabel, setBtnLabel] = useState('');
  const [btnEndpoint, setBtnEndpoint] = useState('');
  const [btnMethod, setBtnMethod] = useState('GET');
  const [btnBody, setBtnBody] = useState('');
  const [btnDescription, setBtnDescription] = useState('');
  const [btnConfirm, setBtnConfirm] = useState(false);

  useEffect(() => { load(); }, [accountId]);

  const load = async () => {
    if (!accountId) return;
    try {
      const [cfg, wl, info, lw, bb] = await Promise.all([
        telegramBotApi.getConfig(accountId),
        telegramBotApi.getWhitelist(accountId),
        telegramBotApi.getBotInfo(accountId),
        telegramBotApi.getLogWatchers(accountId),
        telegramBotApi.getBotButtons(accountId),
      ]);
      setConfig(cfg);
      setWhitelist(wl);
      setBotInfo(info);
      setWatchers(lw);
      setButtons(bb);
      setTokenInput(cfg.bot_token);
      setSelectedEvents(cfg.notify_events);
      setTokenDirty(false);
      setEventsDirty(false);
    } catch {
      notify('failed to load settings', 'error');
    } finally {
      setLoading(false);
    }
  };

  // ─── Token ────────────────────────────────────

  const handleSaveToken = async () => {
    if (!accountId || !tokenDirty) return;
    setSavingToken(true);
    try {
      const res = await telegramBotApi.updateConfig(accountId, { bot_token: tokenInput });
      notify(res.restarted ? 'token saved, bot restarted' : 'token saved', 'success');
      setTokenDirty(false);
      // Reload bot info
      const info = await telegramBotApi.getBotInfo(accountId);
      setBotInfo(info);
    } catch (e: any) {
      notify(e?.response?.data?.detail || 'failed to save token', 'error');
    } finally {
      setSavingToken(false);
    }
  };

  const handleRestart = async () => {
    if (!accountId) return;
    try {
      await telegramBotApi.restartBot(accountId);
      notify('bot restarted', 'success');
      const info = await telegramBotApi.getBotInfo(accountId);
      setBotInfo(info);
    } catch (e: any) {
      notify(e?.response?.data?.detail || 'restart failed', 'error');
    }
  };

  // ─── Event Filters ────────────────────────────

  const handleToggleEvent = (key: string) => {
    setSelectedEvents(prev => {
      const next = prev.includes(key) ? prev.filter(e => e !== key) : [...prev, key];
      setEventsDirty(true);
      return next;
    });
  };

  const handleSaveEvents = async () => {
    if (!accountId || !eventsDirty) return;
    setSavingEvents(true);
    try {
      await telegramBotApi.updateConfig(accountId, { notify_events: selectedEvents });
      notify('event filters saved', 'success');
      setEventsDirty(false);
    } catch {
      notify('failed to save event filters', 'error');
    } finally {
      setSavingEvents(false);
    }
  };

  // ─── Whitelist ────────────────────────────────

  const handleAddWhitelist = async () => {
    if (!accountId) return;
    const id = parseInt(newId, 10);
    if (isNaN(id)) {
      notify('invalid telegram id', 'error');
      return;
    }
    try {
      await telegramBotApi.addToWhitelist(accountId, id, newLabel);
      setWhitelist(prev => [...prev, { telegram_id: id, label: newLabel }]);
      setAddOpen(false);
      setNewId('');
      setNewLabel('');
      notify('user added to whitelist', 'success');
    } catch (e: any) {
      notify(e?.response?.data?.detail || 'failed to add', 'error');
    }
  };

  const handleRemoveWhitelist = async (telegramId: number) => {
    if (!accountId) return;
    try {
      await telegramBotApi.removeFromWhitelist(accountId, telegramId);
      setWhitelist(prev => prev.filter(u => u.telegram_id !== telegramId));
      notify('user removed from whitelist', 'success');
    } catch {
      notify('failed to remove', 'error');
    }
  };

  if (loading || !config) {
    return (
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>settings</Typography>
        <Typography color="text.secondary">loading...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="settings" onRefresh={load} />

      {/* ─── Bot Token ──────────────────────────── */}
      <Accordion defaultExpanded sx={{ bgcolor: '#141414', mb: 2, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography sx={{ fontWeight: 600 }}>bot token</Typography>
            {botInfo?.online ? (
              <Chip label={`@${botInfo.username}`} size="small" color="success" variant="outlined" />
            ) : (
              <Chip label="offline" size="small" color="error" variant="outlined" />
            )}
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
            <TextField
              fullWidth
              size="small"
              label="Bot Token"
              type={showToken ? 'text' : 'password'}
              value={tokenInput}
              onChange={e => { setTokenInput(e.target.value); setTokenDirty(true); }}
              placeholder="123456:ABCdefGHIjklMNOpqrsTUVwxyz"
              slotProps={{
                input: {
                  endAdornment: (
                    <IconButton size="small" onClick={() => setShowToken(v => !v)}>
                      {showToken ? <HideIcon fontSize="small" /> : <ShowIcon fontSize="small" />}
                    </IconButton>
                  ),
                },
              }}
            />
            <Button
              variant="contained"
              disabled={!tokenDirty || savingToken}
              onClick={handleSaveToken}
              startIcon={<SaveIcon />}
              sx={{ minWidth: 100, whiteSpace: 'nowrap' }}
            >
              save
            </Button>
            <Tooltip title="restart bot">
              <span>
                <IconButton onClick={handleRestart} disabled={!config.has_token}>
                  <RestartIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            create a bot via @BotFather in Telegram and paste the token here
          </Typography>
        </AccordionDetails>
      </Accordion>

      {/* ─── Event Filters ──────────────────────── */}
      <Accordion defaultExpanded sx={{ bgcolor: '#141414', mb: 2, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandIcon />}>
          <Typography sx={{ fontWeight: 600 }}>event notifications</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            select which events trigger Telegram notifications
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            {config.available_events.map(ev => (
              <FormControlLabel
                key={ev.key}
                control={
                  <Checkbox
                    checked={selectedEvents.includes(ev.key)}
                    onChange={() => handleToggleEvent(ev.key)}
                    size="small"
                    sx={{ '&.Mui-checked': { color: '#8B5CF6' } }}
                  />
                }
                label={
                  <Box>
                    <Typography variant="body2">{ev.key}</Typography>
                    <Typography variant="caption" color="text.secondary">{ev.label}</Typography>
                  </Box>
                }
                sx={{
                  border: '1px solid',
                  borderColor: selectedEvents.includes(ev.key)
                    ? alpha('#8B5CF6', 0.3)
                    : 'rgba(255,255,255,0.06)',
                  borderRadius: 1,
                  px: 1.5,
                  py: 0.5,
                  m: 0,
                  transition: 'border-color 0.2s',
                }}
              />
            ))}
          </Box>
          <Button
            variant="contained"
            size="small"
            disabled={!eventsDirty || savingEvents}
            onClick={handleSaveEvents}
            startIcon={<SaveIcon />}
          >
            save filters
          </Button>
        </AccordionDetails>
      </Accordion>

      {/* ─── Whitelist ──────────────────────────── */}
      <Accordion defaultExpanded sx={{ bgcolor: '#141414', mb: 2, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography sx={{ fontWeight: 600 }}>whitelist</Typography>
            <Chip label={whitelist.length} size="small" variant="outlined" />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            only whitelisted Telegram users will receive notifications and can interact with the bot.
            users can send /start to the bot to see their Telegram ID.
          </Typography>

          <Button
            size="small"
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={() => setAddOpen(true)}
            sx={{ mb: 2 }}
          >
            add user
          </Button>

          <TablePaper>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>telegram id</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>label</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {whitelist.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} sx={{ textAlign: 'center', py: 3, color: 'text.secondary' }}>
                      whitelist is empty
                    </TableCell>
                  </TableRow>
                ) : (
                  whitelist.map(u => (
                    <TableRow key={u.telegram_id} sx={{ '&:hover': { bgcolor: alpha('#8B5CF6', 0.04) } }}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                          {u.telegram_id}
                        </Typography>
                      </TableCell>
                      <TableCell>{u.label || '—'}</TableCell>
                      <TableCell align="right">
                        <Tooltip title="remove">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleRemoveWhitelist(u.telegram_id)}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TablePaper>
        </AccordionDetails>
      </Accordion>

      {/* ─── Bot Buttons (Remote Control) ─────── */}
      <Accordion defaultExpanded sx={{ bgcolor: '#141414', mb: 2, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography sx={{ fontWeight: 600 }}>bot buttons</Typography>
            <Chip label={buttons.length} size="small" variant="outlined" />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            add buttons that appear in Telegram via /menu command.
            each button calls an API endpoint and returns the result.
            use {'{'}<code>account_id</code>{'}'} in the endpoint — it will be replaced automatically.
          </Typography>

          <Button
            size="small"
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={() => {
              setEditingButton(null);
              setBtnLabel('');
              setBtnEndpoint('');
              setBtnMethod('GET');
              setBtnBody('');
              setBtnDescription('');
              setBtnConfirm(false);
              setButtonDialogOpen(true);
            }}
            sx={{ mb: 2 }}
          >
            add button
          </Button>

          <TablePaper>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>label</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>endpoint</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>method</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="center">confirm</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="center">enabled</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {buttons.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} sx={{ textAlign: 'center', py: 3, color: 'text.secondary' }}>
                      no buttons configured — add one to see it in /menu
                    </TableCell>
                  </TableRow>
                ) : (
                  buttons.map(b => (
                    <TableRow key={b.id} sx={{ '&:hover': { bgcolor: alpha('#8B5CF6', 0.04) } }}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>{b.label}</Typography>
                        {b.description && (
                          <Typography variant="caption" color="text.secondary">{b.description}</Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 11 }}>
                          {b.api_endpoint}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={b.api_method} size="small" variant="outlined"
                          color={b.api_method === 'GET' ? 'info' : b.api_method === 'POST' ? 'warning' : 'error'}
                        />
                      </TableCell>
                      <TableCell align="center">
                        {b.confirm ? '⚠️' : '—'}
                      </TableCell>
                      <TableCell align="center">
                        <Switch
                          size="small"
                          checked={b.enabled}
                          onChange={async () => {
                            if (!accountId) return;
                            try {
                              await telegramBotApi.updateBotButton(accountId, b.id, { enabled: !b.enabled });
                              setButtons(prev => prev.map(x => x.id === b.id ? { ...x, enabled: !x.enabled } : x));
                            } catch {
                              notify('failed to update', 'error');
                            }
                          }}
                          sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#8B5CF6' } }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="edit">
                          <IconButton
                            size="small"
                            onClick={() => {
                              setEditingButton(b);
                              setBtnLabel(b.label);
                              setBtnEndpoint(b.api_endpoint);
                              setBtnMethod(b.api_method);
                              setBtnBody(b.api_body ? JSON.stringify(b.api_body, null, 2) : '');
                              setBtnDescription(b.description);
                              setBtnConfirm(b.confirm);
                              setButtonDialogOpen(true);
                            }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={async () => {
                              if (!accountId) return;
                              try {
                                await telegramBotApi.deleteBotButton(accountId, b.id);
                                setButtons(prev => prev.filter(x => x.id !== b.id));
                                notify('button removed', 'success');
                              } catch {
                                notify('failed to remove', 'error');
                              }
                            }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TablePaper>
        </AccordionDetails>
      </Accordion>

      {/* ─── Log Watchers ──────────────────────── */}
      <Accordion defaultExpanded sx={{ bgcolor: '#141414', mb: 2, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography sx={{ fontWeight: 600 }}>log watchers</Typography>
            <Chip label={watchers.length} size="small" variant="outlined" />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            forward specific log messages to Telegram. specify a substring to match —
            if it appears anywhere in a log line, the bot will send it.
            optionally set a custom message instead of the raw log.
          </Typography>

          <Button
            size="small"
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={() => {
              setEditingWatcher(null);
              setWatcherPattern('');
              setWatcherCustomMsg('');
              setWatcherDialogOpen(true);
            }}
            sx={{ mb: 2 }}
          >
            add watcher
          </Button>

          <TablePaper>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>pattern</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>custom message</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="center">enabled</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {watchers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} sx={{ textAlign: 'center', py: 3, color: 'text.secondary' }}>
                      no log watchers configured
                    </TableCell>
                  </TableRow>
                ) : (
                  watchers.map(w => (
                    <TableRow key={w.id} sx={{ '&:hover': { bgcolor: alpha('#8B5CF6', 0.04) } }}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                          {w.pattern}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color={w.custom_message ? 'text.primary' : 'text.secondary'}>
                          {w.custom_message || '— raw log —'}
                        </Typography>
                      </TableCell>
                      <TableCell align="center">
                        <Switch
                          size="small"
                          checked={w.enabled}
                          onChange={async () => {
                            if (!accountId) return;
                            try {
                              await telegramBotApi.updateLogWatcher(accountId, w.id, { enabled: !w.enabled });
                              setWatchers(prev => prev.map(x => x.id === w.id ? { ...x, enabled: !x.enabled } : x));
                            } catch {
                              notify('failed to update', 'error');
                            }
                          }}
                          sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#8B5CF6' } }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="edit">
                          <IconButton
                            size="small"
                            onClick={() => {
                              setEditingWatcher(w);
                              setWatcherPattern(w.pattern);
                              setWatcherCustomMsg(w.custom_message);
                              setWatcherDialogOpen(true);
                            }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={async () => {
                              if (!accountId) return;
                              try {
                                await telegramBotApi.deleteLogWatcher(accountId, w.id);
                                setWatchers(prev => prev.filter(x => x.id !== w.id));
                                notify('watcher removed', 'success');
                              } catch {
                                notify('failed to remove', 'error');
                              }
                            }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TablePaper>
        </AccordionDetails>
      </Accordion>

      {/* ─── Add/Edit Button Dialog ──────────── */}
      <Dialog
        open={buttonDialogOpen}
        onClose={() => setButtonDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 600 }}>
          {editingButton ? 'edit bot button' : 'add bot button'}
        </DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField
            label="Button label"
            value={btnLabel}
            onChange={e => setBtnLabel(e.target.value)}
            size="small"
            placeholder="🎮 Guard Code"
            helperText="text shown on the button in Telegram (supports emoji)"
          />
          <TextField
            label="API endpoint"
            value={btnEndpoint}
            onChange={e => setBtnEndpoint(e.target.value)}
            size="small"
            placeholder="/api/accounts/{account_id}/modules/steam_rent/guard/login"
            helperText="{account_id} will be replaced automatically"
          />
          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              select
              label="Method"
              value={btnMethod}
              onChange={e => setBtnMethod(e.target.value)}
              size="small"
              sx={{ minWidth: 100 }}
              slotProps={{ select: { native: true } }}
            >
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="DELETE">DELETE</option>
            </TextField>
            <FormControlLabel
              control={
                <Checkbox
                  checked={btnConfirm}
                  onChange={e => setBtnConfirm(e.target.checked)}
                  size="small"
                  sx={{ '&.Mui-checked': { color: '#8B5CF6' } }}
                />
              }
              label="ask confirmation"
            />
          </Box>
          {btnMethod === 'POST' && (
            <TextField
              label="Request body (JSON, optional)"
              value={btnBody}
              onChange={e => setBtnBody(e.target.value)}
              size="small"
              multiline
              rows={3}
              placeholder='{"key": "value"}'
            />
          )}
          <TextField
            label="Description (optional)"
            value={btnDescription}
            onChange={e => setBtnDescription(e.target.value)}
            size="small"
            placeholder="Get Steam Guard code for login"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setButtonDialogOpen(false)}>cancel</Button>
          <Button
            variant="contained"
            disabled={!btnLabel.trim() || !btnEndpoint.trim()}
            onClick={async () => {
              if (!accountId) return;
              let parsedBody: Record<string, unknown> | null = null;
              if (btnBody.trim()) {
                try {
                  parsedBody = JSON.parse(btnBody);
                } catch {
                  notify('invalid JSON body', 'error');
                  return;
                }
              }
              try {
                if (editingButton) {
                  await telegramBotApi.updateBotButton(accountId, editingButton.id, {
                    label: btnLabel.trim(),
                    api_endpoint: btnEndpoint.trim(),
                    api_method: btnMethod,
                    api_body: parsedBody,
                    description: btnDescription.trim(),
                    confirm: btnConfirm,
                  });
                  setButtons(prev => prev.map(b =>
                    b.id === editingButton.id
                      ? {
                          ...b,
                          label: btnLabel.trim(),
                          api_endpoint: btnEndpoint.trim(),
                          api_method: btnMethod,
                          api_body: parsedBody,
                          description: btnDescription.trim(),
                          confirm: btnConfirm,
                        }
                      : b,
                  ));
                  notify('button updated', 'success');
                } else {
                  const created = await telegramBotApi.addBotButton(accountId, {
                    label: btnLabel.trim(),
                    api_endpoint: btnEndpoint.trim(),
                    api_method: btnMethod,
                    api_body: parsedBody,
                    description: btnDescription.trim(),
                    confirm: btnConfirm,
                  });
                  setButtons(prev => [...prev, created]);
                  notify('button added', 'success');
                }
                setButtonDialogOpen(false);
              } catch {
                notify('failed to save button', 'error');
              }
            }}
          >
            {editingButton ? 'save' : 'add'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Add/Edit Watcher Dialog ────────────── */}
      <Dialog
        open={watcherDialogOpen}
        onClose={() => setWatcherDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 600 }}>
          {editingWatcher ? 'edit log watcher' : 'add log watcher'}
        </DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField
            label="Pattern (substring to match)"
            value={watcherPattern}
            onChange={e => setWatcherPattern(e.target.value)}
            size="small"
            placeholder="[auto_raise] Raised:"
            helperText="the bot will search for this text in every log line"
          />
          <TextField
            label="Custom message (optional)"
            value={watcherCustomMsg}
            onChange={e => setWatcherCustomMsg(e.target.value)}
            size="small"
            placeholder="lots raised successfully"
            helperText="leave empty to forward the raw log line"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWatcherDialogOpen(false)}>cancel</Button>
          <Button
            variant="contained"
            disabled={!watcherPattern.trim()}
            onClick={async () => {
              if (!accountId) return;
              try {
                if (editingWatcher) {
                  await telegramBotApi.updateLogWatcher(accountId, editingWatcher.id, {
                    pattern: watcherPattern.trim(),
                    custom_message: watcherCustomMsg.trim(),
                  });
                  setWatchers(prev => prev.map(w =>
                    w.id === editingWatcher.id
                      ? { ...w, pattern: watcherPattern.trim(), custom_message: watcherCustomMsg.trim() }
                      : w,
                  ));
                  notify('watcher updated', 'success');
                } else {
                  const created = await telegramBotApi.addLogWatcher(accountId, {
                    pattern: watcherPattern.trim(),
                    custom_message: watcherCustomMsg.trim(),
                  });
                  setWatchers(prev => [...prev, created]);
                  notify('watcher added', 'success');
                }
                setWatcherDialogOpen(false);
              } catch {
                notify('failed to save watcher', 'error');
              }
            }}
          >
            {editingWatcher ? 'save' : 'add'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Add User Dialog ────────────────────── */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 600 }}>add to whitelist</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField
            label="Telegram ID"
            value={newId}
            onChange={e => setNewId(e.target.value)}
            size="small"
            type="number"
            placeholder="123456789"
            helperText="send /start to the bot to get your ID"
          />
          <TextField
            label="Label (optional)"
            value={newLabel}
            onChange={e => setNewLabel(e.target.value)}
            size="small"
            placeholder="Admin"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>cancel</Button>
          <Button variant="contained" onClick={handleAddWhitelist} disabled={!newId}>
            add
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
