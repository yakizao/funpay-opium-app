import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Button, TextField, Paper, Chip, Tooltip, IconButton,
  Accordion, AccordionSummary, AccordionDetails, alpha, InputAdornment,
  Dialog, DialogTitle, DialogContent, DialogActions, Alert,
} from '@mui/material';
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  RestartAlt as ResetIcon,
  Search as SearchIcon,
  Preview as PreviewIcon,
  HelpOutline as HelpIcon,
  Timer as TimerIcon,
} from '@mui/icons-material';
import { useLayout } from '../../components/Layout';
import { usePolling } from '../../hooks/usePolling';
import { steamRentApi, MessagesResponse } from './api';

// ── Types (from API) ───────────────────────────────────

interface MessageGroup {
  id: string;
  label: string;
  description: string;
  keys: string[];
}

interface MessageMeta {
  label: string;
  placeholders: string[];
  examples: Record<string, string>;
  stale?: boolean;
  unknown_placeholders?: string[];
}

// ── Placeholder help dialog ─────────────────────────────

function PlaceholderHelpDialog({ open, onClose, docs }: {
  open: boolean; onClose: () => void; docs: Record<string, string>;
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>плейсхолдеры</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Вставляйте плейсхолдеры в шаблоны в формате{' {}’'}. При отправке сообщения они автоматически заменяются на реальные данные.
          Если плейсхолдер пустой — строка с ним автоматически убирается из сообщения.
        </Typography>
        <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse' }}>
          <Box component="thead">
            <Box component="tr" sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Box component="th" sx={{ textAlign: 'left', py: 1, pr: 2 }}>
                <Typography variant="caption" fontWeight={700}>плейсхолдер</Typography>
              </Box>
              <Box component="th" sx={{ textAlign: 'left', py: 1 }}>
                <Typography variant="caption" fontWeight={700}>описание</Typography>
              </Box>
            </Box>
          </Box>
          <Box component="tbody">
            {Object.entries(docs).map(([key, desc]) => (
              <Box component="tr" key={key} sx={{ borderBottom: 1, borderColor: 'divider', '&:last-child': { border: 0 } }}>
                <Box component="td" sx={{ py: 0.75, pr: 2, whiteSpace: 'nowrap' }}>
                  <Chip
                    size="small"
                    label={`{${key}}`}
                    variant="outlined"
                    sx={{
                      height: 22, fontSize: 12, fontFamily: 'monospace',
                      borderColor: alpha('#a78bfa', 0.5), color: '#a78bfa',
                    }}
                  />
                </Box>
                <Box component="td" sx={{ py: 0.75 }}>
                  <Typography variant="body2" color="text.secondary">{desc}</Typography>
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>закрыть</Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Preview dialog ─────────────────────────────────────

function PreviewDialog({ open, onClose, template, meta }: {
  open: boolean; onClose: () => void; template: string; meta: MessageMeta;
}) {
  let preview = template;
  try {
    for (const p of meta.placeholders) {
      preview = preview.split(`{${p}}`).join(meta.examples[p] ?? `[${p}]`);
    }
  } catch { /* keep raw */ }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>предпросмотр сообщения</DialogTitle>
      <DialogContent>
        <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default', whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 14 }}>
          {preview}
        </Paper>
        {meta.placeholders.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">
              пример данных: {meta.placeholders.map(p => `${p}="${meta.examples[p] ?? '...'}"`).join(', ')}
            </Typography>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>закрыть</Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Main page ──────────────────────────────────────────

export default function MessagesPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();

  const [data, setData] = useState<MessagesResponse | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [warningMinutes, setWarningMinutes] = useState(0);
  const [warningMinutesSaved, setWarningMinutesSaved] = useState(0);

  const load = useCallback(async (silent = false) => {
    if (!accountId) return;
    if (!silent) setLoading(true);
    try {
      const [messagesRes, configRes] = await Promise.all([
        steamRentApi.getMessages(accountId),
        steamRentApi.getConfig(accountId),
      ]);
      setData(messagesRes.data);
      const mins = Number(configRes.data.expiry_warning_minutes ?? 0);
      setWarningMinutes(mins);
      setWarningMinutesSaved(mins);
      if (!silent) setEdits({});
    } catch { if (!silent) notify('failed to load messages', 'error'); }
    if (!silent) setLoading(false);
  }, [accountId, notify]);

  useEffect(() => { load(); }, [load]);

  const changedKeys = useMemo(() => {
    if (!data) return new Set<string>();
    const s = new Set<string>();
    for (const [key, val] of Object.entries(edits)) {
      if (val !== data.messages[key]) s.add(key);
    }
    return s;
  }, [edits, data]);

  usePolling(() => load(true), 30000, !!accountId && changedKeys.size === 0 && warningMinutes === warningMinutesSaved);

  const isModifiedFromDefault = (key: string): boolean => {
    if (!data) return false;
    const current = edits[key] ?? data.messages[key];
    return current !== data.defaults[key];
  };

  const handleChange = (key: string, value: string) => {
    setEdits(prev => ({ ...prev, [key]: value }));
  };

  const handleReset = (key: string) => {
    if (!data) return;
    setEdits(prev => ({ ...prev, [key]: data.defaults[key] }));
  };

  const handleSave = async () => {
    if (!accountId || !data) return;
    setSaving(true);
    try {
      const promises: Promise<unknown>[] = [];

      if (changedKeys.size > 0) {
        const payload: Record<string, string | null> = {};
        for (const key of changedKeys) {
          const val = edits[key];
          payload[key] = val === data.defaults[key] ? null : val;
        }
        promises.push(
          steamRentApi.updateMessages(accountId, payload).then(r => {
            setData(prev => prev ? { ...prev, messages: r.data.messages } : prev);
            setEdits({});
          }),
        );
      }

      if (warningMinutes !== warningMinutesSaved) {
        promises.push(
          steamRentApi.updateConfig(accountId, { expiry_warning_minutes: warningMinutes }).then(() => {
            setWarningMinutesSaved(warningMinutes);
          }),
        );
      }

      await Promise.all(promises);
      notify('Сохранено', 'success');
    } catch { notify('Ошибка сохранения', 'error'); }
    setSaving(false);
  };

  const filteredGroups = useMemo(() => {
    if (!data) return [];
    const groups: MessageGroup[] = data.groups;
    if (!search) return groups;
    const q = search.toLowerCase();
    return groups.map(g => ({
      ...g,
      keys: g.keys.filter(k => {
        const meta = data.meta[k];
        const label = meta?.label ?? k;
        const template = edits[k] ?? data.messages[k] ?? '';
        return k.includes(q) || label.toLowerCase().includes(q) || template.toLowerCase().includes(q);
      }),
    })).filter(g => g.keys.length > 0);
  }, [search, data, edits]);

  if (!data) return <Box sx={{ p: 3 }}><Typography>loading…</Typography></Box>;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h5" fontWeight={700}>шаблоны сообщений</Typography>
          <Tooltip title="справка по плейсхолдерам">
            <IconButton size="small" onClick={() => setHelpOpen(true)} sx={{ color: 'text.secondary' }}>
              <HelpIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Typography variant="body2" color="text.secondary">
            настройка всех сообщений, отправляемых покупателям. используйте {'{плейсхолдеры}'} для динамических данных.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button startIcon={<RefreshIcon />} onClick={() => load()} disabled={loading}>
            обновить
          </Button>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={(changedKeys.size === 0 && warningMinutes === warningMinutesSaved) || saving}
          >
            сохранить{changedKeys.size + (warningMinutes !== warningMinutesSaved ? 1 : 0) > 0
              ? ` (${changedKeys.size + (warningMinutes !== warningMinutesSaved ? 1 : 0)})`
              : ''}
          </Button>
        </Box>
      </Box>

      {/* Search */}
      <TextField
        size="small"
        placeholder="поиск по шаблонам…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        sx={{ mb: 2, width: 350 }}
        InputProps={{
          startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>,
        }}
      />

      {/* Groups */}
      {filteredGroups.map(group => (
        <Accordion
          key={group.id}
          defaultExpanded
          disableGutters
          sx={{
            mb: 1,
            bgcolor: 'background.paper',
            '&:before': { display: 'none' },
            borderRadius: 1,
            overflow: 'hidden',
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography fontWeight={600}>{group.label}</Typography>
              <Typography variant="caption" color="text.secondary">- {group.description}</Typography>
              {group.keys.some(k => changedKeys.has(k)) && (
                <Chip size="small" label="изменено" color="warning" sx={{ ml: 1, height: 20 }} />
              )}
            </Box>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            {/* Expiry warning minutes config — inside the expiry group */}
            {group.id === 'expiry' && (
              <Paper
                variant="outlined"
                sx={{
                  p: 2, mb: 1.5, display: 'flex', alignItems: 'center', gap: 2,
                  borderColor: warningMinutes !== warningMinutesSaved ? 'warning.main' : 'divider',
                }}
              >
                <TimerIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="subtitle2" fontWeight={600}>
                    за сколько минут предупреждать
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    за сколько минут до конца аренды отправить предупреждение покупателю. 0 = выключено.
                  </Typography>
                </Box>
                <TextField
                  size="small"
                  type="number"
                  value={warningMinutes}
                  onChange={e => setWarningMinutes(Math.max(0, parseInt(e.target.value) || 0))}
                  sx={{ width: 120 }}
                  inputProps={{ min: 0 }}
                  InputProps={{
                    endAdornment: <InputAdornment position="end">мин</InputAdornment>,
                  }}
                />
              </Paper>
            )}
            {group.keys.map(key => {
              const current = edits[key] ?? data.messages[key] ?? '';
              const meta = data.meta[key];
              const placeholders = meta?.placeholders ?? [];
              const modified = isModifiedFromDefault(key);
              const unsaved = changedKeys.has(key);

              return (
                <Paper
                  key={key}
                  variant="outlined"
                  sx={{
                    p: 2, mb: 1.5,
                    borderColor: unsaved
                      ? 'warning.main'
                      : modified
                        ? alpha('#a78bfa', 0.4)
                        : 'divider',
                  }}
                >
                  {/* Label row */}
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="subtitle2" fontWeight={600}>
                        {meta?.label ?? key}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                        {key}
                      </Typography>
                      {modified && (
                        <Chip size="small" label="кастом" variant="outlined" sx={{ height: 18, fontSize: 11 }} />
                      )}
                    </Box>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <Tooltip title="предпросмотр">
                        <IconButton size="small" onClick={() => setPreviewKey(key)}>
                          <PreviewIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      {modified && (
                        <Tooltip title="сбросить на дефолт">
                          <IconButton size="small" color="warning" onClick={() => handleReset(key)}>
                            <ResetIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  </Box>

                  {/* Stale override warning */}
                  {meta?.stale && (
                    <Alert severity="warning" sx={{ mb: 1, py: 0 }}>
                      шаблон содержит несуществующие плейсхолдеры: {meta.unknown_placeholders?.map(p => `{${p}}`).join(', ')}.
                      Сбросьте на дефолт нажав ⟲ или исправьте вручную. 
                    </Alert>
                  )}

                  {/* Placeholders */}
                  {placeholders.length > 0 && (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                      {placeholders.map(p => (
                        <Tooltip key={p} title={data.placeholder_docs?.[p] ?? p} arrow>
                          <Chip
                            size="small"
                            label={`{${p}}`}
                            variant="outlined"
                            sx={{
                              height: 22, fontSize: 12, fontFamily: 'monospace',
                              borderColor: alpha('#a78bfa', 0.5),
                              color: '#a78bfa',
                              cursor: 'pointer',
                            }}
                            onClick={() => {
                              navigator.clipboard.writeText(`{${p}}`);
                              notify(`{${p}} скопировано`, 'info');
                            }}
                          />
                        </Tooltip>
                      ))}
                    </Box>
                  )}

                  {/* Template editor */}
                  <TextField
                    fullWidth
                    multiline
                    minRows={1}
                    maxRows={10}
                    size="small"
                    value={current}
                    onChange={e => handleChange(key, e.target.value)}
                    sx={{
                      '& .MuiInputBase-root': {
                        fontFamily: 'monospace',
                        fontSize: 13,
                      },
                    }}
                  />
                </Paper>
              );
            })}
          </AccordionDetails>
        </Accordion>
      ))}

      {/* Placeholder help dialog */}
      {data && (
        <PlaceholderHelpDialog
          open={helpOpen}
          onClose={() => setHelpOpen(false)}
          docs={data.placeholder_docs ?? {}}
        />
      )}

      {/* Preview dialog */}
      {previewKey && data && (
        <PreviewDialog
          open={!!previewKey}
          onClose={() => setPreviewKey(null)}
          template={edits[previewKey] ?? data.messages[previewKey] ?? ''}
          meta={data.meta[previewKey] ?? { label: previewKey, placeholders: [], examples: {} }}
        />
      )}
    </Box>
  );
}
