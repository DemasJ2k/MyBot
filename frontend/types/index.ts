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
export type SystemMode = 'guide' | 'autonomous';

export interface SystemConfig {
  mode: SystemMode;
}

// Strategy types
export interface Strategy {
  name: string;
  description?: string;
  config: Record<string, unknown>;
}

// Signal types
export interface Signal {
  id: number;
  strategy_name: string;
  symbol: string;
  signal_type: 'long' | 'short';
  status: 'pending' | 'executed' | 'cancelled';
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

export interface BacktestRequest {
  strategy_name: string;
  symbol: string;
  interval: string;
  start_date: string;
  end_date: string;
  initial_balance?: number;
  commission_percent?: number;
  slippage_percent?: number;
  risk_per_trade_percent?: number;
}

// Execution types
export interface ExecutionOrder {
  id: number;
  client_order_id: string;
  broker_order_id: string | null;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  status: string;
  filled_quantity: number;
  average_fill_price: number | null;
}

// Journal types
export interface JournalEntry {
  id: number;
  entry_id: string;
  source: 'backtest' | 'live' | 'paper';
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
  context: Record<string, unknown>;
  executed: boolean;
  decision_time: string;
}

// Optimization types
export interface OptimizationJob {
  id: number;
  strategy_name: string;
  symbol: string;
  status: string;
  parameter_space: Record<string, unknown>;
  best_params: Record<string, unknown> | null;
  best_score: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface Playbook {
  id: number;
  name: string;
  strategy_name: string;
  symbol: string;
  parameters: Record<string, unknown>;
  performance_metrics: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

// Performance types
export interface PerformanceSnapshot {
  id: number;
  strategy_name: string;
  symbol: string;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  total_pnl: number;
  snapshot_time: string;
}

// Query params
export interface SignalQueryParams {
  strategy_name?: string;
  symbol?: string;
  status?: string;
  limit?: number;
}

export interface BacktestQueryParams {
  strategy_name?: string;
  symbol?: string;
  limit?: number;
}

export interface JournalQueryParams {
  strategy_name?: string;
  symbol?: string;
  source?: string;
  limit?: number;
}

export interface OptimizationQueryParams {
  strategy_name?: string;
  status?: string;
  limit?: number;
}
