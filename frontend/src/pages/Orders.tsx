import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { usePolling } from '../hooks/usePolling';
import {
  Box, Typography, Chip, Button, Tooltip, IconButton, alpha,
  Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import { Undo as RefundIcon } from '@mui/icons-material';
import { accountsApi, OrderShort, OrderTagInfo, OrderTagsResponse } from '../api/client';
import { useLayout } from '../components/Layout';
import { PageHeader } from '../components/PageHeader';
import { DataTable, type Column, type FilterGroup } from '../components/DataTable';

const statusColor: Record<string, string> = {
  paid: '#22C55E', closed: '#707070', refunded: '#F59E0B', dispute: '#EF4444',
};

const normalizeStatus = (s: string) => {
  let v = s;
  if (v.includes('.')) v = v.split('.').pop()!;
  return v.toLowerCase();
};

export default function OrdersPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [orders, setOrders] = useState<OrderShort[]>([]);
  const [tags, setTags] = useState<Record<string, OrderTagInfo>>({});
  const [modules, setModules] = useState<string[]>([]);
  const [gamesByModule, setGamesByModule] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [refundDialog, setRefundDialog] = useState<string | null>(null);

  const [filterModule, setFilterModule] = useState('all');
  const [filterGame, setFilterGame] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => { loadAll(); }, [accountId]);
  useEffect(() => { setFilterGame('all'); }, [filterModule]);

  const loadAll = useCallback(async (silent = false) => {
    if (!accountId) return;
    if (!silent) setLoading(true);
    try {
      const [ordersRes, tagsRes] = await Promise.all([
        accountsApi.getOrders(accountId),
        accountsApi.getOrderTags(accountId).catch(() => ({ data: { tags: {}, modules: [], games: {} } as OrderTagsResponse })),
      ]);
      setOrders(ordersRes.data.orders);
      setTags(tagsRes.data.tags);
      setModules(tagsRes.data.modules);
      setGamesByModule(tagsRes.data.games);
    } catch { if (!silent) notify('failed to load orders', 'error'); }
    finally { setLoading(false); }
  }, [accountId, notify]);
  usePolling(() => loadAll(true), 30000, !!accountId);

  const currentGames = useMemo(() => {
    if (filterModule === 'all') {
      const all = new Set<string>();
      for (const gList of Object.values(gamesByModule)) {
        for (const g of gList) all.add(g);
      }
      return [...all].sort();
    }
    return gamesByModule[filterModule] || [];
  }, [filterModule, gamesByModule]);

  const filtered = useMemo(() => {
    return orders.filter(o => {
      const tag = tags[o.order_id];
      if (filterModule !== 'all' && (!tag || tag.module !== filterModule)) return false;
      if (filterGame !== 'all' && (!tag || tag.game_id !== filterGame)) return false;
      if (filterStatus !== 'all' && normalizeStatus(o.status) !== filterStatus) return false;
      return true;
    });
  }, [orders, tags, filterModule, filterGame, filterStatus]);

  const statuses = useMemo(() => {
    const s = new Set<string>();
    orders.forEach(o => s.add(normalizeStatus(o.status)));
    return Array.from(s);
  }, [orders]);

  const handleRefund = async (orderId: string) => {
    if (!accountId) return;
    try {
      await accountsApi.refundOrder(accountId, orderId);
      notify(`order #${orderId} refunded`, 'success');
      setRefundDialog(null);
      loadAll();
    } catch { notify('refund failed', 'error'); }
  };

  const columns: Column<OrderShort>[] = useMemo(() => [
    {
      id: 'order_id', label: 'order', sortable: true, width: 100,
      sortValue: o => o.order_id,
      searchValue: o => o.order_id,
      render: o => (
        <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace', color: 'text.primary' }}>
          #{o.order_id}
        </Typography>
      ),
    },
    {
      id: 'description', label: 'description', sortable: true,
      sortValue: o => o.description,
      searchValue: o => o.description,
      render: o => (
        <Typography variant="body2" sx={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {o.description}
        </Typography>
      ),
    },
    {
      id: 'price', label: 'price', sortable: true, align: 'right', width: 90,
      sortValue: o => parseFloat(o.price.replace(/[^\d.]/g, '')) || 0,
      render: o => (
        <Typography variant="body2" sx={{ fontWeight: 600, color: '#22C55E' }}>{o.price}</Typography>
      ),
    },
    {
      id: 'buyer', label: 'buyer', sortable: true,
      sortValue: o => o.buyer,
      searchValue: o => o.buyer,
      render: o => <Typography variant="body2">{o.buyer}</Typography>,
    },
    {
      id: 'status', label: 'status', sortable: true, width: 100,
      sortValue: o => normalizeStatus(o.status),
      render: o => {
        const s = normalizeStatus(o.status);
        return (
          <Chip size="small" label={s} sx={{
            bgcolor: alpha(statusColor[s] || '#707070', 0.12),
            color: statusColor[s] || '#a0a0a0', fontWeight: 600,
          }} />
        );
      },
    },
    {
      id: 'date', label: 'date', sortable: true, width: 140,
      sortValue: o => o.date,
      render: o => <Typography variant="caption" color="text.secondary">{o.date}</Typography>,
    },
    {
      id: 'actions', label: '', align: 'right', width: 60,
      render: o => o.status.toLowerCase() === 'paid' ? (
        <Tooltip title="refund">
          <IconButton size="small" onClick={() => setRefundDialog(o.order_id)} color="warning">
            <RefundIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ) : null,
    },
  ], []);

  const filterGroups: FilterGroup[] = useMemo(() => {
    const groups: FilterGroup[] = [];
    if (modules.length > 0) {
      groups.push({
        label: 'module', value: filterModule, onChange: setFilterModule,
        options: [
          { label: 'all', value: 'all', count: orders.length },
          ...modules.map(m => ({
            label: m.replace(/_/g, ' '), value: m,
            count: orders.filter(o => tags[o.order_id]?.module === m).length,
            color: '#8B5CF6',
          })),
        ],
      });
    }
    if (currentGames.length > 0) {
      groups.push({
        label: 'game', value: filterGame, onChange: setFilterGame,
        options: [
          { label: 'all games', value: 'all' },
          ...currentGames.map(g => ({ label: g, value: g, color: '#06B6D4' })),
        ],
      });
    }
    groups.push({
      label: 'status', value: filterStatus, onChange: setFilterStatus,
      options: [
        { label: 'all', value: 'all', count: orders.length },
        ...statuses.map(s => ({
          label: s, value: s,
          count: orders.filter(o => normalizeStatus(o.status) === s).length,
          color: statusColor[s] || '#707070',
        })),
      ],
    });
    return groups;
  }, [modules, filterModule, currentGames, filterGame, filterStatus, orders, tags, statuses]);

  return (
    <Box>
      <PageHeader
        title="orders"
        subtitle={<>{filtered.length}<span style={{ opacity: 0.5 }}> / {orders.length} orders</span></>}
        onRefresh={loadAll}
      />

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={o => o.order_id}
        loading={loading}
        emptyMessage="no orders found"
        filters={filterGroups}
        searchPlaceholder="search orders..."
        defaultSortColumn="date"
        defaultSortDirection="desc"
      />

      <Dialog open={!!refundDialog} onClose={() => setRefundDialog(null)} maxWidth="xs" fullWidth>
        <DialogTitle>confirm refund</DialogTitle>
        <DialogContent>
          <Typography>refund order #{refundDialog}? this action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRefundDialog(null)}>cancel</Button>
          <Button variant="contained" color="warning" onClick={() => refundDialog && handleRefund(refundDialog)}>refund</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
