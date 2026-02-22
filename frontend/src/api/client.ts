import axios from 'axios';

const TOKEN_KEY = 'opium_token';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

// ─── Auth Interceptors ───────────────────────────────

// Request: attach Bearer token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response: handle 401 → fire event for AuthProvider
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const originalUrl: string = error.config?.url ?? '';
      // Don't redirect on login endpoint itself
      if (!originalUrl.includes('/auth/login')) {
        localStorage.removeItem(TOKEN_KEY);
        window.dispatchEvent(new CustomEvent('opium:auth:expired'));
      }
    }
    return Promise.reject(error);
  },
);

export default api;

// ─── Auth helpers ─────────────────────────────────────

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ─── Auth Types ───────────────────────────────────────

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
}

export interface TokenRefreshResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthMeResponse {
  username: string;
  issued_at: number;
  expires_at: number;
}

export interface AuthConfigResponse {
  auth_enabled: boolean;
}

// ─── Types ────────────────────────────────────────────

export interface AccountInfo {
  account_id: string;
  username: string | null;
  fp_id: number | null;
  state: string;
  is_running: boolean;
  enabled: boolean;
  last_error: string | null;
  modules: string[];
}

export interface AccountConfig {
  account_id: string;
  golden_key: string;
  user_agent: string;
  proxy?: string | null;
  anti_detect?: {
    startup_delay_min?: number;
    startup_delay_max?: number;
    shutdown_delay_min?: number;
    shutdown_delay_max?: number;
    runner_delay_min?: number;
    runner_delay_max?: number;
    session_refresh_interval?: number;
    session_refresh_jitter?: number;
  } | null;
  rate_limit?: Record<string, number> | null;
  reconnect?: Record<string, unknown> | null;
  disable_messages?: boolean;
  disable_orders?: boolean;
  enabled?: boolean;
}

export interface ChatShort {
  chat_id: number;
  name: string;
  last_message: string;
  unread: boolean;
  media_url: string | null;
}

export interface Message {
  id: number;
  author_id: number;
  author: string;
  text: string;
  html: string;
  image_url: string | null;
  is_my: boolean;
}

export interface OrderShort {
  order_id: string;
  description: string;
  price: string;
  buyer: string;
  status: string;
  date: string;
}

export interface OrderTagInfo {
  module: string;
  game_id?: string;
}

export interface OrderTagsResponse {
  tags: Record<string, OrderTagInfo>;
  modules: string[];
  games: Record<string, string[]>;
}

export interface Balance {
  total_rub: number;
  available_rub: number;
  total_usd: number;
  available_usd: number;
  total_eur: number;
  available_eur: number;
}

export interface SystemStatus {
  running: boolean;
  accounts_count: number;
  accounts: Record<string, { state: string; is_running: boolean }>;
}

// ─── System API ───────────────────────────────────────

export const systemApi = {
  status: () => api.get<SystemStatus>('/status'),
  availableModules: () => api.get<{ modules: string[] }>('/modules/available'),
};

// ─── Auth API ─────────────────────────────────────────

export const authApi = {
  login: (data: LoginRequest) =>
    api.post<LoginResponse>('/auth/login', data),
  me: () =>
    api.get<AuthMeResponse>('/auth/me'),
  refresh: () =>
    api.post<TokenRefreshResponse>('/auth/refresh'),
  config: () =>
    api.get<AuthConfigResponse>('/auth/config'),
  health: () =>
    api.get<{ status: string; timestamp: number }>('/health'),
};

// ─── Accounts API ─────────────────────────────────────

export const accountsApi = {
  list: () => api.get<AccountInfo[]>('/accounts'),
  get: (id: string) => api.get<AccountInfo>(`/accounts/${id}`),
  create: (data: AccountConfig) => api.post<AccountInfo>('/accounts', data),
  delete: (id: string) => api.delete(`/accounts/${id}`),
  start: (id: string) => api.post(`/accounts/${id}/start`),
  stop: (id: string) => api.post(`/accounts/${id}/stop`),
  getConfig: (id: string) => api.get<AccountConfig>(`/accounts/${id}/config`),
  updateConfig: (id: string, config: Record<string, unknown>) =>
    api.patch(`/accounts/${id}/config`, config),

  // Module management
  listModules: (id: string) => api.get<{ modules: string[] }>(`/accounts/${id}/modules`),
  addModule: (id: string, moduleName: string) =>
    api.post(`/accounts/${id}/modules`, { module_name: moduleName }),
  getModuleConfig: (id: string, moduleName: string) =>
    api.get<Record<string, unknown>>(`/accounts/${id}/modules/${moduleName}`),
  updateModuleConfig: (id: string, moduleName: string, config: Record<string, unknown>) =>
    api.put(`/accounts/${id}/modules/${moduleName}`, config),

  // Data
  getBalance: (id: string) => api.get<Balance>(`/accounts/${id}/balance`),
  getChats: (id: string) => api.get<{ chats: ChatShort[]; total: number }>(`/accounts/${id}/chats`),
  getChatHistory: (id: string, chatId: number) =>
    api.get<{ messages: Message[]; chat_id: number; count: number }>(`/accounts/${id}/chats/${chatId}/history`),
  sendMessage: (id: string, chatId: number, text: string) =>
    api.post(`/accounts/${id}/chats/${chatId}/send`, { text }),
  getOrders: (id: string) => api.get<{ orders: OrderShort[]; total: number }>(`/accounts/${id}/orders`),
  getOrderTags: (id: string) => api.get<OrderTagsResponse>(`/accounts/${id}/order-tags`),
  getOrderDetail: (id: string, orderId: string) =>
    api.get(`/accounts/${id}/orders/${orderId}`),
  refundOrder: (id: string, orderId: string) =>
    api.post(`/accounts/${id}/orders/${orderId}/refund`),
};
