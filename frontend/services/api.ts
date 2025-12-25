import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;
  private isRefreshing = false;
  private refreshSubscribers: ((token: string) => void)[] = [];

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}/api/v1`,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = this.getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        const csrfToken = this.getCsrfToken();
        if (csrfToken) {
          config.headers['X-CSRF-Token'] = csrfToken;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
          if (this.isRefreshing) {
            // Wait for token refresh
            return new Promise((resolve) => {
              this.refreshSubscribers.push((token: string) => {
                originalRequest.headers.Authorization = `Bearer ${token}`;
                resolve(this.client(originalRequest));
              });
            });
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            const refreshed = await this.refreshToken();

            if (refreshed) {
              const token = this.getAccessToken();
              this.refreshSubscribers.forEach((callback) => callback(token!));
              this.refreshSubscribers = [];
              return this.client(originalRequest);
            }
          } catch {
            // Refresh failed
          } finally {
            this.isRefreshing = false;
          }

          // Refresh failed, redirect to login
          this.clearTokens();
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
        }

        return Promise.reject(error);
      }
    );
  }

  private getAccessToken(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('access_token');
    }
    return null;
  }

  private getRefreshToken(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('refresh_token');
    }
    return null;
  }

  private setTokens(accessToken: string, refreshToken: string) {
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  private getCsrfToken(): string | null {
    if (typeof document === 'undefined') return null;
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
  }

  clearTokens() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }

  private async refreshToken(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();

    if (!refreshToken) {
      return false;
    }

    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      });

      this.setTokens(response.data.access_token, response.data.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  // Auth endpoints
  async login(email: string, password: string) {
    const response = await this.client.post('/auth/login', {
      email,
      password,
    });

    this.setTokens(response.data.access_token, response.data.refresh_token);
    return response.data;
  }

  async register(email: string, password: string) {
    const response = await this.client.post('/auth/register', {
      email,
      password,
    });
    return response.data;
  }

  async logout() {
    this.clearTokens();
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  // System mode
  async getSystemMode() {
    const response = await this.client.get('/ai/mode');
    return response.data;
  }

  async setSystemMode(mode: 'guide' | 'autonomous') {
    const response = await this.client.put('/ai/mode', { mode });
    return response.data;
  }

  // Strategies
  async listStrategies() {
    const response = await this.client.get('/strategies/');
    return response.data;
  }

  async analyzeSymbol(symbol: string, strategyName?: string, interval = '1h') {
    const params = { interval, ...(strategyName && { strategy_name: strategyName }) };
    const response = await this.client.post(`/strategies/analyze/${symbol}`, null, { params });
    return response.data;
  }

  async getSignals(params?: { strategy_name?: string; symbol?: string; status?: string; limit?: number }) {
    const response = await this.client.get('/strategies/signals', { params });
    return response.data;
  }

  async cancelSignal(signalId: number) {
    const response = await this.client.post(`/strategies/signals/${signalId}/cancel`);
    return response.data;
  }

  // Backtesting
  async runBacktest(data: {
    strategy_name: string;
    symbol: string;
    interval: string;
    start_date: string;
    end_date: string;
    initial_balance?: number;
    commission_percent?: number;
    slippage_percent?: number;
    risk_per_trade_percent?: number;
  }) {
    const response = await this.client.post('/backtest/run', data);
    return response.data;
  }

  async getBacktestResults(params?: { strategy_name?: string; symbol?: string; limit?: number }) {
    const response = await this.client.get('/backtest/results', { params });
    return response.data;
  }

  async getBacktestDetail(backtestId: number) {
    const response = await this.client.get(`/backtest/results/${backtestId}`);
    return response.data;
  }

  // Optimization
  async createOptimizationJob(data: {
    strategy_name: string;
    symbol: string;
    interval: string;
    start_date: string;
    end_date: string;
    parameter_space: Record<string, unknown>;
    optimization_target?: string;
    n_trials?: number;
  }) {
    const response = await this.client.post('/optimization/jobs', data);
    return response.data;
  }

  async getOptimizationJobs(params?: { strategy_name?: string; status?: string; limit?: number }) {
    const response = await this.client.get('/optimization/jobs', { params });
    return response.data;
  }

  async getOptimizationJob(jobId: number) {
    const response = await this.client.get(`/optimization/jobs/${jobId}`);
    return response.data;
  }

  async createPlaybook(jobId: number, name: string, notes?: string) {
    const response = await this.client.post(`/optimization/jobs/${jobId}/playbook`, {
      name,
      notes,
    });
    return response.data;
  }

  async getPlaybooks(params?: { strategy_name?: string; symbol?: string; is_active?: boolean; limit?: number }) {
    const response = await this.client.get('/optimization/playbooks', { params });
    return response.data;
  }

  async activatePlaybook(playbookId: number) {
    const response = await this.client.post(`/optimization/playbooks/${playbookId}/activate`);
    return response.data;
  }

  async deactivatePlaybook(playbookId: number) {
    const response = await this.client.post(`/optimization/playbooks/${playbookId}/deactivate`);
    return response.data;
  }

  // Execution
  async executeSignal(signalId: number, positionSize: number, brokerType = 'paper') {
    const response = await this.client.post('/execution/execute', {
      signal_id: signalId,
      position_size: positionSize,
      broker_type: brokerType,
    });
    return response.data;
  }

  async getExecutionMode() {
    const response = await this.client.get('/execution/mode');
    return response.data;
  }

  async setExecutionMode(mode: 'guide' | 'autonomous') {
    const response = await this.client.post('/execution/mode', { mode });
    return response.data;
  }

  async getOrders(params?: { status?: string; limit?: number }) {
    const response = await this.client.get('/execution/orders', { params });
    return response.data;
  }

  async getOrder(orderId: number) {
    const response = await this.client.get(`/execution/orders/${orderId}`);
    return response.data;
  }

  async cancelOrder(orderId: number) {
    const response = await this.client.post(`/execution/orders/${orderId}/cancel`);
    return response.data;
  }

  async getBrokers() {
    const response = await this.client.get('/execution/brokers');
    return response.data;
  }

  // Risk
  async getRiskState() {
    const response = await this.client.get('/risk/state');
    return response.data;
  }

  async getRiskDecisions(limit = 50) {
    const response = await this.client.get('/risk/decisions', { params: { limit } });
    return response.data;
  }

  async getRiskLimits() {
    const response = await this.client.get('/risk/limits');
    return response.data;
  }

  async validateTrade(data: {
    symbol: string;
    side: string;
    quantity: number;
    entry_price: number;
    stop_loss: number;
  }) {
    const response = await this.client.post('/risk/validate', data);
    return response.data;
  }

  // Journal
  async getJournalEntries(params?: { strategy_name?: string; symbol?: string; source?: string; limit?: number }) {
    const response = await this.client.get('/journal/entries', { params });
    return response.data;
  }

  async getJournalEntry(entryId: string) {
    const response = await this.client.get(`/journal/entries/${entryId}`);
    return response.data;
  }

  async getJournalStats(params?: { strategy_name?: string; symbol?: string }) {
    const response = await this.client.get('/journal/stats', { params });
    return response.data;
  }

  async analyzeStrategy(strategyName: string, symbol: string, lookbackDays = 30) {
    const response = await this.client.get(`/journal/analyze/${strategyName}/${symbol}`, {
      params: { lookback_days: lookbackDays },
    });
    return response.data;
  }

  async detectUnderperformance(strategyName: string, symbol: string) {
    const response = await this.client.get(`/journal/underperformance/${strategyName}/${symbol}`);
    return response.data;
  }

  async runFeedbackCycle(strategyName: string, symbol: string) {
    const response = await this.client.post(`/journal/feedback/${strategyName}/${symbol}`);
    return response.data;
  }

  async getPerformanceSnapshots(params?: { strategy_name?: string; symbol?: string; limit?: number }) {
    const response = await this.client.get('/journal/snapshots', { params });
    return response.data;
  }

  // AI
  async getAIDecisions(params?: { agent_role?: string; limit?: number }) {
    const response = await this.client.get('/ai/decisions', { params });
    return response.data;
  }

  async getAgentMemory(params?: { agent_role?: string; memory_type?: string }) {
    const response = await this.client.get('/ai/memory', { params });
    return response.data;
  }

  async getCoordinatorState() {
    const response = await this.client.get('/ai/coordinator/state');
    return response.data;
  }

  // Data
  async getCandles(symbol: string, interval: string, limit?: number) {
    const response = await this.client.get('/data/candles', {
      params: { symbol, interval, limit },
    });
    return response.data;
  }

  async getQuote(symbol: string) {
    const response = await this.client.get(`/data/quote/${symbol}`);
    return response.data;
  }

  async searchSymbols(query: string) {
    const response = await this.client.get('/data/search', {
      params: { query },
    });
    return response.data;
  }

  async syncCandles(symbol: string, interval: string, startDate?: string, endDate?: string) {
    const response = await this.client.post('/data/sync', null, {
      params: { symbol, interval, start_date: startDate, end_date: endDate },
    });
    return response.data;
  }

  // ============= Settings API =============
  
  // System Settings
  async getSystemSettings() {
    const response = await this.client.get('/settings');
    return response.data;
  }

  async updateSystemSettings(updates: Record<string, unknown>, reason?: string) {
    const response = await this.client.put('/settings', { ...updates, reason });
    return response.data;
  }

  // System Mode (via new settings endpoint)
  async getSystemMode() {
    const response = await this.client.get('/settings/mode');
    return response.data;
  }

  async setSystemMode(mode: 'guide' | 'autonomous', reason?: string) {
    const response = await this.client.post('/settings/mode', { mode, reason });
    return response.data;
  }

  // Hard Constants
  async getHardConstants() {
    const response = await this.client.get('/settings/constants');
    return response.data;
  }

  // Settings Audit
  async getSettingsAudit(limit = 100, changeType?: string) {
    const response = await this.client.get('/settings/audit', {
      params: { limit, change_type: changeType },
    });
    return response.data;
  }

  // User Preferences
  async getUserPreferences() {
    const response = await this.client.get('/settings/preferences');
    return response.data;
  }

  async updateUserPreferences(updates: Record<string, unknown>) {
    const response = await this.client.put('/settings/preferences', updates);
    return response.data;
  }

  async addFavoriteSymbol(symbol: string) {
    const response = await this.client.post(`/settings/preferences/favorites/symbols/${symbol}`);
    return response.data;
  }

  async removeFavoriteSymbol(symbol: string) {
    const response = await this.client.delete(`/settings/preferences/favorites/symbols/${symbol}`);
    return response.data;
  }
}

export const apiClient = new ApiClient();
