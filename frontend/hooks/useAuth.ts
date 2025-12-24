'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/services/api';
import { User } from '@/types';
import { useRouter } from 'next/navigation';

interface UseAuthReturn {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const loadUser = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = async (email: string, password: string) => {
    try {
      setError(null);
      await apiClient.login(email, password);
      await loadUser();
      router.push('/');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    }
  };

  const register = async (email: string, password: string) => {
    try {
      setError(null);
      await apiClient.register(email, password);
      // After registration, log in automatically
      await apiClient.login(email, password);
      await loadUser();
      router.push('/');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setError(message);
      throw err;
    }
  };

  const logout = async () => {
    await apiClient.logout();
    setUser(null);
    router.push('/login');
  };

  const refreshUser = async () => {
    await loadUser();
  };

  return {
    user,
    isLoading,
    error,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    refreshUser,
  };
}
