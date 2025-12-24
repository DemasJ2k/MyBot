# Prompt 12: Frontend Core

## Purpose

Build the Next.js frontend application with TypeScript and TailwindCSS that provides a complete user interface for Flowrex. This system implements the App Router architecture, manages authentication, handles API communication, provides global state management, and enforces mode-aware UI (GUIDE vs AUTONOMOUS).

## Scope

- Next.js 14+ with App Router
- TypeScript strict mode
- TailwindCSS for styling
- API client layer with type safety
- Authentication and session management
- Global state management (server state + client state)
- Mode-aware UI components
- Error boundaries and loading states
- Reusable component library
- Custom hooks for data fetching
- Complete test suite

## Frontend Architecture

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Dashboard home
│   ├── (auth)/                  # Auth route group
│   │   ├── login/
│   │   └── register/
│   ├── strategies/
│   ├── backtest/
│   ├── optimization/
│   ├── signals/
│   ├── execution/
│   ├── performance/
│   ├── journal/
│   ├── ai-chat/
│   └── settings/
├── components/                   # Reusable components
│   ├── ui/                      # Base UI components
│   ├── charts/                  # Chart components
│   ├── tables/                  # Table components
│   └── layout/                  # Layout components
├── hooks/                       # Custom React hooks
├── lib/                         # Utilities
├── services/                    # API clients
├── types/                       # TypeScript types
└── providers/                   # Context providers
```

## Implementation

### Step 1: Project Setup

Initialize Next.js project:

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app --src-dir=false --import-alias="@/*"
```

Update `package.json`:

```json
{
  "name": "flowrex-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "jest",
    "test:watch": "jest --watch"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@tanstack/react-query": "^5.28.0",
    "axios": "^1.6.8",
    "date-fns": "^3.6.0",
    "recharts": "^2.12.0",
    "lucide-react": "^0.363.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "typescript": "^5",
    "eslint": "^8",
    "eslint-config-next": "14.2.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8",
    "autoprefixer": "^10.0.1",
    "@testing-library/react": "^14.2.0",
    "@testing-library/jest-dom": "^6.4.0",
    "jest": "^29.7.0",
    "jest-environment-jsdom": "^29.7.0"
  }
}
```

### Step 2: TypeScript Configuration

Update `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### Step 3: Type Definitions

Create `types/index.ts`:

```typescript
// API Response types
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

