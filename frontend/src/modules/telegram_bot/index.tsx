import {
  Dashboard as DashboardIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import type { ModuleManifest } from '../index';
import TelegramBotDashboard from './Dashboard';
import TelegramBotSettings from './Settings';

export const telegramBotManifest: ModuleManifest = {
  name: 'telegram_bot',
  displayName: 'telegram bot',
  description: 'telegram notifications and monitoring',
  navigation: [
    { label: 'dashboard', path: 'dashboard', icon: <DashboardIcon fontSize="small" /> },
    { label: 'settings', path: 'settings', icon: <SettingsIcon fontSize="small" /> },
  ],
  routes: [
    { path: 'dashboard', component: TelegramBotDashboard },
    { path: 'settings', component: TelegramBotSettings },
  ],
};
