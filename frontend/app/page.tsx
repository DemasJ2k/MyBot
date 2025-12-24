'use client';

import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useMode } from '@/providers/ModeProvider';
import { useRiskState } from '@/hooks/useRisk';
import { useSignals } from '@/hooks/useStrategies';
import { formatCurrency, formatPercent, getValueColor } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  AlertTriangle,
  Zap,
  Shield,
} from 'lucide-react';

interface SignalItem {
  id: number;
  strategy_name: string;
  symbol: string;
  signal_type: string;
  status: string;
  entry_price: number;
  confidence: number;
}

export default function Dashboard() {
  const { mode } = useMode();
  const { data: riskState, isLoading: riskLoading } = useRiskState();
  const { data: signals, isLoading: signalsLoading } = useSignals({ limit: 5 });

  return (
    <>
      <Sidebar />
      <PageContainer title="Dashboard">
        {/* Mode Banner */}
        <div
          className={`mb-6 p-4 rounded-lg flex items-center gap-3 ${
            mode === 'guide'
              ? 'bg-blue-50 border border-blue-200 dark:bg-blue-950 dark:border-blue-800'
              : 'bg-green-50 border border-green-200 dark:bg-green-950 dark:border-green-800'
          }`}
        >
          {mode === 'guide' ? (
            <>
              <Shield className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <div>
                <p className="font-medium text-blue-900 dark:text-blue-100">GUIDE Mode Active</p>
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  Signals require manual approval before execution
                </p>
              </div>
            </>
          ) : (
            <>
              <Zap className="h-5 w-5 text-green-600 dark:text-green-400" />
              <div>
                <p className="font-medium text-green-900 dark:text-green-100">
                  AUTONOMOUS Mode Active
                </p>
                <p className="text-sm text-green-700 dark:text-green-300">
                  Signals are automatically executed
                </p>
              </div>
            </>
          )}
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Account Balance</CardTitle>
              <TrendingUp className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {riskLoading ? (
                  <span className="animate-pulse">Loading...</span>
                ) : (
                  formatCurrency(riskState?.account_balance || 100000)
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Peak: {formatCurrency(riskState?.peak_balance || 100000)}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Daily P&L</CardTitle>
              <Activity className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${getValueColor(riskState?.daily_pnl || 0)}`}>
                {riskLoading ? (
                  <span className="animate-pulse">Loading...</span>
                ) : (
                  formatCurrency(riskState?.daily_pnl || 0)
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Daily loss: {formatPercent(riskState?.daily_loss_percent || 0)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Current Drawdown</CardTitle>
              <TrendingDown className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${getValueColor(-(riskState?.current_drawdown_percent || 0))}`}>
                {riskLoading ? (
                  <span className="animate-pulse">Loading...</span>
                ) : (
                  formatPercent(riskState?.current_drawdown_percent || 0)
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Open positions: {riskState?.open_positions_count || 0}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Risk Status</CardTitle>
              <AlertTriangle className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              {riskLoading ? (
                <span className="animate-pulse">Loading...</span>
              ) : riskState?.emergency_shutdown_active ? (
                <Badge variant="destructive" className="text-lg">SHUTDOWN</Badge>
              ) : riskState?.throttling_active ? (
                <Badge variant="warning" className="text-lg">THROTTLED</Badge>
              ) : (
                <Badge variant="success" className="text-lg">NORMAL</Badge>
              )}
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                Trades today: {riskState?.trades_today || 0}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Recent Signals */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Signals</CardTitle>
          </CardHeader>
          <CardContent>
            {signalsLoading ? (
              <div className="animate-pulse space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 bg-gray-100 dark:bg-gray-800 rounded" />
                ))}
              </div>
            ) : signals?.length > 0 ? (
              <div className="space-y-3">
                {signals.map((signal: SignalItem) => (
                  <div
                    key={signal.id}
                    className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <Badge variant={signal.signal_type === 'long' ? 'success' : 'destructive'}>
                        {signal.signal_type.toUpperCase()}
                      </Badge>
                      <div>
                        <p className="font-medium">{signal.symbol}</p>
                        <p className="text-sm text-gray-500">{signal.strategy_name}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">{formatCurrency(signal.entry_price)}</p>
                      <Badge variant={signal.status === 'pending' ? 'warning' : signal.status === 'executed' ? 'success' : 'secondary'}>
                        {signal.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">No recent signals</p>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
