import { renderHook, waitFor } from '@testing-library/react';
import { useAuth } from '@/hooks/useAuth';

// Mock API client
jest.mock('@/services/api', () => ({
  apiClient: {
    getCurrentUser: jest.fn(),
    login: jest.fn(),
    logout: jest.fn(),
    register: jest.fn(),
  },
}));

describe('useAuth', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should initialize with loading state', () => {
    const { apiClient } = require('@/services/api');
    apiClient.getCurrentUser.mockResolvedValue(null);

    const { result } = renderHook(() => useAuth());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.user).toBe(null);
  });

  it('should load user on mount', async () => {
    const mockUser = { id: 1, email: 'test@example.com', is_active: true, created_at: '2024-01-01' };
    const { apiClient } = require('@/services/api');
    apiClient.getCurrentUser.mockResolvedValue(mockUser);

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
    });
  });

  it('should handle user not found', async () => {
    const { apiClient } = require('@/services/api');
    apiClient.getCurrentUser.mockRejectedValue(new Error('Not authenticated'));

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.user).toBe(null);
      expect(result.current.isAuthenticated).toBe(false);
    });
  });
});
