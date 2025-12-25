'use client';

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { apiClient } from '@/services/api';
import { SystemMode } from '@/types';

interface ModeContextType {
  mode: SystemMode;
  isLoading: boolean;
  error: string | null;
  canSwitch: boolean;
  switchError: string | null;
  setMode: (mode: SystemMode, reason?: string) => Promise<void>;
  refreshMode: () => Promise<void>;
}

const ModeContext = createContext<ModeContextType | undefined>(undefined);

interface ModeProviderProps {
  children: ReactNode;
}

export function ModeProvider({ children }: ModeProviderProps) {
  const [mode, setModeState] = useState<SystemMode>('guide');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canSwitch, setCanSwitch] = useState(true);
  const [switchError, setSwitchError] = useState<string | null>(null);

  const loadMode = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient.getSystemMode();
      setModeState(data.mode);
      setCanSwitch(true);
      setSwitchError(null);
    } catch (err) {
      console.error('Failed to load system mode:', err);
      setError('Failed to load system mode');
      // Default to guide mode on error for safety
      setModeState('guide');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMode();
  }, [loadMode]);

  const setMode = async (newMode: SystemMode, reason?: string) => {
    try {
      setError(null);
      setSwitchError(null);
      setIsLoading(true);
      
      await apiClient.setSystemMode(newMode, reason);
      setModeState(newMode);
      setCanSwitch(true);
      
      // Broadcast mode change event for other components
      window.dispatchEvent(new CustomEvent('modeChanged', { detail: { mode: newMode } }));
    } catch (err: unknown) {
      console.error('Failed to set system mode:', err);
      const errorMessage = err instanceof Error 
        ? err.message 
        : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to set system mode';
      setSwitchError(errorMessage);
      setCanSwitch(false);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const refreshMode = async () => {
    await loadMode();
  };

  return (
    <ModeContext.Provider value={{ mode, isLoading, error, canSwitch, switchError, setMode, refreshMode }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  const context = useContext(ModeContext);
  if (context === undefined) {
    throw new Error('useMode must be used within a ModeProvider');
  }
  return context;
}
