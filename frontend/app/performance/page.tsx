'use client';

import { useMemo } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { usePerformanceSnapshots, useJournalStats } from '@/hooks/useJournal';
import { useRiskState } from '@/hooks/useRisk';
import { PerformanceSnapshot } from '@/types';
import { formatCurrency, formatPercent, formatShortDate, getValueColor, snakeToTitle } from '@/lib/utils';

interface DailyPnlDataItem {
  date: string;
  pnl: number;
}

interface StrategyDataItem {
  name: string;
  pnl: number;
  trades: number;
  winRate: number;
}
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Target,
  BarChart3,
  Activity,
  RefreshCw,
  Calendar,
} from 'lucide-react';

export default function PerformancePage() {
  const { data: snapshots, isLoading: snapshotsLoading, refetch } = usePerformanceSnapshots({ limit: 50 });
  const { data: journalStats, isLoading: statsLoading } = useJournalStats();
  const { data: riskState } = useRiskState();

  // Aggregate performance data by date
  const equityData = useMemo(() => {
    if (!snapshots || snapshots.length === 0) {
      // Demo data
      return Array.from({ length: 30 }, (_, i) => ({
        date: `Day ${i + 1}`,
        equity: 100000 + Math.random() * 5000 * (i / 10),
        pnl: (Math.random() - 0.3) * 500,
      }));
    }

    let cumulativePnl = 0;
    return snapshots
      .slice()
      .reverse()
      .map((s: PerformanceSnapshot) => {
        cumulativePnl += s.total_pnl;
        return {
          date: formatShortDate(s.snapshot_time),
          equity: 100000 + cumulativePnl,
          pnl: s.total_pnl,
          winRate: s.win_rate * 100,
          profitFactor: s.profit_factor,
        };
      });
  }, [snapshots]);

  // Strategy comparison data
  const strategyData = useMemo((): StrategyDataItem[] => {
    if (!snapshots || snapshots.length === 0) return [];

    // Group by strategy
    type StrategyAccumulator = { pnl: number; trades: number; wins: number };
    const byStrategy = snapshots.reduce((acc: Record<string, StrategyAccumulator>, s: PerformanceSnapshot) => {
      if (!acc[s.strategy_name]) {
        acc[s.strategy_name] = { pnl: 0, trades: 0, wins: 0 };
      }
      acc[s.strategy_name].pnl += s.total_pnl;
      acc[s.strategy_name].trades += s.total_trades;
      acc[s.strategy_name].wins += Math.round(s.total_trades * s.win_rate);
      return acc;
    }, {});

    return (Object.entries(byStrategy) as [string, StrategyAccumulator][]).map(([name, data]) => ({
      name: snakeToTitle(name),
      pnl: data.pnl,
      trades: data.trades,
      winRate: data.trades > 0 ? (data.wins / data.trades) * 100 : 0,
    }));
  }, [snapshots]);

  // Daily P&L distribution
  const dailyPnlData = useMemo((): DailyPnlDataItem[] => {
    if (!snapshots || snapshots.length === 0) return [];
    return snapshots.slice(0, 20).map((s: PerformanceSnapshot) => ({
      date: formatShortDate(s.snapshot_time),
      pnl: s.total_pnl,
    }));
  }, [snapshots]);

  // Overall stats
  const overallStats = useMemo(() => {
    if (!journalStats) {
      return {
        totalPnl: 0,
        totalTrades: 0,
        winRate: 0,
        profitFactor: 0,
        avgWin: 0,
        avgLoss: 0,
      };
    }
    return {
      totalPnl: journalStats.total_pnl || 0,
      totalTrades: journalStats.total_trades || 0,
      winRate: journalStats.win_rate || 0,
      profitFactor: journalStats.profit_factor || 0,
      avgWin: journalStats.avg_win || 0,
      avgLoss: journalStats.avg_loss || 0,
    };
  }, [journalStats]);

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Performance"
        description="Track trading performance and analytics"
      >
        {/* Key Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="h-4 w-4 text-gray-500" />
              </div>
              <div className={`text-2xl font-bold ${getValueColor(overallStats.totalPnl)}`}>
                {formatCurrency(overallStats.totalPnl)}
              </div>
              <p className="text-sm text-gray-500">Total P&L</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <Activity className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold">{overallStats.totalTrades}</div>
              <p className="text-sm text-gray-500">Total Trades</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <Target className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold">{formatPercent(overallStats.winRate)}</div>
              <p className="text-sm text-gray-500">Win Rate</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <BarChart3 className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold">{overallStats.profitFactor.toFixed(2)}</div>
              <p className="text-sm text-gray-500">Profit Factor</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className={`text-2xl font-bold text-green-600`}>
                {formatCurrency(overallStats.avgWin)}
              </div>
              <p className="text-sm text-gray-500">Avg Win</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className={`text-2xl font-bold text-red-600`}>
                {formatCurrency(overallStats.avgLoss)}
              </div>
              <p className="text-sm text-gray-500">Avg Loss</p>
            </CardContent>
          </Card>
        </div>

        {/* Equity Curve */}
        <Card className="mb-8">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Equity Curve</CardTitle>
              <CardDescription>Account value over time</CardDescription>
            </div>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </CardHeader>
          <CardContent>
            {snapshotsLoading ? (
              <div className="h-80 flex items-center justify-center">
                <span className="animate-pulse">Loading chart...</span>
              </div>
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equityData}>
                    <defs>
                      <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="date" fontSize={12} tickLine={false} />
                    <YAxis
                      fontSize={12}
                      tickLine={false}
                      tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      formatter={(value: number) => [formatCurrency(value), 'Equity']}
                    />
                    <Area
                      type="monotone"
                      dataKey="equity"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      fill="url(#equityGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Daily P&L */}
          <Card>
            <CardHeader>
              <CardTitle>Daily P&L</CardTitle>
              <CardDescription>Daily profit and loss distribution</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyPnlData}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="date" fontSize={10} tickLine={false} />
                    <YAxis fontSize={12} tickLine={false} tickFormatter={(v) => `$${v}`} />
                    <Tooltip formatter={(value: number) => [formatCurrency(value), 'P&L']} />
                    <Bar dataKey="pnl">
                      {dailyPnlData.map((entry: DailyPnlDataItem, index: number) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Strategy Performance */}
          <Card>
            <CardHeader>
              <CardTitle>Strategy Comparison</CardTitle>
              <CardDescription>Performance by strategy</CardDescription>
            </CardHeader>
            <CardContent>
              {strategyData.length > 0 ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={strategyData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                      <XAxis type="number" fontSize={12} tickFormatter={(v) => `$${v}`} />
                      <YAxis dataKey="name" type="category" fontSize={12} width={100} />
                      <Tooltip formatter={(value: number) => [formatCurrency(value), 'P&L']} />
                      <Bar dataKey="pnl">
                        {strategyData.map((entry: StrategyDataItem, index: number) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-500">
                  No strategy data available
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Performance Snapshots Table */}
        <Card>
          <CardHeader>
            <CardTitle>Performance Snapshots</CardTitle>
            <CardDescription>Detailed performance records by strategy and symbol</CardDescription>
          </CardHeader>
          <CardContent>
            {snapshotsLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-12 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : snapshots && snapshots.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b dark:border-gray-700">
                      <th className="text-left py-3 px-4">Date</th>
                      <th className="text-left py-3 px-4">Strategy</th>
                      <th className="text-left py-3 px-4">Symbol</th>
                      <th className="text-right py-3 px-4">Trades</th>
                      <th className="text-right py-3 px-4">Win Rate</th>
                      <th className="text-right py-3 px-4">Profit Factor</th>
                      <th className="text-right py-3 px-4">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshots.slice(0, 20).map((snapshot: PerformanceSnapshot) => (
                      <tr
                        key={snapshot.id}
                        className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        <td className="py-3 px-4 text-gray-500">
                          <div className="flex items-center gap-2">
                            <Calendar className="h-4 w-4" />
                            {formatShortDate(snapshot.snapshot_time)}
                          </div>
                        </td>
                        <td className="py-3 px-4">{snakeToTitle(snapshot.strategy_name)}</td>
                        <td className="py-3 px-4">
                          <Badge variant="outline">{snapshot.symbol}</Badge>
                        </td>
                        <td className="py-3 px-4 text-right">{snapshot.total_trades}</td>
                        <td className="py-3 px-4 text-right">
                          {formatPercent(snapshot.win_rate * 100)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {snapshot.profit_factor.toFixed(2)}
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${getValueColor(snapshot.total_pnl)}`}>
                          {formatCurrency(snapshot.total_pnl)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12">
                <BarChart3 className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">No performance data yet</p>
                <p className="text-sm text-gray-400 mt-2">
                  Performance snapshots will appear after trades are recorded
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
