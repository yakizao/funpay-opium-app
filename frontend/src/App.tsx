import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Accounts from './pages/Accounts';
import Chats from './pages/Chats';
import Orders from './pages/Orders';
import Login from './pages/Login';
import { useAuth } from './auth/AuthContext';
import { getModuleManifests } from './modules';

/** Full-screen centered spinner for initial auth check */
function AuthLoader() {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
      }}
    >
      <CircularProgress sx={{ color: '#8B5CF6' }} />
    </Box>
  );
}

export default function App() {
  const { user, loading, authDisabled } = useAuth();
  const manifests = getModuleManifests();

  // Still checking auth status
  if (loading) return <AuthLoader />;

  // Auth is enabled and user is NOT authenticated → show login
  if (!authDisabled && !user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  // Authenticated (or auth disabled) → main app
  return (
    <Routes>
      {/* Redirect /login to / when already logged in */}
      <Route path="/login" element={<Navigate to="/" replace />} />

      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/accounts/:accountId/chats" element={<Chats />} />
        <Route path="/accounts/:accountId/orders" element={<Orders />} />

        {/* Module routes - auto-registered from manifests */}
        {manifests.flatMap(m =>
          m.routes.map(r => (
            <Route
              key={`${m.name}-${r.path}`}
              path={`/accounts/:accountId/modules/${m.name}/${r.path}`}
              element={<r.component />}
            />
          ))
        )}

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
