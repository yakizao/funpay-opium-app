import { useState, useEffect, useCallback } from 'react';
import { accountsApi, systemApi } from '../api/client';
import { useLayout } from '../components/Layout';

/**
 * Shared hook for account management actions (start/stop/delete/addModule).
 * Eliminates duplication between Dashboard and Accounts pages.
 */
export function useAccountActions() {
  const { refetch, notify } = useLayout();
  const [availableModules, setAvailableModules] = useState<string[]>([]);
  const [addModuleDialog, setAddModuleDialog] = useState<{ open: boolean; accountId: string }>({
    open: false,
    accountId: '',
  });
  const [settingsDialog, setSettingsDialog] = useState<{ open: boolean; accountId: string }>({
    open: false,
    accountId: '',
  });

  useEffect(() => {
    systemApi.availableModules().then(r => setAvailableModules(r.data.modules)).catch(() => {});
  }, []);

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm(`delete account "${id}"? this action cannot be undone.`)) return;
    try {
      await accountsApi.delete(id);
      notify('account deleted', 'success');
      refetch();
    } catch {
      notify('failed to delete account', 'error');
    }
  }, [refetch, notify]);

  const handleStart = useCallback(async (id: string) => {
    try {
      await accountsApi.start(id);
      notify('account started', 'success');
      refetch();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      notify(detail || 'failed to start', 'error');
    }
  }, [refetch, notify]);

  const handleStop = useCallback(async (id: string) => {
    try {
      await accountsApi.stop(id);
      notify('account stopped', 'info');
      refetch();
    } catch {
      notify('failed to stop', 'error');
    }
  }, [refetch, notify]);

  const handleAddModule = useCallback(async (accountId: string, moduleName: string) => {
    try {
      await accountsApi.addModule(accountId, moduleName);
      notify(`module ${moduleName} added`, 'success');
      refetch();
      setAddModuleDialog({ open: false, accountId: '' });
    } catch {
      notify('failed to add module', 'error');
    }
  }, [refetch, notify]);

  const openAddModule = useCallback((accountId: string) => {
    setAddModuleDialog({ open: true, accountId });
  }, []);

  const closeAddModule = useCallback(() => {
    setAddModuleDialog({ open: false, accountId: '' });
  }, []);

  const openSettings = useCallback((accountId: string) => {
    setSettingsDialog({ open: true, accountId });
  }, []);

  const closeSettings = useCallback(() => {
    setSettingsDialog({ open: false, accountId: '' });
  }, []);

  return {
    availableModules,
    addModuleDialog,
    settingsDialog,
    handleDelete,
    handleStart,
    handleStop,
    handleAddModule,
    openAddModule,
    closeAddModule,
    openSettings,
    closeSettings,
  };
}
