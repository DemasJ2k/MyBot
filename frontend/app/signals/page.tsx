'use client';

import { useState, useMemo } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useMode } from '@/providers/ModeProvider';
import { useSignals, useCancelSignal } from '@/hooks/useStrategies';
import { useExecuteSignal } from '@/hooks/useExecution';
import { Signal } from '@/types';
import { formatCurrency, formatPercent, formatDate, getValueColor, snakeToTitle } from '@/lib/utils';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from 'recharts';
import {
  Zap,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Play,
  X,
  AlertTriangle,
  Filter,
} from 'lucide-react';

interface ChartDataItem {
  name: string;
  value: number;
  color: string;
}

export default function SignalsPage() {
  const { mode } = useMode();
  const { data: signals, isLoading, refetch } = useSignals({ limit: 50 });
  const executeSignal = useExecuteSignal();
  const cancelSignal = useCancelSignal();

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [positionSize, setPositionSize] = useState<number>(1000);

  // Filter signals based on status
  const filteredSignals = useMemo(() => {
    if (!signals) return [];
    if (statusFilter === 'all') return signals;
    return signals.filter((s: Signal) => s.status === statusFilter);
  }, [signals, statusFilter]);

  // Summary stats
  const stats = useMemo(() => {
    if (!signals || signals.length === 0) return null;
    const pending = signals.filter((s: Signal) => s.status === 'pending').length;
    const executed = signals.filter((s: Signal) => s.status === 'executed').length;
    const cancelled = signals.filter((s: Signal) => s.status === 'cancelled').length;
    const long = signals.filter((s: Signal) => s.signal_type === 'long').length;
    const short = signals.filter((s: Signal) => s.signal_type === 'short').length;
    const avgConfidence = signals.reduce((sum: number, s: Signal) => sum + s.confidence, 0) / signals.length;
    return { pending, executed, cancelled, long, short, avgConfidence, total: signals.length };
  }, [signals]);

  // Chart data for signal types
  const typeData = useMemo((): ChartDataItem[] => {
    if (!stats) return [];
    return [
      { name: 'Long', value: stats.long, color: '#22c55e' },
      { name: 'Short', value: stats.short, color: '#ef4444' },
    ];
  }, [stats]);

  // Chart data for status
  const statusData = useMemo((): ChartDataItem[] => {
    if (!stats) return [];
    return [
      { name: 'Pending', value: stats.pending, color: '#eab308' },
      { name: 'Executed', value: stats.executed, color: '#22c55e' },
      { name: 'Cancelled', value: stats.cancelled, color: '#6b7280' },
    ].filter(d => d.value > 0);
  }, [stats]);

  const handleExecute = (signalId: number) => {
    executeSignal.mutate({
      signalId,
      positionSize,
      brokerType: 'paper',
    });
  };

  const handleCancel = (signalId: number) => {
    cancelSignal.mutate(signalId);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge variant="warning">Pending</Badge>;
      case 'executed':
        return <Badge variant="success">Executed</Badge>;
      case 'cancelled':
        return <Badge variant="secondary">Cancelled</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Signals"
        description="View and manage trading signals"
      >
        {/* Mode Warning */}
        {mode === 'autonomous' && (
          <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-yellow-600" />
            <div>
              <p className="font-medium text-yellow-900 dark:text-yellow-100">
                Autonomous Mode Active
              </p>
              <p className="text-sm text-yellow-700 dark:text-yellow-300">
                Signals are being automatically executed. Switch to Guide mode for manual control.
              </p>
            </div>
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-blue-600">{stats?.total || 0}</div>
              <p className="text-sm text-gray-500">Total Signals</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-yellow-600">{stats?.pending || 0}</div>
              <p className="text-sm text-gray-500">Pending</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600">{stats?.executed || 0}</div>
              <p className="text-sm text-gray-500">Executed</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600">{stats?.long || 0}</div>
              <p className="text-sm text-gray-500">Long Signals</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-red-600">{stats?.short || 0}</div>
              <p className="text-sm text-gray-500">Short Signals</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{formatPercent(stats?.avgConfidence || 0)}</div>
              <p className="text-sm text-gray-500">Avg Confidence</p>
            </CardContent>
          </Card>
        </div>

        {/* Charts Row */}
        {stats && stats.total > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <Card>
              <CardHeader>
                <CardTitle>Signal Types</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={typeData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={60}
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {typeData.map((entry: ChartDataItem, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Signal Status</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={statusData}>
                      <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                      <XAxis dataKey="name" fontSize={12} />
                      <YAxis fontSize={12} />
                      <Tooltip />
                      <Bar dataKey="value">
                        {statusData.map((entry: ChartDataItem, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Signals Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Signal List</CardTitle>
              <CardDescription>Real-time trading signals from all strategies</CardDescription>
            </div>
            <div className="flex items-center gap-4">
              {/* Position Size for Execution */}
              {mode === 'guide' && (
                <div className="flex items-center gap-2">
                  <label className="text-sm text-gray-500">Position Size:</label>
                  <input
                    type="number"
                    value={positionSize}
                    onChange={(e) => setPositionSize(Number(e.target.value))}
                    className="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-sm"
                  />
                </div>
              )}
              {/* Filter */}
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-gray-500" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-sm"
                >
                  <option value="all">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="executed">Executed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : filteredSignals.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b dark:border-gray-700">
                      <th className="text-left py-3 px-4">Time</th>
                      <th className="text-left py-3 px-4">Strategy</th>
                      <th className="text-left py-3 px-4">Symbol</th>
                      <th className="text-left py-3 px-4">Type</th>
                      <th className="text-right py-3 px-4">Entry</th>
                      <th className="text-right py-3 px-4">SL</th>
                      <th className="text-right py-3 px-4">TP</th>
                      <th className="text-right py-3 px-4">R:R</th>
                      <th className="text-right py-3 px-4">Confidence</th>
                      <th className="text-center py-3 px-4">Status</th>
                      {mode === 'guide' && <th className="text-right py-3 px-4">Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSignals.map((signal: Signal) => (
                      <tr
                        key={signal.id}
                        className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        <td className="py-3 px-4 text-gray-500">
                          {formatDate(signal.signal_time)}
                        </td>
                        <td className="py-3 px-4">
                          {snakeToTitle(signal.strategy_name)}
                        </td>
                        <td className="py-3 px-4 font-medium">{signal.symbol}</td>
                        <td className="py-3 px-4">
                          <Badge variant={signal.signal_type === 'long' ? 'success' : 'destructive'}>
                            {signal.signal_type === 'long' ? (
                              <TrendingUp className="h-3 w-3 mr-1" />
                            ) : (
                              <TrendingDown className="h-3 w-3 mr-1" />
                            )}
                            {signal.signal_type.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-right font-medium">
                          {formatCurrency(signal.entry_price)}
                        </td>
                        <td className="py-3 px-4 text-right text-red-600">
                          {formatCurrency(signal.stop_loss)}
                        </td>
                        <td className="py-3 px-4 text-right text-green-600">
                          {formatCurrency(signal.take_profit)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {signal.risk_reward_ratio.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className={getValueColor(signal.confidence - 50)}>
                            {formatPercent(signal.confidence)}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          {getStatusBadge(signal.status)}
                        </td>
                        {mode === 'guide' && (
                          <td className="py-3 px-4 text-right">
                            {signal.status === 'pending' && (
                              <div className="flex justify-end gap-2">
                                <Button
                                  size="sm"
                                  variant="default"
                                  onClick={() => handleExecute(signal.id)}
                                  disabled={executeSignal.isPending}
                                >
                                  <Play className="h-3 w-3 mr-1" />
                                  Execute
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleCancel(signal.id)}
                                  disabled={cancelSignal.isPending}
                                >
                                  <X className="h-3 w-3" />
                                </Button>
                              </div>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12">
                <Zap className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">No signals found</p>
                <p className="text-sm text-gray-400 mt-2">
                  Signals will appear here when strategies generate them
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
