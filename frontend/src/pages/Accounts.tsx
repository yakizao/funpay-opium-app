import { useState } from 'react';
import {
  Box, Typography, Button, IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
  DialogActions, Table, TableHead, TableBody, TableRow, TableCell,
  Chip, alpha,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  PlayCircle as StartIcon,
  StopCircle as StopIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { StatusDot, stateToStatus } from '../components/GlowCard';
import { AddAccountDialog, AccountSettingsDialog } from '../components/AccountDialogs';
import { PageHeader } from '../components/PageHeader';
import { TablePaper } from '../components/TablePaper';
import { useLayout } from '../components/Layout';
import { useAccountActions } from '../hooks/useAccountActions';

export default function AccountsPage() {
  const { accounts, refetch, notify } = useLayout();
  const [addOpen, setAddOpen] = useState(false);
  const {
    availableModules, addModuleDialog, settingsDialog,
    handleDelete, handleStart, handleStop, handleAddModule,
    openAddModule, closeAddModule, openSettings, closeSettings,
  } = useAccountActions();

  return (
    <Box>
      <PageHeader
        title="accounts"
        subtitle={`${accounts.length} accounts configured`}
        onRefresh={refetch}
        actions={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
            add account
          </Button>
        }
      />

      <TablePaper>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>status</TableCell>
              <TableCell>account id</TableCell>
              <TableCell>username</TableCell>
              <TableCell>fp id</TableCell>
              <TableCell>state</TableCell>
              <TableCell>modules</TableCell>
              <TableCell align="right">actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {accounts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>
                  No accounts yet. click "add account" to get started.
                </TableCell>
              </TableRow>
            ) : (
              accounts.map(acc => {
                const status = stateToStatus(acc.state);
                return (
                <TableRow key={acc.account_id}>
                  <TableCell><StatusDot status={status} size={10} /></TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.primary' }}>{acc.account_id}</Typography>
                  </TableCell>
                  <TableCell>{acc.username || '-'}</TableCell>
                  <TableCell>{acc.fp_id || '-'}</TableCell>
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
                        fontWeight: 600,
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                      {acc.modules?.map(m => (
                        <Chip key={m} size="small" label={m.replace(/_/g, ' ')} sx={{
                          fontSize: '0.68rem', height: 22,
                          bgcolor: alpha('#8B5CF6', 0.1), color: '#A78BFA',
                        }} />
                      ))}
                      <Tooltip title="add module">
                        <IconButton size="small" onClick={() => openAddModule(acc.account_id)}>
                          <AddIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                      <Tooltip title="settings"><IconButton size="small" onClick={() => openSettings(acc.account_id)}><SettingsIcon fontSize="small" /></IconButton></Tooltip>
                      {acc.is_running ? (
                        <Tooltip title="stop"><IconButton size="small" onClick={() => handleStop(acc.account_id)} color="warning"><StopIcon fontSize="small" /></IconButton></Tooltip>
                      ) : (
                        <Tooltip title="start"><IconButton size="small" onClick={() => handleStart(acc.account_id)} color="success"><StartIcon fontSize="small" /></IconButton></Tooltip>
                      )}
                      <Tooltip title="delete"><IconButton size="small" onClick={() => handleDelete(acc.account_id)} color="error"><DeleteIcon fontSize="small" /></IconButton></Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              );})
            )}
          </TableBody>
        </Table>
      </TablePaper>

      {/* Add Account Dialog */}
      <AddAccountDialog open={addOpen} onClose={() => setAddOpen(false)} onSuccess={() => { refetch(); setAddOpen(false); notify('account created', 'success'); }} />

      {/* Account Settings Dialog */}
      <AccountSettingsDialog
        open={settingsDialog.open}
        accountId={settingsDialog.accountId}
        onClose={closeSettings}
        onSave={() => notify('settings saved', 'success')}
      />

      {/* Add Module Dialog */}
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

