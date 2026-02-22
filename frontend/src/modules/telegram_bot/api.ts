import api from '../../api/client';

const base = (accountId: string) =>
  `/accounts/${accountId}/modules/telegram_bot`;

// ─── Types ───────────────────────────────────────────

export interface TelegramBotConfig {
  bot_token: string;
  has_token: boolean;
  notify_events: string[];
  available_events: { key: string; label: string }[];
}

export interface WhitelistEntry {
  telegram_id: number;
  label: string;
}

export interface BotInfo {
  online: boolean;
  username: string | null;
  first_name: string | null;
  bot_id: number | null;
}

export interface EventLogEntry {
  event_type: string;
  text_preview: string;
  sent_to: number;
  total: number;
  timestamp: string;
}

export interface LogWatcher {
  id: string;
  pattern: string;
  custom_message: string;
  enabled: boolean;
}

export interface BotButton {
  id: string;
  label: string;
  api_endpoint: string;
  api_method: string;
  api_body: Record<string, unknown> | null;
  description: string;
  confirm: boolean;
  enabled: boolean;
}

// ─── API ─────────────────────────────────────────────

export const telegramBotApi = {
  // Config
  getConfig: (accountId: string) =>
    api.get<TelegramBotConfig>(`${base(accountId)}/config`).then(r => r.data),

  updateConfig: (accountId: string, data: { bot_token?: string; notify_events?: string[] }) =>
    api.patch<{ ok: boolean; restarted: boolean }>(`${base(accountId)}/config`, data).then(r => r.data),

  // Whitelist
  getWhitelist: (accountId: string) =>
    api.get<WhitelistEntry[]>(`${base(accountId)}/whitelist`).then(r => r.data),

  addToWhitelist: (accountId: string, telegramId: number, label: string = '') =>
    api.post(`${base(accountId)}/whitelist`, { telegram_id: telegramId, label }).then(r => r.data),

  updateWhitelistEntry: (accountId: string, telegramId: number, label: string) =>
    api.patch(`${base(accountId)}/whitelist/${telegramId}`, { label }).then(r => r.data),

  removeFromWhitelist: (accountId: string, telegramId: number) =>
    api.delete(`${base(accountId)}/whitelist/${telegramId}`).then(r => r.data),

  // Events
  getEvents: (accountId: string, limit = 50) =>
    api.get<EventLogEntry[]>(`${base(accountId)}/events`, { params: { limit } }).then(r => r.data),

  clearEvents: (accountId: string) =>
    api.delete(`${base(accountId)}/events`).then(r => r.data),

  // Bot
  getBotInfo: (accountId: string) =>
    api.get<BotInfo>(`${base(accountId)}/bot-info`).then(r => r.data),

  restartBot: (accountId: string) =>
    api.post(`${base(accountId)}/restart`).then(r => r.data),

  sendTest: (accountId: string) =>
    api.post<{ ok: boolean; sent: number; total: number }>(`${base(accountId)}/test`).then(r => r.data),

  // Log Watchers
  getLogWatchers: (accountId: string) =>
    api.get<LogWatcher[]>(`${base(accountId)}/log-watchers`).then(r => r.data),

  addLogWatcher: (accountId: string, data: { pattern: string; custom_message?: string; enabled?: boolean }) =>
    api.post<LogWatcher>(`${base(accountId)}/log-watchers`, data).then(r => r.data),

  updateLogWatcher: (accountId: string, watcherId: string, data: { pattern?: string; custom_message?: string; enabled?: boolean }) =>
    api.patch(`${base(accountId)}/log-watchers/${watcherId}`, data).then(r => r.data),

  deleteLogWatcher: (accountId: string, watcherId: string) =>
    api.delete(`${base(accountId)}/log-watchers/${watcherId}`).then(r => r.data),

  // Bot Buttons
  getBotButtons: (accountId: string) =>
    api.get<BotButton[]>(`${base(accountId)}/bot-buttons`).then(r => r.data),

  addBotButton: (accountId: string, data: {
    label: string; api_endpoint: string; api_method?: string;
    api_body?: Record<string, unknown> | null; description?: string;
    confirm?: boolean; enabled?: boolean;
  }) =>
    api.post<BotButton>(`${base(accountId)}/bot-buttons`, data).then(r => r.data),

  updateBotButton: (accountId: string, buttonId: string, data: {
    label?: string; api_endpoint?: string; api_method?: string;
    api_body?: Record<string, unknown> | null; description?: string;
    confirm?: boolean; enabled?: boolean;
  }) =>
    api.patch(`${base(accountId)}/bot-buttons/${buttonId}`, data).then(r => r.data),

  deleteBotButton: (accountId: string, buttonId: string) =>
    api.delete(`${base(accountId)}/bot-buttons/${buttonId}`).then(r => r.data),
};
