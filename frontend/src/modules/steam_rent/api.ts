import api from '../../api/client';

const base = (accountId: string) =>
  `/accounts/${accountId}/modules/steam_rent`;

// ─── Types ───────────────────────────────────────────

export interface SteamGame {
  game_id: string;
  aliases: string[];
  proxy_settings?: Record<string, unknown> | null;
  frozen?: boolean;
}

export interface LotMapping {
  lot_pattern: string;
  game_id: string;
  rent_minutes: number;
  bonus_minutes: number;
  min_rating_for_bonus: number;
}

export interface SteamAccount {
  id: string;
  login: string;
  password: string;        // masked as '***' in API response
  game_ids: string[];
  status: 'free' | 'rented';
  shared_secret: string | null;   // masked as '***' in API response
  identity_secret: string | null; // masked as '***' in API response
  has_mafile: boolean;     // replaces mafile object (never returned)
  change_password_on_rent: boolean;
  kick_devices_on_rent: boolean;
  password_history: string[];
  proxy_settings: Record<string, unknown> | null;
  frozen?: boolean;
}

export interface Rental {
  rental_id: string;
  order_id: string;
  buyer_id: number;
  buyer_username: string;
  game_id: string;
  steam_account_id: string;
  start_time: string;
  end_time: string;
  entitled_bonus_minutes: number;
  min_rating_for_bonus: number;
  bonus_minutes: number;
  status: 'active' | 'expired' | 'revoked';
  delivered_login: string;
  delivered_password: string;
}

export interface SteamRentConfig {
  change_password_on_rent: boolean;
  kick_devices_on_rent: boolean;
  scheduler_check_interval_sec: number;
  expiry_warning_minutes: number;
  [key: string]: unknown;
}

export interface SteamRentOverview {
  active_rentals: number;
  total_rentals: number;
  free_accounts: number;
  total_accounts: number;
  total_games: number;
  lot_mappings: number;
  pending_orders: number;
}

// ─── Proxy Types ─────────────────────────────────────

export interface Proxy {
  proxy_id: string;
  host: string;
  port: number;
  proxy_type: 'http' | 'https' | 'socks5';
  username: string;
  password: string;  // masked as '***' in API response
  name: string;
  enabled: boolean;
}

export interface ProxyList {
  list_id: string;
  name: string;
  proxy_ids: string[];
}

export interface ProxySettings {
  mode: 'direct' | 'fixed' | 'mix' | 'mix-list';
  fixed_proxy_id?: string | null;
  proxy_list_id?: string | null;
  fallback: 'try-all' | 'direct';
}

// ─── API Functions ───────────────────────────────────

