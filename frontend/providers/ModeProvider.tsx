'use client';

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { apiClient } from '@/services/api';
import { SystemMode } from '@/types';

interface ModeContextType {
  mode: SystemMode;
  isLoading: boolean;
  error: string | null;
  setMode: (mode: SystemMode) => Promise<void>;
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

  const loadMode = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient.getSystemMode();
      setModeState(data.mode);
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

  const setMode = async (newMode: SystemMode) => {
    try {
      setError(null);
      await apiClient.setSystemMode(newMode);
      setModeState(newMode);
    } catch (err) {
      console.error('Failed to set system mode:', err);
      setError('Failed to set system mode');
      throw err;
    }
  };

  const refreshMode = async () => {
    await loadMode();
  };

  return (
    <ModeContext.Provider value={{ mode, isLoading, error, setMode, refreshMode }}>
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
