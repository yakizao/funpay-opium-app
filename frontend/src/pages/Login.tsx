import { useState, type FormEvent } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  LockOutlined,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import { useAuth } from '../auth/AuthContext';

export default function Login() {
  const { login } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login({ username, password });
      // AuthContext will update state → App.tsx will redirect to /
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Connection error';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: '#0e0e0e', // lighter than #09090B
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background glow - behind the card */}
      <Box
        sx={{
          position: 'absolute',
          width: 700,
          height: 700,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${alpha('#8B5CF6', 1)} 0%, ${alpha('#8B5CF6', 0.08)} 40%, transparent 60%)`,
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      <Card
        sx={{
          width: 400,
          maxWidth: '90vw',
          border: `1px solid ${alpha('#8B5CF6', 0.25)}`,
          boxShadow: `0 0 40px ${alpha('#8B5CF6', 0.2)}`,
          position: 'relative',
          zIndex: 1,
        }}
      >
        <CardContent sx={{ p: 4 }}>
          {/* Header */}
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: '14px',
                bgcolor: alpha('#8B5CF6', 0.12),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mx: 'auto',
                mb: 2,
              }}
            >
              <LockOutlined sx={{ fontSize: 28, color: '#A78BFA' }} />
            </Box>
            <Typography variant="h5" sx={{ fontWeight: 700, color: '#FAFAFA' }}>
              opium
            </Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              sign in to continue
            </Typography>
          </Box>

          {/* Error */}
          {error && (
            <Alert
              severity="error"
              sx={{ mb: 2, borderRadius: 2 }}
              onClose={() => setError(null)}
            >
              {error}
            </Alert>
          )}

          {/* Form */}
          <Box component="form" onSubmit={handleSubmit} noValidate>
            <TextField
              fullWidth
              label="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              disabled={loading}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              disabled={loading}
              sx={{ mb: 3 }}
              slotProps={{
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => setShowPassword(!showPassword)}
                        tabIndex={-1}
                      >
                        {showPassword ? (
                          <VisibilityOff fontSize="small" />
                        ) : (
                          <Visibility fontSize="small" />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                },
              }}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading || !username || !password}
              sx={{
                py: 1.3,
                fontSize: '0.9rem',
                bgcolor: '#8B5CF6',
                '&:hover': { bgcolor: '#7C3AED' },
              }}
            >
              {loading ? (
                <CircularProgress size={22} color="inherit" />
              ) : (
                'sign in'
              )}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
