# Opium — Frontend Guide

> **Версия**: 2.0 — 2026-02-15
> **Стек**: React 19, TypeScript strict, MUI v6, Vite, react-router-dom
> **Аудитория**: Разработчик модулей, AI-ассистент

---

## 1. Структура

```
frontend/
├── index.html                 # SPA entry point
├── package.json               # Dependencies
├── vite.config.ts             # Dev server (:3000 → proxy :8000)
├── tsconfig.json              # TS config
└── src/
    ├── main.tsx               # React root (AuthProvider → App)
    ├── App.tsx                # Routing + auth guard
    ├── theme.ts               # MUI dark theme
    ├── vite-env.d.ts          # Vite type refs
    │
    ├── api/
    │   └── client.ts          # Axios instance + types + API methods
    │
    ├── auth/
    │   └── AuthContext.tsx     # JWT auth state management
    │
    ├── components/           # Shared UI components
    │   ├── Layout.tsx         # Sidebar + routing outlet
    │   ├── PageHeader.tsx     # Заголовок + refresh + actions
    │   ├── GlowCard.tsx       # Card + StatCard + StatusDot
    │   └── TablePaper.tsx     # Dark table wrapper
    │
    ├── hooks/                # Shared hooks
    │   ├── useAccountActions.ts
│   │   ├── useCountdown.ts
│   │   └── usePolling.ts
    │
    ├── pages/                # Core pages (не модульные)
    │   ├── Dashboard.tsx      # Главная
    │   ├── Accounts.tsx       # Управление аккаунтами
    │   ├── Chats.tsx          # Чаты аккаунта
    │   ├── Orders.tsx         # Заказы аккаунта
    │   └── Login.tsx          # Страница логина
    │
    └── modules/             # Модули (auto-discovery)
        ├── index.ts           # ModuleManifest + glob import
        ├── steam_rent/        # Модуль аренды Steam
        │   ├── index.tsx      # Manifest export
        │   ├── api.ts         # API types + calls
        │   ├── Dashboard.tsx
        │   ├── SteamAccounts.tsx
        │   ├── Games.tsx
        │   ├── LotMappings.tsx
        │   ├── Rentals.tsx
        │   ├── Proxies.tsx
        │   └── Messages.tsx
        ├── telegram_bot/      # Telegram-бот: настройки + дашборд
        │   ├── index.tsx      # Manifest export
        │   ├── api.ts         # API types + calls
        │   ├── Dashboard.tsx  # Статус, события, вайтлист
        │   └── Settings.tsx   # Токен, log watchers, кнопки
        └── auto_raise/        # Автоподнятие лотов
            └── index.tsx      # Manifest export (встроенный дашборд)
```

---

## 2. Тема (Design System)

Тёмная тема, accent: `#8B5CF6` (фиолетовый).

### Палитра

| Token | Цвет | Использование |
|-------|------|--------------|
| `primary.main` | `#8B5CF6` | Акцентный, selected state |
| `secondary.main` | `#06B6D4` | Вторичный акцент |
| `background.default` | `#0a0a0a` | Фон страницы |
| `background.paper` | `#141414` | Фон карточек, таблиц |
| `text.primary` | `#FAFAFA` | Основной текст |
| `text.secondary` | `#a0a0a0` | Вторичный текст |
| `success.main` | `#22C55E` | Активные статусы |
| `error.main` | `#EF4444` | Ошибки, удаление |
| `warning.main` | `#F59E0B` | Предупреждения |
| `divider` | `rgba(255,255,255,0.07)` | Разделители |

### Типографика

- Шрифт: `Inter`
- h3-h4: bold 700-800
- body: 0.9rem
- button: `textTransform: 'none'`, fontWeight 600
- caption: uppercase, 0.72rem, letter-spacing 0.04em

### Компоненты (кастомизация)

