'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/services/api';
import { Shield, PlayCircle, AlertTriangle, RefreshCw, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ExecutionMode = 'simulation' | 'paper' | 'live';

interface ExecutionModeState {
  mode: ExecutionMode;
  is_live: boolean;
  is_simulation: boolean;
  description: string;
}

interface SimulationAccount {
  has_account: boolean;
  balance: number;
  equity: number;
  margin_used: number;
  margin_available: number;
  initial_balance: number;
  total_pnl: number;
  total_trades: number;
  winning_trades: number;
  win_rate: number;
  open_positions: number;
  unrealized_pnl: number;
  slippage_pips: number;
  commission_per_lot: number;
  latency_ms: number;
  fill_probability: number;
  last_reset: string | null;
}

export function useExecutionMode() {
  const [modeState, setModeState] = useState<ExecutionModeState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMode = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient.getExecutionMode();
      setModeState(data);
    } catch (err) {
      console.error('Failed to load execution mode:', err);
      setError('Failed to load execution mode');
      // Default to simulation on error (safest)
      setModeState({
        mode: 'simulation',
        is_live: false,
        is_simulation: true,
        description: 'Defaulted to simulation mode due to error',
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMode();
  }, [loadMode]);

  const setMode = async (
    newMode: ExecutionMode,
    options?: { reason?: string; password?: string; confirmed?: boolean }
  ) => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient.setExecutionMode(newMode, options);
      setModeState(data);
      window.dispatchEvent(new CustomEvent('executionModeChanged', { detail: data }));
      return data;
    } catch (err: unknown) {
      const errorDetail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(errorDetail || 'Failed to change execution mode');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  return {
    mode: modeState?.mode ?? 'simulation',
    isLive: modeState?.is_live ?? false,
    isSimulation: modeState?.is_simulation ?? true,
    description: modeState?.description ?? '',
    isLoading,
    error,
    setMode,
    refresh: loadMode,
  };
}

interface ExecutionModeIndicatorProps {
  showLabel?: boolean;
  className?: string;
}

export function ExecutionModeIndicator({ showLabel = true, className }: ExecutionModeIndicatorProps) {
  const { mode, isLoading } = useExecutionMode();

  if (isLoading) {
    return <div className="animate-pulse h-6 w-28 bg-gray-200 dark:bg-gray-700 rounded" />;
  }

  const modeConfig = {
    simulation: {
      icon: Shield,
      label: 'SIMULATION',
      bgClass: 'bg-blue-100 dark:bg-blue-900',
      textClass: 'text-blue-800 dark:text-blue-200',
    },
    paper: {
      icon: PlayCircle,
      label: 'PAPER',
      bgClass: 'bg-yellow-100 dark:bg-yellow-900',
      textClass: 'text-yellow-800 dark:text-yellow-200',
    },
    live: {
      icon: AlertTriangle,
      label: 'LIVE',
      bgClass: 'bg-red-100 dark:bg-red-900',
      textClass: 'text-red-800 dark:text-red-200',
    },
  };

  const config = modeConfig[mode];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium',
        config.bgClass,
        config.textClass,
        className
      )}
    >
      <Icon className="h-4 w-4" />
      {showLabel && <span>{config.label}</span>}
    </div>
  );
}

interface ExecutionModeWarningProps {
  className?: string;
}

export function ExecutionModeWarning({ className }: ExecutionModeWarningProps) {
  const { mode, isLive } = useExecutionMode();

  if (!isLive) {
    return null;
  }

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-4 py-2 bg-red-100 text-red-800 rounded-lg dark:bg-red-900 dark:text-red-200 border border-red-300 dark:border-red-700',
        className
      )}
    >
      <AlertTriangle className="h-5 w-5" />
      <span className="font-bold">⚠️ LIVE TRADING</span>
      <span className="text-sm">- Real money is at risk!</span>
    </div>
  );
}

interface ExecutionModeSelectorProps {
  className?: string;
  onModeChange?: (mode: ExecutionMode) => void;
}

