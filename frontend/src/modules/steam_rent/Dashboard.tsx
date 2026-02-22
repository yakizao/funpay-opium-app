import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Typography, Table, TableHead, TableBody, TableRow,
  TableCell, Chip, alpha, Skeleton,
} from '@mui/material';
import Grid from '@mui/material/Grid2';
import {
  People as AccountsIcon,
  Gamepad as GamesIcon,
  Receipt as RentalsIcon,
  HourglassTop as PendingIcon,
} from '@mui/icons-material';
import { StatCard, StatusDot } from '../../components/GlowCard';
import { PageHeader } from '../../components/PageHeader';
import { TablePaper } from '../../components/TablePaper';
import { useLayout } from '../../components/Layout';
import { useCountdown } from '../../hooks/useCountdown';
import { usePolling } from '../../hooks/usePolling';
import { steamRentApi, SteamRentOverview, Rental } from './api';

export default function SteamRentDashboard() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const { formatRemaining, isExpiringSoon } = useCountdown();
  const [overview, setOverview] = useState<SteamRentOverview | null>(null);
  const [rentals, setRentals] = useState<Rental[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, [accountId]);

  const load = async (silent = false) => {
    if (!accountId) return;
    try {
      const [ov, rn] = await Promise.all([
        steamRentApi.getOverview(accountId),
        steamRentApi.getActiveRentals(accountId),
      ]);
      setOverview(ov.data);
      setRentals(rn.data);
    } catch { if (!silent) notify('failed to load dashboard', 'error'); }
    finally { setLoading(false); }
  };
  usePolling(() => load(true), 15000, !!accountId);

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>steam rent</Typography>
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {[...Array(4)].map((_, i) => (
            <Grid key={i} size={{ xs: 6, md: 3 }}>
              <Skeleton variant="rounded" height={100} sx={{ borderRadius: 4, bgcolor: 'rgba(255,255,255,0.04)' }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="steam rent" subtitle="module dashboard" onRefresh={load} />

      {/* Stats */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard label="active rentals" value={overview?.active_rentals ?? 0} icon={<RentalsIcon />} color="#22C55E" />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            label="steam accounts"
            value={
              <>
                {overview?.free_accounts ?? 0}
                <span style={{ opacity: 0.5 }}>
                  /{overview?.total_accounts ?? 0}
                  <span style={{ marginLeft: 4 }}> free</span>
                </span>
              </>
            }
            icon={<AccountsIcon />}
            color="#8B5CF6"
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard label="games" value={overview?.total_games ?? 0} icon={<GamesIcon />} color="#06B6D4" />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard label="pending orders" value={overview?.pending_orders ?? 0} icon={<PendingIcon />} color="#F59E0B" />
        </Grid>
      </Grid>

      {/* Active Rentals */}
      <Typography variant="h6" sx={{ mb: 2 }}>active rentals</Typography>
      <TablePaper>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>order</TableCell>
              <TableCell>buyer</TableCell>
              <TableCell>game</TableCell>
              <TableCell>account</TableCell>
              <TableCell>remaining</TableCell>
              <TableCell>bonus</TableCell>
              <TableCell>status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rentals.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                  no active rentals
                </TableCell>
              </TableRow>
            ) : (
              rentals.map(r => {
                const timeLeft = formatRemaining(r.end_time);
                const expiring = timeLeft !== 'expired' && isExpiringSoon(r.end_time);

                return (
                  <TableRow key={r.rental_id}>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace', color: 'text.primary' }}>
                        #{r.order_id}
                      </Typography>
                    </TableCell>
                    <TableCell>{r.buyer_username}</TableCell>
                    <TableCell>
                      <Chip size="small" label={r.game_id} sx={{ bgcolor: alpha('#06B6D4', 0.1), color: '#22D3EE', fontWeight: 500 }} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.primary' }}>
                        {r.steam_account_id}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{
                        fontWeight: 600, fontFamily: 'monospace',
                        color: timeLeft === 'expired' ? 'error.main' : expiring ? 'warning.main' : 'success.main',
                      }}>
                        {timeLeft}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {r.bonus_minutes > 0 ? (
                        <Chip size="small" label={`+${r.bonus_minutes}m`} sx={{ bgcolor: alpha('#22C55E', 0.1), color: '#22C55E', fontWeight: 600 }} />
                      ) : '-'}
                    </TableCell>
                    <TableCell>
                      <StatusDot status={r.status === 'active' ? 'running' : 'stopped'} />
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TablePaper>
    </Box>
  );
}
