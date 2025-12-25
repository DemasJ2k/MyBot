'use client';

import { useState, useMemo } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useJournalEntries, useJournalStats } from '@/hooks/useJournal';
import { JournalEntry } from '@/types';
import { formatCurrency, formatPercent, formatDate, formatShortDate, getValueColor, snakeToTitle } from '@/lib/utils';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  BookOpen,
  RefreshCw,
  Filter,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

interface PnlDataItem {
  date: string;
  pnl: number;
  cumulative: number;
}

interface ChartDataItem {
  name: string;
  value: number;
  color: string;
}

export default function JournalPage() {
  const { data: entries, isLoading: entriesLoading, refetch } = useJournalEntries({ limit: 100 });
  const { data: stats } = useJournalStats();

  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);

  // Filter entries
  const filteredEntries = useMemo(() => {
    if (!entries) return [];
    if (sourceFilter === 'all') return entries;
    return entries.filter((e: JournalEntry) => e.source === sourceFilter);
  }, [entries, sourceFilter]);

  // Chart data - P&L over time
  const pnlOverTime = useMemo((): PnlDataItem[] => {
    if (!entries || entries.length === 0) return [];
    let cumulative = 0;
    return entries
      .slice()
      .reverse()
      .slice(0, 30)
      .map((e: JournalEntry) => {
        cumulative += e.pnl;
        return {
          date: formatShortDate(e.exit_time),
          pnl: e.pnl,
          cumulative,
        };
      });
  }, [entries]);

  // Win/Loss distribution
  const winLossData = useMemo((): ChartDataItem[] => {
    if (!stats) return [];
    const wins = stats.total_wins || 0;
    const losses = stats.total_losses || 0;
    return [
      { name: 'Wins', value: wins, color: '#22c55e' },
      { name: 'Losses', value: losses, color: '#ef4444' },
    ].filter(d => d.value > 0);
  }, [stats]);

  // Source distribution
  const sourceData = useMemo((): ChartDataItem[] => {
    if (!entries || entries.length === 0) return [];
    const counts = entries.reduce((acc: Record<string, number>, e: JournalEntry) => {
      acc[e.source] = (acc[e.source] || 0) + 1;
      return acc;
    }, {});
    const colors: Record<string, string> = {
      live: '#3b82f6',
      paper: '#22c55e',
      backtest: '#8b5cf6',
    };
    return (Object.entries(counts) as [string, number][]).map(([source, count]) => ({
      name: snakeToTitle(source),
      value: count,
      color: colors[source] || '#6b7280',
    }));
  }, [entries]);

  // Summary stats
  const summaryStats = useMemo(() => {
    return {
      totalTrades: stats?.total_trades || 0,
      winRate: stats?.win_rate || 0,
      totalPnl: stats?.total_pnl || 0,
      profitFactor: stats?.profit_factor || 0,
      avgWin: stats?.avg_win || 0,
      avgLoss: stats?.avg_loss || 0,
      largestWin: stats?.largest_win || 0,
      largestLoss: stats?.largest_loss || 0,
    };
  }, [stats]);

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Trading Journal"
        description="Review and analyze completed trades"
      >
        {/* Summary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 mb-8">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{summaryStats.totalTrades}</div>
              <p className="text-xs text-gray-500">Total Trades</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className={`text-2xl font-bold ${getValueColor(summaryStats.totalPnl)}`}>
                {formatCurrency(summaryStats.totalPnl)}
              </div>
              <p className="text-xs text-gray-500">Total P&L</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{formatPercent(summaryStats.winRate)}</div>
              <p className="text-xs text-gray-500">Win Rate</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{summaryStats.profitFactor.toFixed(2)}</div>
              <p className="text-xs text-gray-500">Profit Factor</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600">{formatCurrency(summaryStats.avgWin)}</div>
              <p className="text-xs text-gray-500">Avg Win</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-red-600">{formatCurrency(summaryStats.avgLoss)}</div>
              <p className="text-xs text-gray-500">Avg Loss</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600">{formatCurrency(summaryStats.largestWin)}</div>
              <p className="text-xs text-gray-500">Best Trade</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-red-600">{formatCurrency(summaryStats.largestLoss)}</div>
              <p className="text-xs text-gray-500">Worst Trade</p>
            </CardContent>
          </Card>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Cumulative P&L */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Cumulative P&L</CardTitle>
              <CardDescription>Running total profit and loss</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={pnlOverTime}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="date" fontSize={10} tickLine={false} />
                    <YAxis fontSize={12} tickLine={false} tickFormatter={(v) => `$${v}`} />
                    <Tooltip formatter={(value: number) => [formatCurrency(value), 'Cumulative']} />
                    <Line
                      type="monotone"
                      dataKey="cumulative"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Win/Loss Pie */}
          <Card>
            <CardHeader>
              <CardTitle>Win/Loss Ratio</CardTitle>
            </CardHeader>
            <CardContent>
              {winLossData.length > 0 ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={winLossData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={40}
                        outerRadius={70}
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {winLossData.map((entry: ChartDataItem, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-500">
                  No trade data
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Individual P&L Chart */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Individual Trade P&L</CardTitle>
            <CardDescription>Profit and loss for each trade</CardDescription>
          </CardHeader>
          <CardContent>
            {pnlOverTime.length > 0 ? (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={pnlOverTime}>
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis dataKey="date" fontSize={10} tickLine={false} />
                    <YAxis fontSize={12} tickLine={false} tickFormatter={(v) => `$${v}`} />
                    <Tooltip formatter={(value: number) => [formatCurrency(value), 'P&L']} />
                    <Bar dataKey="pnl">
                      {pnlOverTime.map((entry: PnlDataItem, index: number) => (
                        <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-gray-500">
                No trade data
              </div>
            )}
          </CardContent>
        </Card>

        {/* Trade Journal Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Trade History</CardTitle>
              <CardDescription>Detailed record of all completed trades</CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-gray-500" />
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-sm"
                >
                  <option value="all">All Sources</option>
                  <option value="live">Live</option>
                  <option value="paper">Paper</option>
                  <option value="backtest">Backtest</option>
                </select>
              </div>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {entriesLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : filteredEntries.length > 0 ? (
              <div className="space-y-2">
                {filteredEntries.slice(0, 50).map((entry: JournalEntry) => (
                  <div
                    key={entry.entry_id}
                    className="border dark:border-gray-700 rounded-lg overflow-hidden"
                  >
                    <div
                      className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                      onClick={() => setExpandedEntry(expandedEntry === entry.entry_id ? null : entry.entry_id)}
                    >
                      <div className="flex items-center gap-4">
                        {expandedEntry === entry.entry_id ? (
                          <ChevronDown className="h-4 w-4 text-gray-500" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-gray-500" />
                        )}
                        {entry.is_winner ? (
                          <CheckCircle className="h-5 w-5 text-green-500" />
                        ) : (
                          <XCircle className="h-5 w-5 text-red-500" />
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{entry.symbol}</span>
                            <Badge variant={entry.side === 'long' ? 'success' : 'destructive'}>
                              {entry.side.toUpperCase()}
                            </Badge>
                            <Badge variant="outline">{entry.source}</Badge>
                          </div>
                          <p className="text-sm text-gray-500">
                            {snakeToTitle(entry.strategy_name)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <div className={`font-bold ${getValueColor(entry.pnl)}`}>
                            {formatCurrency(entry.pnl)}
                          </div>
                          <div className={`text-sm ${getValueColor(entry.pnl_percent)}`}>
                            {formatPercent(entry.pnl_percent)}
                          </div>
                        </div>
                        <div className="text-right text-sm text-gray-500">
                          <div>{formatShortDate(entry.exit_time)}</div>
                        </div>
                      </div>
                    </div>

                    {expandedEntry === entry.entry_id && (
                      <div className="p-4 bg-gray-50 dark:bg-gray-800 border-t dark:border-gray-700">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div>
                            <p className="text-xs text-gray-500 uppercase">Entry Price</p>
                            <p className="font-medium">{formatCurrency(entry.entry_price)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500 uppercase">Exit Price</p>
                            <p className="font-medium">{formatCurrency(entry.exit_price)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500 uppercase">Entry Time</p>
                            <p className="font-medium text-sm">{formatDate(entry.entry_time)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500 uppercase">Exit Time</p>
                            <p className="font-medium text-sm">{formatDate(entry.exit_time)}</p>
                          </div>
                          <div className="col-span-2">
                            <p className="text-xs text-gray-500 uppercase">Exit Reason</p>
                            <p className="font-medium">{snakeToTitle(entry.exit_reason)}</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <BookOpen className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">No journal entries yet</p>
                <p className="text-sm text-gray-400 mt-2">
                  Trades will be recorded here after they are completed
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