export function ExecutionModeSelector({ className, onModeChange }: ExecutionModeSelectorProps) {
  const { mode, isLoading, setMode, error } = useExecutionMode();
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingMode, setPendingMode] = useState<ExecutionMode | null>(null);
  const [password, setPassword] = useState('');
  const [reason, setReason] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleModeSelect = async (newMode: ExecutionMode) => {
    if (newMode === mode) return;

    if (newMode === 'live') {
      // Show confirmation dialog for live mode
      setPendingMode(newMode);
      setShowConfirmDialog(true);
      setLocalError(null);
      return;
    }

    try {
      await setMode(newMode);
      onModeChange?.(newMode);
    } catch (err) {
      console.error('Failed to change mode:', err);
    }
  };

  const handleLiveConfirm = async () => {
    if (!pendingMode || !password || !reason) {
      setLocalError('Password and reason are required for live trading');
      return;
    }

    try {
      await setMode(pendingMode, {
        password,
        reason,
        confirmed: true,
      });
      setShowConfirmDialog(false);
      setPassword('');
      setReason('');
      setPendingMode(null);
      setLocalError(null);
      onModeChange?.(pendingMode);
    } catch (err: unknown) {
      const errorDetail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setLocalError(errorDetail || 'Failed to enable live trading');
    }
  };

  const modes: { value: ExecutionMode; label: string; icon: React.ElementType; description: string }[] = [
    {
      value: 'simulation',
      label: 'Simulation',
      icon: Shield,
      description: 'Virtual trading - no real money',
    },
    {
      value: 'paper',
      label: 'Paper',
      icon: PlayCircle,
      description: "Broker's demo account",
    },
    {
      value: 'live',
      label: 'Live',
      icon: AlertTriangle,
      description: 'Real money - USE WITH CAUTION',
    },
  ];

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex gap-2">
        {modes.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            onClick={() => handleModeSelect(value)}
            disabled={isLoading}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all',
              mode === value
                ? value === 'live'
                  ? 'bg-red-500 text-white ring-2 ring-red-500'
                  : value === 'paper'
                  ? 'bg-yellow-500 text-white ring-2 ring-yellow-500'
                  : 'bg-blue-500 text-white ring-2 ring-blue-500'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700',
              isLoading && 'opacity-50 cursor-not-allowed'
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {error && (
        <div className="text-red-600 text-sm dark:text-red-400">{error}</div>
      )}

      {/* Live Mode Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center gap-3 text-red-600 dark:text-red-400 mb-4">
              <AlertTriangle className="h-8 w-8" />
              <h3 className="text-xl font-bold">Enable Live Trading?</h3>
            </div>

            <div className="space-y-4">
              <div className="bg-red-50 dark:bg-red-900/30 p-4 rounded-lg text-sm text-red-800 dark:text-red-200">
                <p className="font-bold mb-2">⚠️ WARNING</p>
                <p>
                  You are about to enable LIVE TRADING. Real money will be at risk.
                  All trades will be executed with actual funds.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Password Verification</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  placeholder="Enter your password"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Reason for Live Trading</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  placeholder="Why are you enabling live trading?"
                  rows={2}
                />
              </div>

              {localError && (
                <div className="text-red-600 text-sm dark:text-red-400">{localError}</div>
              )}

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => {
                    setShowConfirmDialog(false);
                    setPassword('');
                    setReason('');
                    setPendingMode(null);
                    setLocalError(null);
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleLiveConfirm}
                  disabled={!password || !reason}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Enable Live Trading
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface SimulationAccountCardProps {
  className?: string;
}

export function SimulationAccountCard({ className }: SimulationAccountCardProps) {
  const [account, setAccount] = useState<SimulationAccount | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isResetting, setIsResetting] = useState(false);
  const { mode } = useExecutionMode();

  const loadAccount = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await apiClient.getSimulationAccount();
      setAccount(data);
    } catch (err) {
      console.error('Failed to load simulation account:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (mode === 'simulation') {
      loadAccount();
    }
  }, [mode, loadAccount]);

  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset your simulation account? All positions will be closed.')) {
      return;
    }

    try {
      setIsResetting(true);
      const data = await apiClient.resetSimulationAccount();
      setAccount(data);
    } catch (err) {
      console.error('Failed to reset account:', err);
    } finally {
      setIsResetting(false);
    }
  };

  if (mode !== 'simulation') {
    return null;
  }

  if (isLoading) {
    return <div className="animate-pulse h-40 bg-gray-200 dark:bg-gray-700 rounded-lg" />;
  }

  if (!account || !account.has_account) {
    return (
      <div className={cn('p-4 bg-gray-100 dark:bg-gray-800 rounded-lg', className)}>
        <p className="text-gray-500">No simulation account found. Start trading to create one.</p>
      </div>
    );
  }

  const pnlColor = account.total_pnl >= 0 ? 'text-green-600' : 'text-red-600';

  return (
    <div className={cn('p-4 bg-white dark:bg-gray-800 rounded-lg shadow border dark:border-gray-700', className)}>
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Shield className="h-5 w-5 text-blue-500" />
          Simulation Account
        </h3>
        <div className="flex gap-2">
          <button
            onClick={loadAccount}
            className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={handleReset}
            disabled={isResetting}
            className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded"
          >
            {isResetting ? 'Resetting...' : 'Reset'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-gray-500 dark:text-gray-400">Balance</div>
          <div className="text-lg font-semibold">${account.balance.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Equity</div>
          <div className="text-lg font-semibold">${account.equity.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Total P&L</div>
          <div className={cn('text-lg font-semibold', pnlColor)}>
            {account.total_pnl >= 0 ? '+' : ''}${account.total_pnl.toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Win Rate</div>
          <div className="text-lg font-semibold">{account.win_rate.toFixed(1)}%</div>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t dark:border-gray-700 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-gray-500 dark:text-gray-400">Trades</div>
          <div>{account.total_trades}</div>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Winning</div>
          <div>{account.winning_trades}</div>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Open Positions</div>
          <div>{account.open_positions}</div>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Unrealized P&L</div>
          <div className={cn(account.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600')}>
            {account.unrealized_pnl >= 0 ? '+' : ''}${account.unrealized_pnl.toFixed(2)}
          </div>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-1 mb-1">
          <Settings className="h-3 w-3" />
          Simulation Settings
        </div>
        <div className="flex flex-wrap gap-4">
          <span>Slippage: {account.slippage_pips} pips</span>
          <span>Commission: ${account.commission_per_lot}/lot</span>
          <span>Latency: {account.latency_ms}ms</span>
          <span>Fill: {(account.fill_probability * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
}
