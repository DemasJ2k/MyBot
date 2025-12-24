import { apiClient } from '@/services/api';

describe('ApiClient', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should be instantiated', () => {
    expect(apiClient).toBeDefined();
  });

  it('should have all required methods', () => {
    expect(typeof apiClient.login).toBe('function');
    expect(typeof apiClient.logout).toBe('function');
    expect(typeof apiClient.register).toBe('function');
    expect(typeof apiClient.getCurrentUser).toBe('function');
    expect(typeof apiClient.getSystemMode).toBe('function');
    expect(typeof apiClient.listStrategies).toBe('function');
  });

  it('should clear tokens on logout', async () => {
    // Set tokens first
    window.localStorage.setItem('access_token', 'test-token');
    window.localStorage.setItem('refresh_token', 'test-refresh');

    // Call logout
    await apiClient.logout();

    // Verify removeItem was called
    expect(window.localStorage.removeItem).toHaveBeenCalledWith('access_token');
    expect(window.localStorage.removeItem).toHaveBeenCalledWith('refresh_token');
  });
});