export const steamRentApi = {
  // Overview / stats
  getOverview: (accountId: string) =>
    api.get<SteamRentOverview>(`${base(accountId)}/overview`),

  // Config
  getConfig: (accountId: string) =>
    api.get<SteamRentConfig>(`${base(accountId)}/config`),
  updateConfig: (accountId: string, config: Partial<SteamRentConfig>) =>
    api.put(`${base(accountId)}/config`, config),

  // Games
  getGames: (accountId: string) =>
    api.get<SteamGame[]>(`${base(accountId)}/games`),
  createGame: (accountId: string, game: SteamGame) =>
    api.post(`${base(accountId)}/games`, game),
  updateGame: (accountId: string, gameId: string, game: Partial<SteamGame>) =>
    api.put(`${base(accountId)}/games/${gameId}`, game),
  deleteGame: (accountId: string, gameId: string) =>
    api.delete(`${base(accountId)}/games/${gameId}`),
  freezeGame: (accountId: string, gameId: string) =>
    api.post<{ ok: boolean; frozen: boolean }>(`${base(accountId)}/games/${gameId}/freeze`),

  // Lot Mappings
  getLotMappings: (accountId: string) =>
    api.get<LotMapping[]>(`${base(accountId)}/lot-mappings`),
  createLotMapping: (accountId: string, mapping: LotMapping) =>
    api.post(`${base(accountId)}/lot-mappings`, mapping),
  updateLotMapping: (accountId: string, index: number, mapping: Partial<LotMapping>) =>
    api.put(`${base(accountId)}/lot-mappings/${index}`, mapping),
  deleteLotMapping: (accountId: string, index: number) =>
    api.delete(`${base(accountId)}/lot-mappings/${index}`),

  // Steam Accounts
  getSteamAccounts: (accountId: string) =>
    api.get<SteamAccount[]>(`${base(accountId)}/steam-accounts`),
  createSteamAccount: (accountId: string, acc: Partial<SteamAccount>) =>
    api.post(`${base(accountId)}/steam-accounts`, acc),
  updateSteamAccount: (accountId: string, steamId: string, acc: Partial<SteamAccount>) =>
    api.put(`${base(accountId)}/steam-accounts/${steamId}`, acc),
  deleteSteamAccount: (accountId: string, steamId: string) =>
    api.delete(`${base(accountId)}/steam-accounts/${steamId}`),
  freezeSteamAccount: (accountId: string, steamId: string) =>
    api.post<{ ok: boolean; frozen: boolean }>(`${base(accountId)}/steam-accounts/${steamId}/freeze`),

  // Steam Account actions
  getPassword: (accountId: string, steamId: string) =>
    api.get<{ password: string }>(`${base(accountId)}/steam-accounts/${steamId}/password`),
  getGuardCode: (accountId: string, steamId: string) =>
    api.post<{ code: string }>(`${base(accountId)}/steam-accounts/${steamId}/guard-code`),
  changePassword: (accountId: string, steamId: string, newPassword?: string) =>
    api.post(`${base(accountId)}/steam-accounts/${steamId}/change-password`,
      newPassword ? { new_password: newPassword } : {}, { timeout: 120000 }),
  kickSessions: (accountId: string, steamId: string) =>
    api.post(`${base(accountId)}/steam-accounts/${steamId}/kick-sessions`, {}, { timeout: 120000 }),
  importMafile: (accountId: string, steamId: string, mafileJson: string) =>
    api.post(`${base(accountId)}/steam-accounts/${steamId}/import-mafile`, mafileJson, {
      headers: { 'Content-Type': 'text/plain' },
    }),

  // Rentals
  getRentals: (accountId: string) =>
    api.get<Rental[]>(`${base(accountId)}/rentals`),
  getActiveRentals: (accountId: string) =>
    api.get<Rental[]>(`${base(accountId)}/rentals/active`),
  modifyRentalTime: (accountId: string, rentalId: string, minutes: number) =>
    api.patch<Rental>(`${base(accountId)}/rentals/${rentalId}/time`, { minutes }),
  terminateRental: (accountId: string, rentalId: string) =>
    api.post<Rental>(`${base(accountId)}/rentals/${rentalId}/terminate`),

  // Proxies
  getProxies: (accountId: string) =>
    api.get<Proxy[]>(`${base(accountId)}/proxies`),
  createProxy: (accountId: string, data: Partial<Proxy> & { url?: string }) =>
    api.post<Proxy>(`${base(accountId)}/proxies`, data),
  updateProxy: (accountId: string, proxyId: string, data: Partial<Proxy>) =>
    api.put<Proxy>(`${base(accountId)}/proxies/${proxyId}`, data),
  deleteProxy: (accountId: string, proxyId: string) =>
    api.delete(`${base(accountId)}/proxies/${proxyId}`),
  checkProxyHealth: (accountId: string, proxyId: string) =>
    api.post<{ healthy: boolean; proxy_id: string }>(`${base(accountId)}/proxies/${proxyId}/check`, {}, { timeout: 30000 }),

  // Proxy Lists
  getProxyLists: (accountId: string) =>
    api.get<ProxyList[]>(`${base(accountId)}/proxy-lists`),
  createProxyList: (accountId: string, data: { name: string; proxy_ids?: string[] }) =>
    api.post<ProxyList>(`${base(accountId)}/proxy-lists`, data),
  deleteProxyList: (accountId: string, listId: string) =>
    api.delete(`${base(accountId)}/proxy-lists/${listId}`),
  addProxyToList: (accountId: string, listId: string, proxyId: string) =>
    api.post(`${base(accountId)}/proxy-lists/${listId}/proxies/${proxyId}`),
  removeProxyFromList: (accountId: string, listId: string, proxyId: string) =>
    api.delete(`${base(accountId)}/proxy-lists/${listId}/proxies/${proxyId}`),

  // Messages
  getMessages: (accountId: string) =>
    api.get<MessagesResponse>(`${base(accountId)}/messages`),
  updateMessages: (accountId: string, messages: Record<string, string | null>) =>
    api.put<{ ok: boolean; messages: Record<string, string> }>(`${base(accountId)}/messages`, messages),
};

// ─── Messages Types ──────────────────────────────────

export interface MessagesResponse {
  messages: Record<string, string>;
  defaults: Record<string, string>;
  groups: Array<{ id: string; label: string; description: string; keys: string[] }>;
  meta: Record<string, { label: string; placeholders: string[]; examples: Record<string, string>; stale?: boolean; unknown_placeholders?: string[] }>;
  placeholder_docs: Record<string, string>;
}
