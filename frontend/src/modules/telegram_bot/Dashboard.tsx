import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Table, TableHead, TableBody, TableRow,
  TableCell, Chip, alpha, Skeleton, IconButton, Tooltip,
} from '@mui/material';
import Grid from '@mui/material/Grid2';
import {
  Telegram as TelegramIcon,
  People as PeopleIcon,
  Notifications as NotificationsIcon,
  DeleteSweep as ClearIcon,
  Send as SendIcon,
} from '@mui/icons-material';
import { StatCard } from '../../components/GlowCard';
import { PageHeader } from '../../components/PageHeader';
import { TablePaper } from '../../components/TablePaper';
import { useLayout } from '../../components/Layout';
import { usePolling } from '../../hooks/usePolling';
import { telegramBotApi, BotInfo, EventLogEntry } from './api';

export default function TelegramBotDashboard() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [botInfo, setBotInfo] = useState<BotInfo | null>(null);
  const [events, setEvents] = useState<EventLogEntry[]>([]);
  const [whitelistCount, setWhitelistCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);

  useEffect(() => { load(); }, [accountId]);

  const load = async (silent = false) => {
    if (!accountId) return;
    try {
      const [info, evts, wl] = await Promise.all([
        telegramBotApi.getBotInfo(accountId),
        telegramBotApi.getEvents(accountId, 50),
        telegramBotApi.getWhitelist(accountId),
      ]);
      setBotInfo(info);
      setEvents(evts);
      setWhitelistCount(wl.length);
    } catch {
      if (!silent) notify('failed to load dashboard', 'error');
    } finally {
      setLoading(false);
    }
  };

  usePolling(() => load(true), 15000, !!accountId);

  const handleTest = async () => {
    if (!accountId || testing) return;
    setTesting(true);
    try {
      const res = await telegramBotApi.sendTest(accountId);
      notify(`test message sent: ${res.sent}/${res.total}`, 'success');
    } catch (e: any) {
      notify(e?.response?.data?.detail || 'failed to send test', 'error');
    } finally {
      setTesting(false);
    }
  };

  const handleClearEvents = async () => {
    if (!accountId) return;
    try {
      await telegramBotApi.clearEvents(accountId);
      setEvents([]);
      notify('event log cleared', 'success');
    } catch {
      notify('failed to clear events', 'error');
    }
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>telegram bot</Typography>
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {[0, 1, 2].map(i => (
            <Grid size={{ xs: 12, sm: 4 }} key={i}>
              <Skeleton variant="rounded" height={100} sx={{ bgcolor: '#1a1a1a' }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  const recentEvents = [...events].reverse();

  return (
    <Box>
      <PageHeader
        title="telegram bot"
        subtitle={
          botInfo?.online
            ? <Chip label={`@${botInfo.username}`} size="small" color="success" variant="outlined" />
            : <Chip label="offline" size="small" color="error" variant="outlined" />
        }
        onRefresh={() => load()}
        actions={
          <Tooltip title="send test message">
            <span>
              <IconButton
                onClick={handleTest}
                disabled={testing || !botInfo?.online}
                sx={{ bgcolor: 'rgba(255,255,255,0.04)' }}
              >
                <SendIcon />
              </IconButton>
            </span>
          </Tooltip>
        }
      />

      {/* Stats */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            label="bot status"
            value={botInfo?.online ? 'online' : 'offline'}
            icon={<TelegramIcon />}
            color={botInfo?.online ? '#22C55E' : '#EF4444'}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            label="whitelist"
            value={whitelistCount}
            icon={<PeopleIcon />}
            color="#3B82F6"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            label="events sent"
            value={events.length}
            icon={<NotificationsIcon />}
            color="#8B5CF6"
          />
        </Grid>
      </Grid>

      {/* Recent Events */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>recent events</Typography>
        {events.length > 0 && (
          <Tooltip title="clear event log">
            <IconButton size="small" onClick={handleClearEvents}>
              <ClearIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>

      <TablePaper>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>time</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>event</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>preview</TableCell>
              <TableCell sx={{ fontWeight: 600 }} align="right">delivered</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recentEvents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                  no events yet
                </TableCell>
              </TableRow>
            ) : (
              recentEvents.slice(0, 30).map((e, i) => (
                <TableRow key={i} sx={{ '&:hover': { bgcolor: alpha('#8B5CF6', 0.04) } }}>
                  <TableCell sx={{ whiteSpace: 'nowrap', color: 'text.secondary', fontSize: '0.8rem' }}>
                    {formatTimestamp(e.timestamp)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={e.event_type}
                      size="small"
                      sx={{
                        bgcolor: alpha(eventColor(e.event_type), 0.15),
                        color: eventColor(e.event_type),
                        fontWeight: 500,
                        fontSize: '0.75rem',
                      }}
                    />
                  </TableCell>
                  <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {stripHtml(e.text_preview)}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {e.sent_to}/{e.total}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TablePaper>
    </Box>
  );
}

// ─── Helpers ────────────────────────────────────

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('ru', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso.slice(0, 16);
  }
}

function eventColor(type: string): string {
  switch (type) {
    case 'new_order': return '#22C55E';
    case 'new_message': return '#3B82F6';
    case 'order_status_changed': return '#F59E0B';
    case 'orders_list_changed': return '#8B5CF6';
    default: return '#a0a0a0';
  }
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '').replace(/\n/g, ' ');
}