| Компонент | borderRadius | Особенности |
|-----------|-------------|-------------|
| Card | 16px | `no backgroundImage`, border 0.06 |
| Button | 10px | No box-shadow, outlined: 0.12 border |
| TextField | 10px | size="small" default |
| Chip | 8px | 0.75rem, fontWeight 500 |
| Dialog | 16px | #141414, no backgroundImage |
| Tooltip | 8px | #262626, 0.75rem |
| IconButton | 10px | hover: 0.06 opacity |

### Стилевые соглашения

```tsx
// Lowercase для всех label'ов и заголовков
<PageHeader title="steam rent" />
<Chip label="active" />
<Button>add product</Button>

// Glow effects для интерактивных карточек
import { glowShadow, cardHoverSx } from '../../theme';
<Card sx={cardHoverSx}>...</Card>
```

---

## 3. Routing

`App.tsx` организует маршруты:

```
/                                    → Dashboard
/login                               → Login (если auth enabled)
/accounts                            → Accounts
/accounts/:accountId/chats           → Chats
/accounts/:accountId/orders          → Orders
/accounts/:accountId/modules/{name}/{path} → Module pages (auto)
```

### Auto-registration модулей

```tsx
// App.tsx (ключевая часть)
const manifests = getModuleManifests();

{manifests.flatMap(m =>
  m.routes.map(r => (
    <Route
      key={`${m.name}-${r.path}`}
      path={`/accounts/:accountId/modules/${m.name}/${r.path}`}
      element={<r.component />}
    />
  ))
)}
```

---

## 4. Layout и Navigation

`Layout.tsx` — основной layout с sidebar.

### Sidebar структура

```
┌─────────────────────────┐
│ opium           [</>]   │ ← Logo + collapse toggle
├─────────────────────────┤
│ [account selector ▼]    │ ← Выбор аккаунта
├─────────────────────────┤
│ 📊 dashboard            │ ← Global nav
├──── {account_id} ──────────┤
│ 💬 chats                │ ← Per-account nav
│ 🛒 orders               │
├──── steam rent ─────────┤
│ 📊 dashboard            │ ← Module nav (auto from manifest)
│ 🎮 steam accounts       │
│ 🕹️ games                │
│ 🔗 lot mappings         │
│ 📋 rentals              │
│ 🔒 proxies              │
│ 💬 messages             │
├─────────────────────────┤
│ admin              [🚪] │ ← Logout (only when auth enabled)
│ opium v2.0              │
└─────────────────────────┘
```

### Sidebar показывает только активные модули

```tsx
const enabledModules = selectedAccount?.modules ?? [];
moduleManifests.filter(m => enabledModules.includes(m.name))
```

### LayoutContext

```tsx
import { useLayout } from '../../components/Layout';

const { accounts, selectedAccount, accountId, refetch, notify } = useLayout();

// accounts: AccountInfo[] — все аккаунты
// selectedAccount: AccountInfo | null — текущий из URL
// accountId: string | null — из URL params
// refetch: () => void — перезагрузить список аккаунтов
// notify: (msg, severity) => void — показать snackbar
```

---

## 5. Shared Components

### PageHeader

```tsx
import { PageHeader } from '../../components/PageHeader';

<PageHeader
  title="my page"                    // h4, fontWeight 700
  subtitle="additional information"  // body2, text.secondary
  onRefresh={loadData}               // Кнопка refresh (опционально)
  actions={                          // Дополнительные actions (опционально)
    <Button variant="outlined" size="small" startIcon={<AddIcon />}>
      add item
    </Button>
  }
/>
```

### StatCard

```tsx
import { StatCard } from '../../components/GlowCard';

<StatCard
  label="active rentals"     // caption, uppercase
  value={42}                 // h4, bold
  icon={<PeopleIcon />}      // В цветном квадрате
  color="#22C55E"            // Цвет glow + icon bg (default: #8B5CF6)
  subtitle="2 expiring soon" // Под value (опционально)
/>
```

### StatusDot

