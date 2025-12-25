'use client';

import { useMemo } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useMode } from '@/providers/ModeProvider';
import { useRiskState } from '@/hooks/useRisk';
import { useSignals } from '@/hooks/useStrategies';
import { useOrders } from '@/hooks/useExecution';
import { usePerformanceSnapshots } from '@/hooks/useJournal';
import { formatCurrency, formatPercent, formatShortDate, getValueColor } from '@/lib/utils';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  AlertTriangle,
  Zap,
  Shield,
  CheckCircle,
  XCircle,
  Clock,
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

interface OrderItem {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  status: string;
  average_fill_price: number | null;
  created_at?: string;
}

interface PerformanceItem {
  id: number;
  strategy_name: string;
  total_pnl: number;
  snapshot_time: string;
}

export default function Dashboard() {
  const { mode } = useMode();
  const { data: riskState, isLoading: riskLoading } = useRiskState();
  const { data: signals, isLoading: signalsLoading } = useSignals({ limit: 5 });
  const { data: orders, isLoading: ordersLoading } = useOrders({ limit: 5 });
  const { data: snapshots, isLoading: snapshotsLoading } = usePerformanceSnapshots({ limit: 30 });

  // Prepare equity curve data from performance snapshots
  const equityData = useMemo(() => {
    if (!snapshots || snapshots.length === 0) {
      // Default demo data if no snapshots yet
      return [
        { date: 'Day 1', equity: 100000 },
        { date: 'Day 2', equity: 100500 },
        { date: 'Day 3', equity: 101200 },
        { date: 'Day 4', equity: 100800 },
        { date: 'Day 5', equity: 102500 },
      ];
    }
    return snapshots
      .slice()
      .reverse()
      .map((s: PerformanceItem) => ({
        date: formatShortDate(s.snapshot_time),
        equity: 100000 + s.total_pnl, // Base equity + cumulative P&L
      }));
  }, [snapshots]);

  const statusIcon = (status: string) => {
    switch (status) {
      case 'filled':
      case 'executed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'cancelled':
      case 'rejected':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-yellow-500" />;
    }
  };

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

        {/* Equity Curve Chart */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Equity Curve</CardTitle>
          </CardHeader>
          <CardContent>
            {snapshotsLoading ? (
              <div className="h-64 flex items-center justify-center">
                <span className="animate-pulse">Loading chart...</span>
              </div>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={equityData}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="date" fontSize={12} tickLine={false} />
                    <YAxis
                      fontSize={12}
                      tickLine={false}
                      tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      formatter={(value: number) => [formatCurrency(value), 'Equity']}
                      labelStyle={{ color: '#374151' }}
                      contentStyle={{
                        backgroundColor: 'white',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="equity"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Two-column layout for signals and orders */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

        {/* Recent Orders */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Orders</CardTitle>
          </CardHeader>
          <CardContent>
            {ordersLoading ? (
              <div className="animate-pulse space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 bg-gray-100 dark:bg-gray-800 rounded" />
                ))}
              </div>
            ) : orders?.length > 0 ? (
              <div className="space-y-3">
                {orders.map((order: OrderItem) => (
                  <div
                    key={order.id}
                    className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      {statusIcon(order.status)}
                      <Badge variant={order.side === 'buy' ? 'success' : 'destructive'}>
                        {order.side.toUpperCase()}
                      </Badge>
                      <div>
                        <p className="font-medium">{order.symbol}</p>
                        <p className="text-sm text-gray-500">Qty: {order.quantity}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      {order.average_fill_price ? (
                        <p className="font-medium">{formatCurrency(order.average_fill_price)}</p>
                      ) : (
                        <p className="text-gray-500">-</p>
                      )}
                      <Badge variant="secondary">{order.status}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">No recent orders</p>
            )}
          </CardContent>
        </Card>
        </div>
      </PageContainer>
    </>
  );
}
