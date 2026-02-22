import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import {
  authApi,
  getStoredToken,
  setStoredToken,
  clearStoredToken,
  type LoginRequest,
  type AuthMeResponse,
} from '../api/client';

// ─── Types ────────────────────────────────────────────

interface AuthState {
  /** null = loading, false = not authenticated, AuthMeResponse = authenticated */
  user: AuthMeResponse | null;
  /** true while initial auth check is in progress */
  loading: boolean;
  /** true when auth is disabled on backend (all requests pass through) */
  authDisabled: boolean;
}

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Token refresh scheduler ─────────────────────────

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleRefresh(expiresIn: number, refreshFn: () => Promise<boolean>) {
  if (refreshTimer) clearTimeout(refreshTimer);
  // Refresh 2 minutes before expiry, minimum 30s
  const refreshAfterMs = Math.max((expiresIn - 120) * 1000, 30_000);
  refreshTimer = setTimeout(async () => {
    const ok = await refreshFn();
    if (!ok) {
      // Token refresh failed; the 401 interceptor will handle it
    }
  }, refreshAfterMs);
}

function clearRefreshSchedule() {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

// ─── Provider ─────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    authDisabled: false,
  });

  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      const { data } = await authApi.refresh();
      setStoredToken(data.access_token);
      scheduleRefresh(data.expires_in, refreshToken);
      return true;
    } catch {
      clearStoredToken();
      clearRefreshSchedule();
      setState((s) => ({ ...s, user: null, loading: false }));
      return false;
    }
  }, []);

  const login = useCallback(
    async (body: LoginRequest) => {
      const { data } = await authApi.login(body);
      setStoredToken(data.access_token);

      // Fetch user profile
      const { data: user } = await authApi.me();
      setState({ user, loading: false, authDisabled: false });
      scheduleRefresh(data.expires_in, refreshToken);
    },
    [refreshToken],
  );

  const logout = useCallback(() => {
    clearStoredToken();
    clearRefreshSchedule();
    setState({ user: null, loading: false, authDisabled: false });
  }, []);

  // Initial auth check
  useEffect(() => {
    let cancelled = false;

    async function check() {
      // 1. Check if auth is enabled on the backend
      try {
        const { data: cfg } = await authApi.config();
        console.log('[Auth] /auth/config response:', { auth_enabled: cfg.auth_enabled });

        if (!cfg.auth_enabled) {
          // Auth disabled on backend - clear any stale token
          clearStoredToken();
          clearRefreshSchedule();
          if (!cancelled) {
            console.log('[Auth] Auth disabled, granting access without login');
            setState({ user: null, loading: false, authDisabled: true });
          }
          return;
        }
      } catch (err) {
        // If /auth/config returns 401 → auth IS enabled (need login).
        // If network error → assume auth enabled (safe fallback).
        console.warn('[Auth] /auth/config fetch failed, assuming auth enabled:', err);
      }

      // 2. If we have a token, validate it
      const token = getStoredToken();
      if (!token) {
        console.log('[Auth] No token found, redirecting to login');
        if (!cancelled) {
          setState({ user: null, loading: false, authDisabled: false });
        }
        return;
      }

      try {
        const { data: user } = await authApi.me();
        if (!cancelled) {
          setState({ user, loading: false, authDisabled: false });

          // Schedule refresh based on remaining TTL
          const remainingSec = user.expires_at - Date.now() / 1000;
          if (remainingSec > 0) {
            scheduleRefresh(remainingSec, refreshToken);
          }
        }
      } catch {
        // Token invalid or expired
        clearStoredToken();
        if (!cancelled) {
          setState({ user: null, loading: false, authDisabled: false });
        }
      }
    }

    check();
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  // Listen to 401 events from axios interceptor
  useEffect(() => {
    const handler = () => {
      clearRefreshSchedule();
      setState((s) => ({ ...s, user: null, loading: false }));
    };
    window.addEventListener('opium:auth:expired', handler);
    return () => window.removeEventListener('opium:auth:expired', handler);
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