```tsx
import { StatusDot, stateToStatus } from '../../components/GlowCard';

<StatusDot status="running" size={8} />
// status: 'running' | 'stopped' | 'error' | 'reconnecting' | 'initializing'
// running/error/reconnecting имеют glow, initializing пульсирует

// Конвертация из runtime state:
<StatusDot status={stateToStatus(account.state)} />
```

### GlowCard

```tsx
import GlowCard from '../../components/GlowCard';

<GlowCard glow="#22C55E" onClick={() => navigate('/...')}>
  <CardContent>...</CardContent>
</GlowCard>
// При hover: borderColor = glow * 0.3, boxShadow = glow blur
```

### TablePaper

```tsx
import { TablePaper } from '../../components/TablePaper';

<TablePaper>
  <Table size="small">
    <TableHead>
      <TableRow>
        <TableCell>Name</TableCell>
        <TableCell>Status</TableCell>
      </TableRow>
    </TableHead>
    <TableBody>
      {items.map(item => (
        <TableRow key={item.id}>
          <TableCell>{item.name}</TableCell>
          <TableCell>
            <Chip label={item.status} size="small" color="success" />
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
</TablePaper>
```

---

## 6. Hooks

### useCountdown

```tsx
import { useCountdown } from '../../hooks/useCountdown';

const { formatRemaining, isExpiringSoon } = useCountdown();

// formatRemaining("2024-01-15T12:00:00") → "2h 15m"
// isExpiringSoon("2024-01-15T12:00:00") → true (< 1 hour)
```

### useLayout

Описан в разделе 4 выше.

---

## 7. API Client

`api/client.ts` — единый axios инстанс для всего приложения.

### Настройка

```typescript
import api from '../../api/client';

// Уже настроено:
// - baseURL: '/api'
// - JWT Bearer token (auto из localStorage)
// - 401 → fire 'opium:auth:expired' event
// - timeout: 30s
```

### Core API helpers

```typescript
import { accountsApi, systemApi, authApi } from '../../api/client';

// Accounts
const accounts = await accountsApi.list();       // GET /api/accounts
const info = await accountsApi.get('{account_id}'); // GET /api/accounts/{account_id}
await accountsApi.start('{account_id}');             // POST .../start
await accountsApi.stop('{account_id}');              // POST .../stop

// Chats
const chats = await accountsApi.getChats('{account_id}');
const history = await accountsApi.getChatHistory('{account_id}', 12345);
await accountsApi.sendMessage('{account_id}', 12345, 'Hello!');

// Orders  
const orders = await accountsApi.getOrders('{account_id}');
const tags = await accountsApi.getOrderTags('{account_id}');

// System
const status = await systemApi.status();
const modules = await systemApi.availableModules();
```

### Типы (TypeScript)

Все типы определены в `client.ts`:

```typescript
AccountInfo, AccountConfig, ChatShort, Message, OrderShort,
OrderTagInfo, OrderTagsResponse, Balance, SystemStatus,
LoginRequest, LoginResponse, AuthMeResponse
```

---

## 8. Модульная система фронтенда

### Auto-discovery

`frontend/src/modules/index.ts`:
```typescript
import.meta.glob('./*/index.tsx', { eager: true })
```

При сборке Vite находит все `modules/*/index.tsx` и импортирует их. Каждый экспортированный объект, соответствующий `ModuleManifest`, автоматически регистрируется.

### ModuleManifest

```typescript
interface ModuleManifest {
  name: string;          // === module_name в Python (critical!)
  displayName: string;   // Для sidebar (lowercase)
  description: string;
  navigation: ModuleNavItem[];
  routes: ModuleRoute[];
}

interface ModuleNavItem {
  label: string;     // Текст в sidebar
  path: string;      // Относительный путь (без /)
  icon: ReactElement; // MUI Icon component
}

interface ModuleRoute {
  path: string;              // === ModuleNavItem.path
  component: React.ComponentType;
}
```

### Как добавить фронтенд модуля

