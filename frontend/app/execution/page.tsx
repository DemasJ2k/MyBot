'use client';

import { useState, useMemo } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useMode } from '@/providers/ModeProvider';
import { useOrders, useCancelOrder, useBrokers } from '@/hooks/useExecution';
import { useRiskState } from '@/hooks/useRisk';
import { ExecutionOrder } from '@/types';
import { formatCurrency, snakeToTitle } from '@/lib/utils';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import {
  Shield,
  Zap,
  RefreshCw,
  X,
  CheckCircle,
  Clock,
  AlertTriangle,
  XCircle,
  TrendingUp,
  TrendingDown,
  Filter,
  Server,
} from 'lucide-react';

interface ExtendedOrder extends ExecutionOrder {
  created_at?: string;
  signal_id?: number;
}

interface ChartDataItem {
  name: string;
  value: number;
  color: string;
}

export default function ExecutionPage() {
  const { mode } = useMode();
  const { data: orders, isLoading: ordersLoading, refetch } = useOrders({ limit: 50 });
  const { data: riskState } = useRiskState();
  const { data: brokers, isLoading: brokersLoading } = useBrokers();
  const cancelOrder = useCancelOrder();

  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Filter orders
  const filteredOrders = useMemo(() => {
    if (!orders) return [];
    if (statusFilter === 'all') return orders;
    return orders.filter((o: ExtendedOrder) => o.status === statusFilter);
  }, [orders, statusFilter]);

  // Order stats
  const stats = useMemo(() => {
    if (!orders || orders.length === 0) return null;
    const pending = orders.filter((o: ExtendedOrder) => o.status === 'pending' || o.status === 'submitted').length;
    const filled = orders.filter((o: ExtendedOrder) => o.status === 'filled').length;
    const cancelled = orders.filter((o: ExtendedOrder) => o.status === 'cancelled').length;
    const rejected = orders.filter((o: ExtendedOrder) => o.status === 'rejected').length;
    const buyOrders = orders.filter((o: ExtendedOrder) => o.side === 'buy').length;
    const sellOrders = orders.filter((o: ExtendedOrder) => o.side === 'sell').length;
    return { pending, filled, cancelled, rejected, buyOrders, sellOrders, total: orders.length };
  }, [orders]);

  // Chart data
  const statusChartData = useMemo((): ChartDataItem[] => {
    if (!stats) return [];
    return [
      { name: 'Filled', value: stats.filled, color: '#22c55e' },
      { name: 'Pending', value: stats.pending, color: '#eab308' },
      { name: 'Cancelled', value: stats.cancelled, color: '#6b7280' },
      { name: 'Rejected', value: stats.rejected, color: '#ef4444' },
    ].filter(d => d.value > 0);
  }, [stats]);

  const handleCancelOrder = (orderId: number) => {
    cancelOrder.mutate(orderId);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'filled':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'pending':
      case 'submitted':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'cancelled':
        return <XCircle className="h-4 w-4 text-gray-500" />;
      case 'rejected':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'filled':
        return <Badge variant="success">Filled</Badge>;
      case 'pending':
      case 'submitted':
        return <Badge variant="warning">Pending</Badge>;
      case 'cancelled':
        return <Badge variant="secondary">Cancelled</Badge>;
      case 'rejected':
        return <Badge variant="destructive">Rejected</Badge>;
      case 'partial':
        return <Badge variant="warning">Partial</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Execution"
        description="Monitor and manage order execution"
      >
        {/* Mode & Risk Status */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Mode Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {mode === 'guide' ? (
                  <Shield className="h-5 w-5 text-blue-500" />
                ) : (
                  <Zap className="h-5 w-5 text-green-500" />
                )}
                Execution Mode
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`p-4 rounded-lg ${
                mode === 'guide'
                  ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                  : 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
              }`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className={`text-lg font-bold ${
                      mode === 'guide' ? 'text-blue-700 dark:text-blue-400' : 'text-green-700 dark:text-green-400'
                    }`}>
                      {mode === 'guide' ? 'GUIDE MODE' : 'AUTONOMOUS MODE'}
                    </p>
                    <p className={`text-sm ${
                      mode === 'guide' ? 'text-blue-600 dark:text-blue-300' : 'text-green-600 dark:text-green-300'
                    }`}>
                      {mode === 'guide'
                        ? 'Manual approval required for all trades'
                        : 'Automatic execution enabled'
                      }
                    </p>
                  </div>
                  <Badge variant={mode === 'guide' ? 'default' : 'success'} className="text-lg px-4 py-1">
                    {mode?.toUpperCase()}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Risk Status */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
                Risk Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Daily Loss</p>
                  <p className={`text-lg font-bold ${
                    (riskState?.daily_loss_percent || 0) > 2 ? 'text-red-600' : 'text-gray-900 dark:text-white'
                  }`}>
                    {(riskState?.daily_loss_percent || 0).toFixed(2)}%
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Open Positions</p>
                  <p className="text-lg font-bold">{riskState?.open_positions_count || 0}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Trades Today</p>
                  <p className="text-lg font-bold">{riskState?.trades_today || 0}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  {riskState?.emergency_shutdown_active ? (
                    <Badge variant="destructive">SHUTDOWN</Badge>
                  ) : riskState?.throttling_active ? (
                    <Badge variant="warning">THROTTLED</Badge>
                  ) : (
                    <Badge variant="success">NORMAL</Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Stats & Chart Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Order Stats */}
          <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{stats?.total || 0}</div>
                <p className="text-sm text-gray-500">Total Orders</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold text-green-600">{stats?.filled || 0}</div>
                <p className="text-sm text-gray-500">Filled</p>
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
                <div className="flex gap-4">
                  <div>
                    <div className="text-xl font-bold text-green-600">{stats?.buyOrders || 0}</div>
                    <p className="text-xs text-gray-500">Buy</p>
                  </div>
                  <div>
                    <div className="text-xl font-bold text-red-600">{stats?.sellOrders || 0}</div>
                    <p className="text-xs text-gray-500">Sell</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Status Chart */}
          {statusChartData.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Order Status</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statusChartData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={25}
                        outerRadius={45}
                      >
                        {statusChartData.map((entry: ChartDataItem, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Brokers */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-gray-500" />
              Connected Brokers
            </CardTitle>
          </CardHeader>
          <CardContent>
            {brokersLoading ? (
              <div className="animate-pulse flex gap-4">
                {[1, 2].map((i) => (
                  <div key={i} className="h-16 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : brokers && brokers.length > 0 ? (
              <div className="flex flex-wrap gap-4">
                {brokers.map((broker: { name: string; type: string; is_connected: boolean }, idx: number) => (
                  <div
                    key={idx}
                    className={`p-4 rounded-lg border ${
                      broker.is_connected
                        ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                        : 'border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`h-2 w-2 rounded-full ${
                        broker.is_connected ? 'bg-green-500' : 'bg-gray-400'
                      }`} />
                      <div>
                        <p className="font-medium">{snakeToTitle(broker.name)}</p>
                        <p className="text-sm text-gray-500">{broker.type}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500">No brokers configured. Paper trading is always available.</p>
            )}
          </CardContent>
        </Card>

        {/* Orders Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Order History</CardTitle>
              <CardDescription>View and manage submitted orders</CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-gray-500" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-sm"
                >
                  <option value="all">All Status</option>
                  <option value="filled">Filled</option>
                  <option value="pending">Pending</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {ordersLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : filteredOrders.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b dark:border-gray-700">
                      <th className="text-left py-3 px-4">Order ID</th>
                      <th className="text-left py-3 px-4">Symbol</th>
                      <th className="text-left py-3 px-4">Side</th>
                      <th className="text-right py-3 px-4">Quantity</th>
                      <th className="text-right py-3 px-4">Filled</th>
                      <th className="text-right py-3 px-4">Avg Price</th>
                      <th className="text-center py-3 px-4">Status</th>
                      <th className="text-right py-3 px-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOrders.map((order: ExtendedOrder) => (
                      <tr
                        key={order.id}
                        className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(order.status)}
                            <span className="font-mono text-xs">{order.client_order_id.slice(0, 8)}...</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-medium">{order.symbol}</td>
                        <td className="py-3 px-4">
                          <Badge variant={order.side === 'buy' ? 'success' : 'destructive'}>
                            {order.side === 'buy' ? (
                              <TrendingUp className="h-3 w-3 mr-1" />
                            ) : (
                              <TrendingDown className="h-3 w-3 mr-1" />
                            )}
                            {order.side.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-right">{order.quantity}</td>
                        <td className="py-3 px-4 text-right">{order.filled_quantity}</td>
                        <td className="py-3 px-4 text-right">
                          {order.average_fill_price ? formatCurrency(order.average_fill_price) : '-'}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {getStatusBadge(order.status)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {(order.status === 'pending' || order.status === 'submitted') && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleCancelOrder(order.id)}
                              disabled={cancelOrder.isPending}
                            >
                              <X className="h-3 w-3 mr-1" />
                              Cancel
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12">
                <Shield className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">No orders found</p>
                <p className="text-sm text-gray-400 mt-2">
                  Orders will appear here when signals are executed
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
