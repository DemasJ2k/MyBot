'use client';

import { useState, useMemo } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useStrategies } from '@/hooks/useStrategies';
import { useBacktestResults, useRunBacktest } from '@/hooks/useBacktest';
import { BacktestResult, Strategy } from '@/types';
import { formatCurrency, formatPercent, formatShortDate, getValueColor, snakeToTitle } from '@/lib/utils';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import {
  FlaskConical,
  Play,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Target,
  BarChart3,
} from 'lucide-react';

interface ComparisonDataItem {
  name: string;
  return: number;
  fullName: string;
}

interface EquityDataItem {
  point: number;
  equity: number;
}

export default function BacktestingPage() {
  const { data: strategies } = useStrategies();
  const { data: backtestResults, isLoading: resultsLoading, refetch } = useBacktestResults({ limit: 20 });
  const runBacktest = useRunBacktest();

  const [formData, setFormData] = useState({
    strategy_name: '',
    symbol: '',
    interval: '1d',
    start_date: '',
    end_date: '',
    initial_balance: 100000,
  });

  const [selectedBacktest, setSelectedBacktest] = useState<BacktestResult | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleRunBacktest = () => {
    if (!formData.strategy_name || !formData.symbol || !formData.start_date || !formData.end_date) {
      return;
    }
    runBacktest.mutate(formData);
  };

  // Chart data for selected backtest
  const performanceData = useMemo(() => {
    if (!selectedBacktest) return [];
    // Simulated equity curve based on backtest metrics
    const totalReturn = selectedBacktest.total_return_percent / 100;
    const points = 10;
    const data = [];
    const startBalance = selectedBacktest.initial_balance;
    const finalBalance = selectedBacktest.final_balance;
    
    for (let i = 0; i <= points; i++) {
      const progress = i / points;
      // Simulate some volatility in the equity curve
      const noise = Math.sin(i * 1.5) * 0.02 * startBalance;
      const equity = startBalance + (finalBalance - startBalance) * progress + noise;
      data.push({
        point: i + 1,
        equity: Math.round(equity),
      });
    }
    return data;
  }, [selectedBacktest]);

  // Summary metrics for comparison chart
  const comparisonData = useMemo(() => {
    if (!backtestResults || backtestResults.length === 0) return [];
    return backtestResults.slice(0, 10).map((bt: BacktestResult) => ({
      name: `${bt.strategy_name.slice(0, 8)}...`,
      return: bt.total_return_percent,
      fullName: `${snakeToTitle(bt.strategy_name)} - ${bt.symbol}`,
    }));
  }, [backtestResults]);

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Backtesting"
        description="Test strategies against historical data"
      >
        {/* Run Backtest Form */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FlaskConical className="h-5 w-5 text-purple-500" />
              Run New Backtest
            </CardTitle>
            <CardDescription>
              Configure and run a backtest against historical market data
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium mb-1">Strategy</label>
                <select
                  name="strategy_name"
                  value={formData.strategy_name}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select Strategy</option>
                  {strategies?.map((s: Strategy) => (
                    <option key={s.name} value={s.name}>
                      {snakeToTitle(s.name)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Symbol</label>
                <input
                  type="text"
                  name="symbol"
                  value={formData.symbol}
                  onChange={handleInputChange}
                  placeholder="e.g., AAPL"
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Interval</label>
                <select
                  name="interval"
                  value={formData.interval}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="1m">1 Minute</option>
                  <option value="5m">5 Minutes</option>
                  <option value="15m">15 Minutes</option>
                  <option value="1h">1 Hour</option>
                  <option value="1d">1 Day</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Start Date</label>
                <input
                  type="date"
                  name="start_date"
                  value={formData.start_date}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">End Date</label>
                <input
                  type="date"
                  name="end_date"
                  value={formData.end_date}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Initial Balance</label>
                <input
                  type="number"
                  name="initial_balance"
                  value={formData.initial_balance}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <Button
              onClick={handleRunBacktest}
              disabled={runBacktest.isPending || !formData.strategy_name || !formData.symbol}
            >
              {runBacktest.isPending ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Run Backtest
            </Button>
          </CardContent>
        </Card>

        {/* Results Comparison Chart */}
        {comparisonData.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Return Comparison</CardTitle>
              <CardDescription>Compare returns across recent backtest runs</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonData}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="name" fontSize={12} />
                    <YAxis fontSize={12} tickFormatter={(v) => `${v}%`} />
                    <Tooltip
                      formatter={(value: number) => [`${value.toFixed(2)}%`, 'Return']}
                      labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
                    />
                    <Bar dataKey="return">
                      {comparisonData.map((entry: ComparisonDataItem, index: number) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.return >= 0 ? '#22c55e' : '#ef4444'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Selected Backtest Details */}
        {selectedBacktest && (
          <Card className="mb-8">
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>
                    {snakeToTitle(selectedBacktest.strategy_name)} - {selectedBacktest.symbol}
                  </CardTitle>
                  <CardDescription>
                    {formatShortDate(selectedBacktest.start_date)} to {formatShortDate(selectedBacktest.end_date)}
                  </CardDescription>
                </div>
                <Button variant="outline" onClick={() => setSelectedBacktest(null)}>
                  Close
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingUp className="h-4 w-4 text-gray-500" />
                    <span className="text-sm text-gray-500">Total Return</span>
                  </div>
                  <p className={`text-xl font-bold ${getValueColor(selectedBacktest.total_return_percent)}`}>
                    {formatPercent(selectedBacktest.total_return_percent)}
                  </p>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <Target className="h-4 w-4 text-gray-500" />
                    <span className="text-sm text-gray-500">Win Rate</span>
                  </div>
                  <p className="text-xl font-bold">
                    {formatPercent(selectedBacktest.win_rate_percent)}
                  </p>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingDown className="h-4 w-4 text-gray-500" />
                    <span className="text-sm text-gray-500">Max Drawdown</span>
                  </div>
                  <p className={`text-xl font-bold ${getValueColor(-selectedBacktest.max_drawdown_percent)}`}>
                    {formatPercent(selectedBacktest.max_drawdown_percent)}
                  </p>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <BarChart3 className="h-4 w-4 text-gray-500" />
                    <span className="text-sm text-gray-500">Profit Factor</span>
                  </div>
                  <p className="text-xl font-bold">
                    {selectedBacktest.profit_factor?.toFixed(2) || 'N/A'}
                  </p>
                </div>
              </div>

              {/* Equity Curve */}
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={performanceData}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="point" fontSize={12} />
                    <YAxis fontSize={12} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip
                      formatter={(value: number) => [formatCurrency(value), 'Equity']}
                    />
                    <Line
                      type="monotone"
                      dataKey="equity"
                      stroke="#8b5cf6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Backtest Results Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Backtest History</CardTitle>
              <CardDescription>View and compare previous backtest runs</CardDescription>
            </div>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </CardHeader>
          <CardContent>
            {resultsLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : backtestResults && backtestResults.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b dark:border-gray-700">
                      <th className="text-left py-3 px-4">Strategy</th>
                      <th className="text-left py-3 px-4">Symbol</th>
                      <th className="text-left py-3 px-4">Period</th>
                      <th className="text-right py-3 px-4">Return</th>
                      <th className="text-right py-3 px-4">Win Rate</th>
                      <th className="text-right py-3 px-4">Trades</th>
                      <th className="text-right py-3 px-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backtestResults.map((bt: BacktestResult) => (
                      <tr
                        key={bt.id}
                        className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        <td className="py-3 px-4">{snakeToTitle(bt.strategy_name)}</td>
                        <td className="py-3 px-4">
                          <Badge variant="outline">{bt.symbol}</Badge>
                        </td>
                        <td className="py-3 px-4 text-gray-500">
                          {formatShortDate(bt.start_date)} - {formatShortDate(bt.end_date)}
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${getValueColor(bt.total_return_percent)}`}>
                          {formatPercent(bt.total_return_percent)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {formatPercent(bt.win_rate_percent)}
                        </td>
                        <td className="py-3 px-4 text-right">{bt.total_trades}</td>
                        <td className="py-3 px-4 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedBacktest(bt)}
                          >
                            View
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">
                No backtest results yet. Run your first backtest above.
              </p>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