```
frontend/src/modules/my_module/
├── index.tsx   ← ОБЯЗАТЕЛЬНО: export ModuleManifest
├── api.ts      ← Типы + API вызовы
└── *.tsx       ← Страницы
```

### Пример минимального модуля

**index.tsx:**
```tsx
import { Dashboard as DashboardIcon } from '@mui/icons-material';
import type { ModuleManifest } from '../index';
import DashboardPage from './Dashboard';

export const myModuleManifest: ModuleManifest = {
  name: 'my_module',
  displayName: 'my module',
  description: 'does something cool',
  navigation: [
    { label: 'dashboard', path: 'dashboard', icon: <DashboardIcon fontSize="small" /> },
  ],
  routes: [
    { path: 'dashboard', component: DashboardPage },
  ],
};
```

**Dashboard.tsx:**
```tsx
import { useParams } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import { PageHeader } from '../../components/PageHeader';

export default function DashboardPage() {
  const { accountId } = useParams<{ accountId: string }>();
  return (
    <Box>
      <PageHeader title="my module" />
      <Typography>Hello from my_module for {accountId}!</Typography>
    </Box>
  );
}
```

---

## 9. Grid System

MUI v6 использует `Grid2`:

```tsx
import Grid from '@mui/material/Grid2';

<Grid container spacing={2}>
  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
    <StatCard ... />
  </Grid>
  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
    <StatCard ... />
  </Grid>
</Grid>
```

---

## 10. Паттерны

### Loading state

```tsx
const [loading, setLoading] = useState(true);

if (loading) {
  return (
    <Box>
      <PageHeader title="my page" />
      <Grid container spacing={2}>
        {[...Array(4)].map((_, i) => (
          <Grid key={i} size={{ xs: 6, md: 3 }}>
            <Skeleton variant="rounded" height={100}
              sx={{ borderRadius: 4, bgcolor: 'rgba(255,255,255,0.04)' }} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
```

### Error notifications

```tsx
const { notify } = useLayout();

try {
  await api.deleteItem(accountId, itemId);
  notify('item deleted', 'success');
  load();  // перезагрузка данных
} catch {
  notify('failed to delete item', 'error');
}
```

### CRUD Dialog

```tsx
const [dialogOpen, setDialogOpen] = useState(false);
const [form, setForm] = useState({ name: '', value: '' });

<Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
  <DialogTitle>add item</DialogTitle>
  <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1, minWidth: 400 }}>
    <TextField label="Name" size="small" value={form.name}
      onChange={e => setForm({ ...form, name: e.target.value })} />
  </DialogContent>
  <DialogActions>
    <Button onClick={() => setDialogOpen(false)}>cancel</Button>
    <Button variant="contained" onClick={handleCreate}>create</Button>
  </DialogActions>
</Dialog>
```

### Status Chips

```tsx
<Chip
  label={status}
  size="small"
  color={
    status === 'active' ? 'success' :
    status === 'error' ? 'error' :
    status === 'pending' ? 'warning' : 'default'
  }
/>
```

---

## 11. Сборка и деплой

### Development

```bash
cd frontend
npm install
npm run dev        # Vite dev server :3000 → proxy :8000
```

### Production build

```bash
cd frontend
npm run build      # → frontend/dist/
# Скопировать в api/static/:
cp -r dist/* ../api/static/
```

### Vite config

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```

---

## 12. Чеклист для модуля

- [ ] `frontend/src/modules/{name}/index.tsx` — export `ModuleManifest`
- [ ] `manifest.name` === `module_name` в Python
- [ ] Labels в lowercase
- [ ] Icons с `fontSize="small"`
- [ ] Pages используют `useParams<{ accountId: string }>()`
- [ ] API client: `import api from '../../api/client'`
- [ ] Используют `PageHeader`, `TablePaper`, `StatCard` (не изобретать заново)
- [ ] `useLayout().notify()` для feedback
- [ ] Loading state с `Skeleton`
- [ ] Тёмная тема (не хардкодить белые фоны)
