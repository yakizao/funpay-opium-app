import {
  Dashboard as DashboardIcon,
  SportsEsports as SportsEsportsIcon,
  Gamepad as GamepadIcon,
  Link as LinkIcon,
  Receipt as ReceiptIcon,
  VpnLock as VpnLockIcon,
  Chat as ChatIcon,
} from '@mui/icons-material';
import type { ModuleManifest } from '../index';
import SteamRentDashboard from './Dashboard';
import SteamAccountsPage from './SteamAccounts';
import GamesPage from './Games';
import LotMappingsPage from './LotMappings';
import RentalsPage from './Rentals';
import ProxiesPage from './Proxies';
import MessagesPage from './Messages';

export const steamRentManifest: ModuleManifest = {
  name: 'steam_rent',
  displayName: 'steam rent',
  description: 'automated steam game account rental system',
  navigation: [
    { label: 'dashboard', path: 'dashboard', icon: <DashboardIcon fontSize="small" /> },
    { label: 'steam accounts', path: 'steam-accounts', icon: <SportsEsportsIcon fontSize="small" /> },
    { label: 'games', path: 'games', icon: <GamepadIcon fontSize="small" /> },
    { label: 'lot mappings', path: 'lot-mappings', icon: <LinkIcon fontSize="small" /> },
    { label: 'rentals', path: 'rentals', icon: <ReceiptIcon fontSize="small" /> },
    { label: 'proxies', path: 'proxies', icon: <VpnLockIcon fontSize="small" /> },
    { label: 'messages', path: 'messages', icon: <ChatIcon fontSize="small" /> },
  ],
  routes: [
    { path: 'dashboard', component: SteamRentDashboard },
    { path: 'steam-accounts', component: SteamAccountsPage },
    { path: 'games', component: GamesPage },
    { path: 'lot-mappings', component: LotMappingsPage },
    { path: 'rentals', component: RentalsPage },
    { path: 'proxies', component: ProxiesPage },
    { path: 'messages', component: MessagesPage },
  ],
};
