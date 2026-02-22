import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { usePolling } from '../hooks/usePolling';
import {
  Box, Typography, TextField, IconButton, Paper, List, ListItemButton,
  ListItemText, Divider, alpha, InputAdornment, Skeleton, Badge, Chip,
} from '@mui/material';
import {
  Send as SendIcon,
  Search as SearchIcon,
  ShoppingBag as OrdersIcon,
} from '@mui/icons-material';
import { accountsApi, ChatShort, Message, OrderShort } from '../api/client';
import { useLayout } from '../components/Layout';

/* ─── Status color helpers ─────────────────────────── */
const statusColor = (s: string) => {
  const sl = s.toLowerCase();
  if (sl.includes('paid')) return '#10B981';
  if (sl.includes('closed')) return '#6B7280';
  if (sl.includes('refund')) return '#EF4444';
  return '#8B5CF6';
};

export default function ChatsPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [chats, setChats] = useState<ChatShort[]>([]);
  const [selectedChat, setSelectedChat] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [accountUsername, setAccountUsername] = useState<string | null>(null);
  const [buyerOrders, setBuyerOrders] = useState<OrderShort[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);

  /* ─── Load account username once ─────────────────── */
  useEffect(() => {
    if (!accountId) return;
    accountsApi.get(accountId)
      .then(res => setAccountUsername(res.data.username ?? null))
      .catch(() => {});
  }, [accountId]);

  useEffect(() => {
    if (!accountId) return;
    loadChats();
  }, [accountId]);

  useEffect(() => {
    if (selectedChat && accountId) loadMessages(selectedChat);
  }, [selectedChat]);

  /* Auto-refresh messages for selected chat */
  usePolling(
    () => { if (selectedChat && accountId) return loadMessages(selectedChat); },
    8000,
    !!selectedChat && !!accountId,
  );

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /* ─── Load orders for buyer when chat changes ────── */
  const selectedChatInfo = chats.find(c => c.chat_id === selectedChat);

  useEffect(() => {
    if (!accountId || !selectedChatInfo) {
      setBuyerOrders([]);
      return;
    }
    const buyerName = selectedChatInfo.name;
    setOrdersLoading(true);
    accountsApi.getOrders(accountId)
      .then(res => {
        const filtered = res.data.orders.filter(
          o => o.buyer.toLowerCase() === buyerName.toLowerCase()
        );
        setBuyerOrders(filtered);
      })
      .catch(() => setBuyerOrders([]))
      .finally(() => setOrdersLoading(false));
  }, [accountId, selectedChat]);

  const loadChats = async () => {
    if (!accountId) return;
    try {
      const res = await accountsApi.getChats(accountId);
      setChats(res.data.chats);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  usePolling(loadChats, 10000, !!accountId);

  const loadMessages = async (chatId: number) => {
    if (!accountId) return;
    try {
      const res = await accountsApi.getChatHistory(accountId, chatId);
      setMessages(res.data.messages);
    } catch { notify('failed to load messages', 'error'); }
  };

  const handleSend = async () => {
    if (!input.trim() || !selectedChat || !accountId) return;
    setSending(true);
    try {
      await accountsApi.sendMessage(accountId, selectedChat, input.trim());
      setInput('');
      setTimeout(() => loadMessages(selectedChat), 500);
    } catch { notify('failed to send message', 'error'); }
    finally { setSending(false); }
  };

  /* ─── is_my: by_bot OR author matches account username ── */
  const isMine = useCallback((msg: Message) => {
    if (msg.is_my) return true;
    if (accountUsername && msg.author === accountUsername) return true;
    return false;
  }, [accountUsername]);

  const filtered = chats.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>chats</Typography>

      <Box sx={{ display: 'flex', gap: 2, height: 'calc(100vh - 150px)' }}>
        {/* Chat List */}
        <Paper sx={{
          width: 320, flexShrink: 0, bgcolor: '#141414',
          border: '1px solid rgba(255,255,255,0.06)', borderRadius: 2,
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <Box sx={{ p: 1.5 }}>
            <TextField
              fullWidth placeholder="search chats..."
              value={search} onChange={e => setSearch(e.target.value)}
              slotProps={{
                input: {
                  startAdornment: <InputAdornment position="start"><SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} /></InputAdornment>,
                },
              }}
              sx={{ '& .MuiOutlinedInput-root': { bgcolor: 'rgba(255,255,255,0.03)' } }}
            />
          </Box>
          <Divider />
          <List sx={{ flex: 1, overflow: 'auto', py: 0 }}>
            {loading ? (
              [...Array(8)].map((_, i) => (
                <Box key={i} sx={{ px: 2, py: 1.5 }}>
                  <Skeleton width="60%" height={20} sx={{ bgcolor: 'rgba(255,255,255,0.04)' }} />
                  <Skeleton width="80%" height={16} sx={{ mt: 0.5, bgcolor: 'rgba(255,255,255,0.04)' }} />
                </Box>
              ))
            ) : filtered.length === 0 ? (
              <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                {chats.length === 0 ? 'no chats' : 'no matches'}
              </Typography>
            ) : (
              filtered.map(chat => (
                <ListItemButton
                  key={chat.chat_id}
                  selected={selectedChat === chat.chat_id}
                  onClick={() => setSelectedChat(chat.chat_id)}
                  sx={{
                    py: 1.5, px: 2,
                    '&.Mui-selected': {
                      bgcolor: alpha('#8B5CF6', 0.1),
                      borderLeft: '3px solid #8B5CF6',
                    },
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="body2" sx={{ fontWeight: chat.unread ? 700 : 500, color: 'text.primary' }}>
                          {chat.name}
                        </Typography>
                        {chat.unread && (
                          <Badge color="primary" variant="dot" />
                        )}
                      </Box>
                    }
                    secondary={
                      <Typography variant="caption" sx={{
                        color: 'text.secondary',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        display: 'block', maxWidth: 240,
                      }}>
                        {chat.last_message}
                      </Typography>
                    }
                  />
                </ListItemButton>
              ))
            )}
          </List>
        </Paper>

        {/* Messages */}
        <Paper sx={{
          flex: 1, bgcolor: '#141414',
          border: '1px solid rgba(255,255,255,0.06)', borderRadius: 2,
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          {!selectedChat ? (
            <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body1" color="text.secondary">select a chat</Typography>
            </Box>
          ) : (
            <>
              {/* Chat header */}
              <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary' }}>
                  {selectedChatInfo?.name || `Chat #${selectedChat}`}
                </Typography>
              </Box>

              {/* Messages */}
              <Box sx={{ flex: 1, overflow: 'auto', px: 2.5, py: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
                {messages.map(msg => {
                  const mine = isMine(msg);
                  return (
                    <Box
                      key={msg.id}
                      sx={{
                        alignSelf: mine ? 'flex-end' : 'flex-start',
                        maxWidth: '70%',
                      }}
                    >
                      {!mine && (
                        <Typography variant="caption" sx={{ color: '#8B5CF6', fontWeight: 600, mb: 0.3, display: 'block' }}>
                          {msg.author}
                        </Typography>
                      )}
                      <Box sx={{
                        px: 2, py: 1, borderRadius: 3,
                        bgcolor: mine ? alpha('#8B5CF6', 0.2) : 'rgba(255,255,255,0.05)',
                        border: `1px solid ${mine ? alpha('#8B5CF6', 0.3) : 'rgba(255,255,255,0.06)'}`,
                      }}>
                        <Typography variant="body2" sx={{ color: 'text.primary', whiteSpace: 'pre-wrap' }}>
                          {msg.text}
                        </Typography>
                        {msg.image_url && (
                          <Box component="img" src={msg.image_url} sx={{ mt: 1, maxWidth: '100%', borderRadius: 2 }} />
                        )}
                      </Box>
                    </Box>
                  );
                })}
                <div ref={messagesEnd} />
              </Box>

              {/* Input */}
              <Box sx={{ px: 2, py: 1.5, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <TextField
                  fullWidth
                  placeholder="type a message..."
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  multiline
                  maxRows={4}
                  disabled={sending}
                  slotProps={{
                    input: {
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={handleSend} disabled={!input.trim() || sending} color="primary">
                            <SendIcon />
                          </IconButton>
                        </InputAdornment>
                      ),
                      sx: { bgcolor: 'rgba(255,255,255,0.03)' },
                    },
                  }}
                />
              </Box>
            </>
          )}
        </Paper>

        {/* Orders sidebar — shows when chat is selected */}
        {selectedChat && (
          <Paper sx={{
            width: 280, flexShrink: 0, bgcolor: '#141414',
            border: '1px solid rgba(255,255,255,0.06)', borderRadius: 2,
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 1 }}>
              <OrdersIcon sx={{ fontSize: 18, color: '#8B5CF6' }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                orders · {selectedChatInfo?.name}
              </Typography>
            </Box>
            <Box sx={{ flex: 1, overflow: 'auto', p: 1.5 }}>
              {ordersLoading ? (
                [...Array(3)].map((_, i) => (
                  <Skeleton key={i} height={60} sx={{ mb: 1, bgcolor: 'rgba(255,255,255,0.04)', borderRadius: 1 }} />
                ))
              ) : buyerOrders.length === 0 ? (
                <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', py: 3 }}>
                  no orders
                </Typography>
              ) : (
                buyerOrders.map(order => (
                  <Box
                    key={order.order_id}
                    sx={{
                      mb: 1, p: 1.5, borderRadius: 2,
                      bgcolor: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.06)',
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace' }}>
                        #{order.order_id}
                      </Typography>
                      <Chip
                        label={order.status}
                        size="small"
                        sx={{
                          height: 18, fontSize: 10, fontWeight: 600,
                          bgcolor: alpha(statusColor(order.status), 0.15),
                          color: statusColor(order.status),
                          border: `1px solid ${alpha(statusColor(order.status), 0.3)}`,
                        }}
                      />
                    </Box>
                    <Typography variant="body2" sx={{
                      color: 'text.primary', fontSize: 12,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {order.description}
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                      <Typography variant="caption" sx={{ color: '#8B5CF6', fontWeight: 600 }}>
                        {order.price}
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {order.date}
                      </Typography>
                    </Box>
                  </Box>
                ))
              )}
            </Box>
          </Paper>
        )}
      </Box>
    </Box>
  );
}