// User types
export interface User {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// System mode
export type SystemMode = "guide" | "autonomous";

export interface SystemConfig {
  mode: SystemMode;
}

// Strategy types
export interface Strategy {
  name: string;
  description?: string;
  config: Record<string, any>;
}

// Signal types
export interface Signal {
  id: number;
  strategy_name: string;
  symbol: string;
  signal_type: "long" | "short";
  status: "pending" | "executed" | "cancelled";
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  risk_percent: number;
  confidence: number;
  reason?: string;
  signal_time: string;
  risk_reward_ratio: number;
}

// Backtest types
export interface BacktestResult {
  id: number;
  strategy_name: string;
  symbol: string;
  interval: string;
  start_date: string;
  end_date: string;
  initial_balance: number;
  final_balance: number;
  total_return_percent: number;
  total_trades: number;
  win_rate_percent: number;
  profit_factor: number | null;
  max_drawdown_percent: number;
  sharpe_ratio: number | null;
  created_at: string;
}

// Execution types
export interface ExecutionOrder {
  id: number;
  client_order_id: string;
  broker_order_id: string | null;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  status: string;
  filled_quantity: number;
  average_fill_price: number | null;
}

// Journal types
export interface JournalEntry {
  id: number;
  entry_id: string;
  source: "backtest" | "live" | "paper";
  strategy_name: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_percent: number;
  is_winner: boolean;
  exit_reason: string;
  entry_time: string;
  exit_time: string;
}

// Risk types
export interface RiskState {
  account_balance: number;
  peak_balance: number;
  current_drawdown_percent: number;
  daily_pnl: number;
  daily_loss_percent: number;
  trades_today: number;
  trades_this_hour: number;
  open_positions_count: number;
  total_exposure: number;
  total_exposure_percent: number;
  emergency_shutdown_active: boolean;
  throttling_active: boolean;
  last_updated: string;
}

// AI Decision types
export interface AIDecision {
  id: number;
  agent_role: string;
  decision_type: string;
  decision: string;
  reasoning: string;
  context: Record<string, any>;
  executed: boolean;
  decision_time: string;
}
```

### Step 4: API Client

Create `services/api.ts`:

```typescript
import axios, { AxiosInstance, AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;

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
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && originalRequest) {
          // Try to refresh token
          const refreshed = await this.refreshToken();

          if (refreshed) {
            // Retry original request
            return this.client(originalRequest);
          }

          // Refresh failed, redirect to login
          this.clearTokens();
          window.location.href = '/login';
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

  private clearTokens() {
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
      username: email,
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
  async createOptimizationJob(data: any) {
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

  // Execution
  async executeSignal(signalId: number, positionSize: number, brokerType = 'paper') {
    const response = await this.client.post('/execution/execute', {
      signal_id: signalId,
      position_size: positionSize,
      broker_type: brokerType,
    });
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

  // Journal
  async getJournalEntries(params?: { strategy_name?: string; symbol?: string; source?: string; limit?: number }) {
    const response = await this.client.get('/journal/entries', { params });
    return response.data;
  }

  async getJournalEntry(entryId: string) {
    const response = await this.client.get(`/journal/entries/${entryId}`);
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

  // AI
  async getAIDecisions(params?: { agent_role?: string; limit?: number }) {
    const response = await this.client.get('/ai/decisions', { params });
    return response.data;
  }

  async getAgentMemory(params?: { agent_role?: string; memory_type?: string }) {
    const response = await this.client.get('/ai/memory', { params });
    return response.data;
  }
}

export const apiClient = new ApiClient();
```

### Step 5: React Query Provider

Create `providers/QueryProvider.tsx`:

```typescript
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

### Step 6: Mode Provider

Create `providers/ModeProvider.tsx`:

```typescript
'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '@/services/api';
import { SystemMode } from '@/types';

interface ModeContextType {
  mode: SystemMode;
  isLoading: boolean;
  setMode: (mode: SystemMode) => Promise<void>;
}

const ModeContext = createContext<ModeContextType | undefined>(undefined);

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<SystemMode>('guide');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadMode();
  }, []);

  const loadMode = async () => {
    try {
      const data = await apiClient.getSystemMode();
      setModeState(data.mode);
    } catch (error) {
      console.error('Failed to load system mode:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const setMode = async (newMode: SystemMode) => {
    try {
      await apiClient.setSystemMode(newMode);
      setModeState(newMode);
    } catch (error) {
      console.error('Failed to set system mode:', error);
      throw error;
    }
  };

  return (
    <ModeContext.Provider value={{ mode, isLoading, setMode }}>
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
```

### Step 7: Custom Hooks

Create `hooks/useAuth.ts`:

```typescript
'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/services/api';
import { User } from '@/types';
import { useRouter } from 'next/navigation';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
    } catch (error) {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    try {
      await apiClient.login(email, password);
      await loadUser();
      router.push('/');
    } catch (error) {
      throw error;
    }
  };

  const logout = async () => {
    await apiClient.logout();
    setUser(null);
    router.push('/login');
  };

  return { user, isLoading, login, logout, isAuthenticated: !!user };
}
```

Create `hooks/useStrategies.ts`:

```typescript
'use client';

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient.listStrategies(),
  });
}

export function useSignals(params?: { strategy_name?: string; symbol?: string; status?: string; limit?: number }) {
  return useQuery({
    queryKey: ['signals', params],
    queryFn: () => apiClient.getSignals(params),
    refetchInterval: 5000, // Refresh every 5 seconds
  });
}
```

Create `hooks/useBacktest.ts`:

```typescript
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

export function useBacktestResults(params?: { strategy_name?: string; symbol?: string; limit?: number }) {
  return useQuery({
    queryKey: ['backtest-results', params],
    queryFn: () => apiClient.getBacktestResults(params),
  });
}

export function useBacktestDetail(backtestId: number) {
  return useQuery({
    queryKey: ['backtest', backtestId],
    queryFn: () => apiClient.getBacktestDetail(backtestId),
    enabled: !!backtestId,
  });
}

export function useRunBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) => apiClient.runBacktest(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-results'] });
    },
  });
}
```

### Step 8: Root Layout

Create `app/layout.tsx`:

```typescript
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/providers/QueryProvider';
import { ModeProvider } from '@/providers/ModeProvider';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Flowrex - AI Trading Platform',
  description: 'Institutional-grade AI-powered trading platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <QueryProvider>
          <ModeProvider>
            {children}
          </ModeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
```

### Step 9: UI Components

Create `components/ui/button.tsx`:

```typescript
import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'underline-offset-4 hover:underline text-primary',
      },
      size: {
        default: 'h-10 py-2 px-4',
        sm: 'h-9 px-3 rounded-md',
        lg: 'h-11 px-8 rounded-md',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
```

Create `components/ui/card.tsx`:

```typescript
import * as React from 'react';
import { cn } from '@/lib/utils';

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('rounded-lg border bg-card text-card-foreground shadow-sm', className)}
      {...props}
    />
  )
);
Card.displayName = 'Card';

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('flex flex-col space-y-1.5 p-6', className)} {...props} />
  )
);
CardHeader.displayName = 'CardHeader';

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn('text-2xl font-semibold leading-none tracking-tight', className)} {...props} />
  )
);
CardTitle.displayName = 'CardTitle';

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('p-6 pt-0', className)} {...props} />
  )
);
CardContent.displayName = 'CardContent';

export { Card, CardHeader, CardTitle, CardContent };
```

Create `components/layout/ModeIndicator.tsx`:

```typescript
'use client';

import { useMode } from '@/providers/ModeProvider';
import { Shield, Zap } from 'lucide-react';

export function ModeIndicator() {
  const { mode, isLoading } = useMode();

  if (isLoading) {
    return <div className="animate-pulse h-6 w-24 bg-gray-200 rounded"></div>;
  }

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium ${
        mode === 'guide'
          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
          : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      }`}
    >
      {mode === 'guide' ? <Shield className="h-4 w-4" /> : <Zap className="h-4 w-4" />}
      <span className="uppercase">{mode}</span>
    </div>
  );
}
```

Create `lib/utils.ts`:

```typescript
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(value);
}

export function formatPercent(value: number, decimals = 2): string {
  return `${value.toFixed(decimals)}%`;
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date));
}
```

### Step 10: Error Boundary

Create `components/ErrorBoundary.tsx`:

```typescript
'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Something went wrong</h2>
            <p className="text-gray-600 mb-4">{this.state.error?.message}</p>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
