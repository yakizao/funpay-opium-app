import { useState } from 'react';
import {
  Box, Typography, Button, IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
  DialogActions, Table, TableHead, TableBody, TableRow, TableCell,
  Chip, alpha,
} from '@mui/material';
import Grid from '@mui/material/Grid2';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  PlayCircle as StartIcon,
  StopCircle as StopIcon,
  Settings as SettingsIcon,
  People as PeopleIcon,
  PlayArrow as RunningIcon,
  Error as ErrorIcon,
  Extension as ModulesIcon,
} from '@mui/icons-material';
import { StatCard, StatusDot, stateToStatus } from '../components/GlowCard';
import { AddAccountDialog, AccountSettingsDialog } from '../components/AccountDialogs';
import { PageHeader } from '../components/PageHeader';
import { TablePaper } from '../components/TablePaper';
import { useLayout } from '../components/Layout';
import { useAccountActions } from '../hooks/useAccountActions';

export default function Dashboard() {
  const { accounts, refetch, notify } = useLayout();
  const [addOpen, setAddOpen] = useState(false);
  const {
    availableModules, addModuleDialog, settingsDialog,
    handleDelete, handleStart, handleStop, handleAddModule,
    openAddModule, closeAddModule, openSettings, closeSettings,
  } = useAccountActions();

  const running = accounts.filter(a => a.is_running).length;
  const errors = accounts.filter(a => a.state === 'error').length;
  const totalModules = accounts.reduce((sum, a) => sum + (a.modules?.length ?? 0), 0);

  return (
    <Box>
      <PageHeader
        title="dashboard"
        subtitle={`${accounts.length} accounts · ${running} running`}
        onRefresh={refetch}
        actions={
          <Button size="small" variant="contained" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
            add account
          </Button>
        }
      />

      {/* Stats */}
      <Grid container spacing={1.5} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard label="accounts" value={accounts.length} icon={<PeopleIcon />} color="#8B5CF6" />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            label="running"
            value={running}
            icon={<RunningIcon />}
            color="#22C55E"
            subtitle={`${accounts.length - running} stopped`}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard label="errors" value={errors} icon={<ErrorIcon />} color={errors > 0 ? '#EF4444' : '#22C55E'} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard label="modules" value={totalModules} icon={<ModulesIcon />} color="#06B6D4" />
        </Grid>
      </Grid>

      {/* Accounts Table */}
      <TablePaper>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 40 }}></TableCell>
              <TableCell>account</TableCell>
              <TableCell>username</TableCell>
              <TableCell>state</TableCell>
              <TableCell>modules</TableCell>
              <TableCell align="right">actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {accounts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>
                  No accounts yet. click "add account" to get started.
                </TableCell>
              </TableRow>
            ) : (
              accounts.map(acc => {
                const status = stateToStatus(acc.state);
                return (
                <TableRow key={acc.account_id} hover>
                  <TableCell><StatusDot status={status} size={8} /></TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>{acc.account_id}</Typography>
                    {acc.fp_id && <Typography variant="caption" color="text.secondary">FP #{acc.fp_id}</Typography>}
                  </TableCell>
                  <TableCell>{acc.username || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={acc.state}
                      sx={{
                        bgcolor: alpha(
                          status === 'running' ? '#22C55E'
                          : status === 'error' ? '#EF4444' : '#707070',
                          0.12
                        ),
                        color: status === 'running' ? '#22C55E'
                          : status === 'error' ? '#EF4444' : '#a0a0a0',
                        fontWeight: 600, fontSize: '0.7rem', height: 22,
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                      {acc.modules?.map(m => (
                        <Chip key={m} size="small" label={m.replace(/_/g, ' ')} sx={{
                          fontSize: '0.68rem', height: 20,
                          bgcolor: alpha('#8B5CF6', 0.1), color: '#A78BFA',
                        }} />
                      ))}
                      <Tooltip title="add module">
                        <IconButton size="small" onClick={() => openAddModule(acc.account_id)}>
                          <AddIcon sx={{ fontSize: 14 }} />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                      <Tooltip title="settings"><IconButton size="small" onClick={() => openSettings(acc.account_id)}><SettingsIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                      {acc.is_running ? (
                        <Tooltip title="stop"><IconButton size="small" onClick={() => handleStop(acc.account_id)} color="warning"><StopIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                      ) : (
                        <Tooltip title="start"><IconButton size="small" onClick={() => handleStart(acc.account_id)} color="success"><StartIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                      )}
                      <Tooltip title="delete"><IconButton size="small" onClick={() => handleDelete(acc.account_id)} color="error"><DeleteIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              );})
            )}
          </TableBody>
        </Table>
      </TablePaper>

      {/* Dialogs */}
      <AddAccountDialog open={addOpen} onClose={() => setAddOpen(false)} onSuccess={() => { refetch(); setAddOpen(false); notify('account created', 'success'); }} />
      <AccountSettingsDialog
        open={settingsDialog.open}
        accountId={settingsDialog.accountId}
        onClose={closeSettings}
        onSave={() => notify('settings saved', 'success')}
      />
      <Dialog open={addModuleDialog.open} onClose={closeAddModule} maxWidth="xs" fullWidth>
        <DialogTitle>add module</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>select a module to add to account "{addModuleDialog.accountId}"</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {availableModules
              .filter(m => !accounts.find(a => a.account_id === addModuleDialog.accountId)?.modules?.includes(m))
              .map(m => (
                <Button key={m} variant="outlined" onClick={() => handleAddModule(addModuleDialog.accountId, m)}>
                  {m.replace(/_/g, ' ')}
                </Button>
              ))}
            {availableModules.length === 0 && (
              <Typography variant="body2" color="text.secondary">no modules available</Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeAddModule}>close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