```

### Step 11: Tests

Create `jest.config.js`:

```javascript
const nextJest = require('next/jest');

const createJestConfig = nextJest({
  dir: './',
});

const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
};

module.exports = createJestConfig(customJestConfig);
```

Create `jest.setup.js`:

```javascript
import '@testing-library/jest-dom';
```

Create `__tests__/hooks/useAuth.test.tsx`:

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useAuth } from '@/hooks/useAuth';

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

// Mock API client
jest.mock('@/services/api', () => ({
  apiClient: {
    getCurrentUser: jest.fn(),
    login: jest.fn(),
    logout: jest.fn(),
  },
}));

describe('useAuth', () => {
  it('should initialize with loading state', () => {
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
});
```

## Validation Checklist

Before proceeding to Prompt 13, verify:

- [ ] Next.js 14+ with App Router installed
- [ ] TypeScript strict mode configured
- [ ] TailwindCSS configured
- [ ] All TypeScript types defined in `types/index.ts`
- [ ] API client implemented with interceptors
- [ ] Token refresh logic working
- [ ] React Query provider configured
- [ ] Mode provider managing system mode
- [ ] useAuth hook implemented
- [ ] useStrategies hook implemented
- [ ] useBacktest hook implemented
- [ ] Root layout with providers
- [ ] Button and Card UI components created
- [ ] ModeIndicator component shows current mode
- [ ] Error boundary implemented
- [ ] Utility functions (cn, formatCurrency, formatDate) created
- [ ] Jest configured for testing
- [ ] At least one test passing
- [ ] npm run dev starts without errors
- [ ] npm run build completes successfully
- [ ] TypeScript compilation has no errors
- [ ] All imports resolve correctly
- [ ] CROSSCHECK.md validation for Prompt 12 completed

## Hard Stop Criteria

**DO NOT PROCEED to Prompt 13 unless:**

1. ✅ Next.js project builds without errors
2. ✅ TypeScript compiles with no errors in strict mode
3. ✅ API client successfully connects to backend
4. ✅ Authentication flow works (login/logout)
5. ✅ Mode provider loads and updates system mode
6. ✅ React Query hooks fetch data correctly
7. ✅ Error boundary catches and displays errors
8. ✅ All utility functions work as expected
9. ✅ Jest tests run and pass
10. ✅ CROSSCHECK.md section for Prompt 12 fully validated

If any criterion fails, **HALT** and fix before continuing.

---

**Completion Criteria:**
- Frontend core infrastructure complete
- Type-safe API integration working
- Authentication and session management functional
- Global state management configured
- Mode awareness implemented
- Reusable components library started
- Testing infrastructure ready
- System ready for UI Dashboards (Prompt 13)
