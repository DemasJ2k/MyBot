# 13_UI_DASHBOARDS.md

## Context for Claude Opus 4.5

You are implementing the 10 core dashboard pages for the Flowrex trading platform frontend. Each dashboard must be production-ready with complete functionality, real-time data fetching, interactive charts, and mode-aware behavior.

**Prerequisites:**
- `12_FRONTEND_CORE.md` has been completed
- TypeScript types exist in `types/index.ts`
- API client exists in `services/api.ts`
- React Query and Mode providers are configured
- UI components (Button, Card, ModeIndicator) are available

**Critical Requirements:**
- NO placeholders, templates, or TODOs
- ALL charts use Recharts library with responsive design
- Mode awareness: UI behavior changes based on GUIDE vs AUTONOMOUS
- Clear visual distinction between live, paper, and backtest data
- Surface AI decisions, risk blocks, and execution errors prominently
- Real-time updates using React Query `refetchInterval`
- Accessibility: ARIA labels, keyboard navigation, color contrast
- Mobile-first responsive design
- Error states and empty states for all data

---

## Dashboard 1: Overview/Dashboard (Home)

### Purpose
Central command center showing system health, account status, equity performance, and recent activity at a glance.

### File Location
`app/page.tsx`

### Data Sources
- `GET /api/v1/config` - System configuration and mode (refetch every 5s)
- `GET /api/v1/risk/state` - Current risk state, balances, P&L (refetch every 3s)
- `GET /api/v1/signals?status=pending` - Pending signals (refetch every 5s)
- `GET /api/v1/execution/orders?status=open` - Active orders (refetch every 3s)
- `GET /api/v1/performance/snapshots?limit=100` - Equity curve data (refetch every 10s)
- `GET /api/v1/ai/decisions?limit=5` - Recent AI decisions (refetch every 10s)

### Visual Layout

**Header Section:**
- Page title "Dashboard" (left)
- `<ModeIndicator />` component (right)

**Emergency Alert (conditional):**
- Only visible if `riskState.emergency_shutdown === true`
- Red border-left alert with AlertTriangle icon
- Message: "EMERGENCY SHUTDOWN ACTIVE - System has halted all trading due to critical risk threshold breach"
- `role="alert"` for screen readers

**Summary Cards (4-column grid):**

1. **Account Balance Card**
   - Icon: Activity (blue)
   - Value: `riskState.account_balance` formatted as currency with 2 decimals
   - Static display (no actions)

2. **Total Equity Card**
   - Icon: TrendingUp (green if positive, red if negative)
   - Primary value: `riskState.total_equity` formatted as currency
   - Secondary value: Unrealized P&L (equity - balance) with +/- prefix and color coding
   - Static display

3. **Daily P&L Card**
   - Icon: CheckCircle (green) if positive, AlertTriangle (red) if negative
   - Primary value: `riskState.daily_pnl` with color coding
   - Secondary value: Percentage of account balance
   - Static display

4. **Open Positions Card**
   - Icon: Activity (purple)
   - Primary value: `riskState.open_positions` count
   - Secondary value: Count of pending signals
   - Static display

**Equity Curve Chart:**
- Full-width card
- Title: "Equity Curve"
- Chart type: AreaChart from Recharts
- X-axis: Timestamp (formatted as date)
- Y-axis: Equity value in dollars
- Data: Performance snapshots mapped to `{ timestamp, equity }`
- Gradient fill under line (blue theme)
- Responsive container height: 300px
- Tooltip shows full timestamp and formatted dollar value
- Empty state: "No performance data available" if no data

**Recent Activity (2-column grid):**

1. **Pending Signals Panel**
   - Card with title "Pending Signals"
   - List view showing up to 5 most recent pending signals
   - Each signal displays:
     - Symbol (bold) + Signal type badge (LONG=green, SHORT=red)
     - Strategy name (gray text)
     - Entry price, stop loss (small text)
   - Empty state: "No pending signals"

2. **Active Orders Panel**
   - Card with title "Active Orders"
   - List view showing up to 5 most recent open orders
   - Each order displays:
     - Symbol (bold) + Side badge (BUY=green, SELL=red)
     - Quantity and entry price
     - Current unrealized P&L with color coding
   - Empty state: "No active orders"

**Recent AI Decisions Table:**
- Full-width card
- Title: "Recent AI Decisions"
- Table columns: Time | Agent | Decision | Reasoning
- Shows up to 5 most recent decisions
- Time formatted as HH:MM:SS
- Decision type in monospace code block
- Reasoning truncated with ellipsis if too long
- Empty state: "No recent AI decisions"

### Implementation Code

```typescript
'use client';

import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { ModeIndicator } from '@/components/ui/ModeIndicator';
import { apiClient } from '@/services/api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';

export default function DashboardPage() {
  const { data: systemConfig } = useQuery({
    queryKey: ['systemConfig'],
    queryFn: () => apiClient.getSystemConfig(),
    refetchInterval: 5000,
  });

  const { data: riskState } = useQuery({
    queryKey: ['riskState'],
    queryFn: () => apiClient.getCurrentRiskState(),
    refetchInterval: 3000,
  });

  const { data: signals } = useQuery({
    queryKey: ['signals', 'pending'],
    queryFn: () => apiClient.listSignals({ status: 'pending' }),
    refetchInterval: 5000,
  });

  const { data: orders } = useQuery({
    queryKey: ['orders', 'active'],
    queryFn: () => apiClient.listOrders({ status: 'open' }),
    refetchInterval: 3000,
  });

  const { data: performanceData } = useQuery({
    queryKey: ['performance', 'equity'],
    queryFn: async () => {
      const snapshots = await apiClient.getPerformanceSnapshots({ limit: 100 });
      return snapshots.map(s => ({
        timestamp: new Date(s.snapshot_time).getTime(),
        equity: s.total_equity,
      }));
    },
    refetchInterval: 10000,
  });

  const { data: aiDecisions } = useQuery({
    queryKey: ['aiDecisions', 'recent'],
    queryFn: () => apiClient.getAIDecisions({ limit: 5 }),
    refetchInterval: 10000,
  });

  const accountBalance = riskState?.account_balance || 0;
  const totalEquity = riskState?.total_equity || 0;
  const unrealizedPnl = totalEquity - accountBalance;
  const dailyPnl = riskState?.daily_pnl || 0;
  const openPositions = riskState?.open_positions || 0;
  const emergencyShutdown = riskState?.emergency_shutdown || false;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <ModeIndicator />
      </div>

      {/* Emergency Shutdown Alert */}
      {emergencyShutdown && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded" role="alert">
          <div className="flex items-center">
            <AlertTriangle className="h-5 w-5 mr-2" />
            <p className="font-bold">EMERGENCY SHUTDOWN ACTIVE</p>
          </div>
          <p className="text-sm mt-1">System has halted all trading due to critical risk threshold breach.</p>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Account Balance</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                ${accountBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <Activity className="h-8 w-8 text-blue-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Equity</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                ${totalEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              <p className={`text-sm ${unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {unrealizedPnl >= 0 ? '+' : ''}${unrealizedPnl.toFixed(2)} unrealized
              </p>
            </div>
            <TrendingUp className={`h-8 w-8 ${unrealizedPnl >= 0 ? 'text-green-500' : 'text-red-500'}`} />
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Daily P&L</p>
              <p className={`text-2xl font-bold ${dailyPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {dailyPnl >= 0 ? '+' : ''}${dailyPnl.toFixed(2)}
              </p>
              <p className="text-sm text-gray-500">
                {((dailyPnl / accountBalance) * 100).toFixed(2)}% of balance
              </p>
            </div>
            {dailyPnl >= 0 ? (
              <CheckCircle className="h-8 w-8 text-green-500" />
            ) : (
              <AlertTriangle className="h-8 w-8 text-red-500" />
            )}
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Open Positions</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{openPositions}</p>
              <p className="text-sm text-gray-500">{signals?.length || 0} pending signals</p>
            </div>
            <Activity className="h-8 w-8 text-purple-500" />
          </div>
        </Card>
      </div>

      {/* Equity Curve */}
      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Equity Curve</h2>
        {performanceData && performanceData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={performanceData}>
              <defs>
                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(ts) => new Date(ts).toLocaleDateString()}
                stroke="#9ca3af"
              />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                labelFormatter={(ts) => new Date(ts).toLocaleString()}
                formatter={(value: number) => [`$${value.toFixed(2)}`, 'Equity']}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke="#3b82f6"
                fill="url(#colorEquity)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-center py-12">No performance data available</p>
        )}
      </Card>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Signals */}
        <Card>
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Pending Signals</h2>
          {signals && signals.length > 0 ? (
            <div className="space-y-3">
              {signals.slice(0, 5).map((signal) => (
                <div key={signal.id} className="border-l-4 border-blue-500 pl-3 py-2 bg-gray-50 dark:bg-gray-800 rounded">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-gray-900 dark:text-white">{signal.symbol}</p>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      signal.signal_type === 'long' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {signal.signal_type.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{signal.strategy_name}</p>
                  <p className="text-sm text-gray-500">Entry: ${signal.entry_price.toFixed(2)} | SL: ${signal.stop_loss.toFixed(2)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No pending signals</p>
          )}
        </Card>

        {/* Active Orders */}
        <Card>
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Active Orders</h2>
          {orders && orders.length > 0 ? (
            <div className="space-y-3">
              {orders.slice(0, 5).map((order) => (
                <div key={order.id} className="border-l-4 border-green-500 pl-3 py-2 bg-gray-50 dark:bg-gray-800 rounded">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-gray-900 dark:text-white">{order.symbol}</p>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      order.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {order.side.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Qty: {order.quantity} @ ${order.entry_price?.toFixed(2) || 'N/A'}</p>
                  <p className="text-sm text-gray-500">
                    P&L: <span className={order.unrealized_pnl && order.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}>
                      ${order.unrealized_pnl?.toFixed(2) || '0.00'}
                    </span>
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No active orders</p>
          )}
        </Card>
      </div>

      {/* Recent AI Decisions */}
      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Recent AI Decisions</h2>
        {aiDecisions && aiDecisions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100 dark:bg-gray-800">
                <tr>
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Time</th>
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Agent</th>
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Decision</th>
                  <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Reasoning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {aiDecisions.map((decision) => (
                  <tr key={decision.id}>
                    <td className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400">
                      {new Date(decision.decision_time).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">{decision.agent_name}</td>
                    <td className="px-4 py-2 text-sm">
                      <code className="bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded text-xs">
                        {decision.decision_type}
                      </code>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 max-w-md truncate">
                      {decision.reasoning}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-center py-8">No recent AI decisions</p>
        )}
      </Card>
    </div>
  );
}
```

### Mode Behavior
- **GUIDE Mode:** Read-only display, no interactive actions
- **AUTONOMOUS Mode:** Read-only display, no interactive actions
- Mode only affects other pages with actionable buttons

### Error Handling
- All queries handle loading states with skeleton loaders or spinners
- Network errors display toast notifications
- Empty arrays show friendly empty state messages
- Invalid data falls back to default values (0, empty string, etc.)

---

## Dashboard 2: Strategies

### Purpose
View all registered trading strategies, their performance statistics, enable/disable them, and configure their parameters.

### File Location
`app/strategies/page.tsx`

### Data Sources
- `GET /api/v1/strategies` - List all strategies with performance stats (refetch every 10s)
- `GET /api/v1/config` - Current system mode via `useMode()` hook
- `PUT /api/v1/strategies/{id}` - Update strategy (enable/disable, update config)

### Visual Layout

**Header:**
- Title: "Strategies" (left)
- "Run Backtest" button (right) - navigates to `/backtesting`

**Strategy Grid (3-column responsive):**

Each strategy displays in a Card:

**Card Header:**
- Strategy name (bold, large)
- Description (gray, small)
- Status badge (top-right): "ACTIVE" (green) or "INACTIVE" (gray)

**Performance Stats (2x2 grid):**
- Win Rate: Percentage with 1 decimal
- Profit Factor: Decimal with 2 places
- Total Trades: Integer count
- Net P&L: Dollar amount with color coding (green if positive, red if negative)

**Action Buttons (2-button row):**
1. Enable/Disable Button:
   - Shows "Disable" (red, with Pause icon) if strategy.enabled === true
   - Shows "Enable" (blue, with Play icon) if strategy.enabled === false
   - **Disabled in GUIDE mode** with warning message below
   - Triggers mutation to update strategy.enabled

2. Configure Button:
   - Always enabled (gray, with Settings icon)
   - Opens modal showing current configuration JSON
   - Modal allows editing configuration (future enhancement)

**Mode Warning (conditional):**
- Only visible in GUIDE mode
- Amber text: "Switch to AUTONOMOUS mode to enable/disable strategies"

**Configuration Modal (when open):**
- Overlay with semi-transparent black background
- Centered card (max-width 2xl)
- Title: "Configure {strategy.name}"
- JSON editor showing `strategy.configuration`
- Two buttons: "Close" and "Save Changes"
- Scroll if content overflows

### Implementation Code

```typescript
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { Strategy } from '@/types';
import { useMode } from '@/providers/ModeProvider';
import { Play, Pause, Settings } from 'lucide-react';

export default function StrategiesPage() {
  const { mode } = useMode();
  const queryClient = useQueryClient();
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);

  const { data: strategies, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient.listStrategies(),
    refetchInterval: 10000,
  });

  const toggleStrategyMutation = useMutation({
    mutationFn: async ({ strategyId, enabled }: { strategyId: number; enabled: boolean }) => {
      return apiClient.updateStrategy(strategyId, { enabled });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const handleToggle = (strategy: Strategy) => {
    toggleStrategyMutation.mutate({
      strategyId: strategy.id,
      enabled: !strategy.enabled,
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">Loading strategies...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Strategies</h1>
        <Button variant="primary" onClick={() => window.location.href = '/backtesting'}>
          Run Backtest
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {strategies?.map((strategy) => (
          <Card key={strategy.id}>
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{strategy.name}</h3>
                  <p className="text-sm text-gray-500">{strategy.description}</p>
                </div>
                <div className={`px-2 py-1 rounded text-xs font-semibold ${
                  strategy.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {strategy.enabled ? 'ACTIVE' : 'INACTIVE'}
                </div>
              </div>

              {strategy.performance_stats && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded">
                    <p className="text-xs text-gray-500">Win Rate</p>
                    <p className="text-lg font-semibold text-gray-900 dark:text-white">
                      {(strategy.performance_stats.win_rate * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded">
                    <p className="text-xs text-gray-500">Profit Factor</p>
                    <p className="text-lg font-semibold text-gray-900 dark:text-white">
                      {strategy.performance_stats.profit_factor?.toFixed(2) || 'N/A'}
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded">
                    <p className="text-xs text-gray-500">Total Trades</p>
                    <p className="text-lg font-semibold text-gray-900 dark:text-white">
                      {strategy.performance_stats.total_trades}
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded">
                    <p className="text-xs text-gray-500">Net P&L</p>
                    <p className={`text-lg font-semibold ${
                      strategy.performance_stats.net_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      ${strategy.performance_stats.net_pnl.toFixed(2)}
                    </p>
                  </div>
                </div>
              )}

              <div className="flex space-x-2">
                <Button
                  variant={strategy.enabled ? 'danger' : 'primary'}
                  onClick={() => handleToggle(strategy)}
                  disabled={mode === 'guide'}
                  className="flex-1"
                >
                  {strategy.enabled ? (
                    <>
                      <Pause className="h-4 w-4 mr-2" />
                      Disable
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Enable
                    </>
                  )}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => setSelectedStrategy(strategy)}
                  className="flex-1"
                >
                  <Settings className="h-4 w-4 mr-2" />
                  Configure
                </Button>
              </div>

              {mode === 'guide' && (
                <p className="text-xs text-amber-600 dark:text-amber-500">
                  Switch to AUTONOMOUS mode to enable/disable strategies
                </p>
              )}
            </div>
          </Card>
        ))}
      </div>

      {selectedStrategy && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setSelectedStrategy(null)}>
          <Card className="max-w-2xl w-full max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
              Configure {selectedStrategy.name}
            </h2>
            <div className="space-y-4">
              <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded overflow-x-auto text-sm">
                {JSON.stringify(selectedStrategy.configuration, null, 2)}
              </pre>
              <div className="flex space-x-2">
                <Button variant="secondary" onClick={() => setSelectedStrategy(null)} className="flex-1">
                  Close
                </Button>
                <Button variant="primary" className="flex-1">
                  Save Changes
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
```

### Mode Behavior
- **GUIDE Mode:** Enable/Disable buttons are disabled, Configure is enabled (read-only)
- **AUTONOMOUS Mode:** All actions enabled

### Error Handling
- Loading state shows centered spinner
- Empty strategies array shows "No strategies configured"
- Failed mutations show error toast

---

## Dashboard 3: Backtesting

### Purpose
Run historical backtests on strategies to validate performance before live trading.

### File Location
`app/backtesting/page.tsx`

### Data Sources
- `POST /api/v1/backtest` - Run backtest with configuration
- Response contains `BacktestResult` with metrics and equity curve

### Visual Layout

**Left Sidebar (1/3 width):**

Configuration panel in Card:

**Form Fields:**
1. Strategy (dropdown): NBB, JadeCap, Fabio, Tori
2. Symbol (text input): Default "EURUSD"
3. Start Date (date picker)
4. End Date (date picker)
5. Initial Balance (number input): Default 10000

**Run Button:**
- Blue primary button with Play icon
- Text: "Run Backtest" or "Running..." when pending
- Full width
- Disabled while mutation is pending

**Right Panel (2/3 width):**

Initially shows empty state: "Configure backtest parameters and click 'Run Backtest' to begin"

After backtest completes:

**Performance Metrics Card:**
- Header with "Performance Metrics" title and "Export" button
- 3-column grid (responsive to 2 columns on mobile):
  1. Total Return (percentage with color coding)
  2. Sharpe Ratio (decimal)
  3. Max Drawdown (percentage in red)
  4. Win Rate (percentage)
  5. Total Trades (integer)
  6. Profit Factor (decimal)

**Equity Curve Card:**
- Title: "Equity Curve"
- LineChart showing equity progression over trades
- X-axis: Trade number
- Y-axis: Account equity
- Height: 400px
- Blue line, no dots (performance optimization)
- Tooltip shows trade number and equity value

**Trade Log Card:**
- Title: "Trade Log"
- Scrollable table showing first 20 trades
- Columns: Entry Time | Exit Time | Type | P&L
- Entry/Exit formatted as timestamps
- Type shows LONG (green badge) or SHORT (red badge)
- P&L color-coded (green if positive, red if negative)

### Implementation Code

```typescript
'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { BacktestResult } from '@/types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Play, Download } from 'lucide-react';

export default function BacktestingPage() {
  const [strategyName, setStrategyName] = useState('NBB');
  const [symbol, setSymbol] = useState('EURUSD');
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');
  const [initialBalance, setInitialBalance] = useState(10000);
  const [result, setResult] = useState<BacktestResult | null>(null);

  const backtestMutation = useMutation({
    mutationFn: async () => {
      return apiClient.runBacktest({
        strategy_name: strategyName,
        symbols: [symbol],
        start_date: startDate,
        end_date: endDate,
        initial_balance: initialBalance,
        configuration: {},
      });
    },
    onSuccess: (data) => {
      setResult(data);
    },
  });

  const equityCurve = result?.equity_curve?.map((point, idx) => ({
    trade: idx,
    equity: point,
  })) || [];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Backtesting</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Configuration</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Strategy
              </label>
              <select
                value={strategyName}
                onChange={(e) => setStrategyName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value="NBB">NBB (No Bullshit Breaker)</option>
                <option value="JadeCap">JadeCap (Trend Following)</option>
                <option value="Fabio">Fabio (Auction Market Theory)</option>
                <option value="Tori">Tori (Trendline + Fib)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Symbol
              </label>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                End Date
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Initial Balance
              </label>
              <input
                type="number"
                value={initialBalance}
                onChange={(e) => setInitialBalance(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            <Button
              variant="primary"
              onClick={() => backtestMutation.mutate()}
              disabled={backtestMutation.isPending}
              className="w-full"
            >
              <Play className="h-4 w-4 mr-2" />
              {backtestMutation.isPending ? 'Running...' : 'Run Backtest'}
            </Button>
          </div>
        </Card>

        <div className="lg:col-span-2 space-y-6">
          {result ? (
            <>
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Performance Metrics</h2>
                  <Button variant="secondary" size="sm">
                    <Download className="h-4 w-4 mr-2" />
                    Export
                  </Button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded">
                    <p className="text-sm text-gray-500">Total Return</p>
                    <p className={`text-2xl font-bold ${result.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {(result.total_return * 100).toFixed(2)}%
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded">
                    <p className="text-sm text-gray-500">Sharpe Ratio</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {result.sharpe_ratio?.toFixed(2) || 'N/A'}
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded">
                    <p className="text-sm text-gray-500">Max Drawdown</p>
                    <p className="text-2xl font-bold text-red-600">
                      {(result.max_drawdown * 100).toFixed(2)}%
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded">
                    <p className="text-sm text-gray-500">Win Rate</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {(result.win_rate * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded">
                    <p className="text-sm text-gray-500">Total Trades</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {result.total_trades}
                    </p>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded">
                    <p className="text-sm text-gray-500">Profit Factor</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {result.profit_factor?.toFixed(2) || 'N/A'}
                    </p>
                  </div>
                </div>
              </Card>

              <Card>
                <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Equity Curve</h2>
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={equityCurve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="trade" stroke="#9ca3af" />
                    <YAxis stroke="#9ca3af" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                      formatter={(value: number) => [`$${value.toFixed(2)}`, 'Equity']}
                    />
                    <Line
                      type="monotone"
                      dataKey="equity"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                      name="Account Equity"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              <Card>
                <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Trade Log</h2>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-100 dark:bg-gray-800">
                      <tr>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Entry</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Exit</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Type</th>
                        <th className="px-4 py-2 text-right text-sm font-semibold text-gray-700 dark:text-gray-300">P&L</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {result.trade_log?.slice(0, 20).map((trade, idx) => (
                        <tr key={idx}>
                          <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">
                            {new Date(trade.entry_time).toLocaleString()}
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">
                            {trade.exit_time ? new Date(trade.exit_time).toLocaleString() : 'Open'}
                          </td>
                          <td className="px-4 py-2 text-sm">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${
                              trade.side === 'long' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {trade.side.toUpperCase()}
                            </span>
                          </td>
                          <td className={`px-4 py-2 text-sm text-right font-semibold ${
                            trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            ${trade.pnl.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          ) : (
            <Card>
              <p className="text-gray-500 text-center py-16">
                Configure backtest parameters and click "Run Backtest" to begin
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
```

### Mode Behavior
- Both modes: Backtesting is always allowed (it's simulation, not live trading)

### Error Handling
- Mutation errors show toast notification
- Invalid date ranges validated on frontend
- Backend errors displayed in alert banner

---

## Dashboard 4: Optimization

### Purpose
Run parameter optimization jobs to discover optimal strategy configurations.

### File Location
`app/optimization/page.tsx`

### Data Sources
- `GET /api/v1/optimization/jobs` - List optimization jobs (refetch every 5s)
- `POST /api/v1/optimization/start` - Start new optimization job

### Visual Layout

**Left Sidebar (1/3 width):**

New Optimization panel in Card:

**Form Fields:**
1. Strategy (dropdown): NBB, JadeCap, Fabio, Tori
2. Method (dropdown): Grid Search, Random Search, AI-Driven
3. Iterations (number input): Default 100

**Start Button:**
- Blue primary button with Play icon
- Text: "Start Optimization" or "Starting..." when pending
- Full width

**Right Panel (2/3 width):**

Optimization Jobs list in Card:

Each job displays:

**Job Header:**
- Status icon (left):
  - CheckCircle (green) if completed
  - XCircle (red) if failed
  - Clock spinning (blue) if running
  - Clock static (gray) if pending
- Strategy name and method
- Status badge (right): COMPLETED, FAILED, RUNNING, PENDING

**Job Metadata:**
- Started timestamp
- Completed timestamp (if applicable)

**Progress Bar (if running):**
- Shows job.progress percentage
- Animated blue bar

**Best Parameters (if completed):**
- JSON code block showing optimized configuration
- "Create Playbook" button

### Implementation Code

```typescript
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { Play, Clock, CheckCircle, XCircle } from 'lucide-react';

export default function OptimizationPage() {
  const queryClient = useQueryClient();
  const [strategyName, setStrategyName] = useState('NBB');
  const [method, setMethod] = useState<'grid' | 'random' | 'ai'>('grid');
  const [iterations, setIterations] = useState(100);

  const { data: jobs } = useQuery({
    queryKey: ['optimizationJobs'],
    queryFn: () => apiClient.getOptimizationJobs(),
    refetchInterval: 5000,
  });

  const startOptimizationMutation = useMutation({
    mutationFn: async () => {
      return apiClient.startOptimization({
        strategy_name: strategyName,
        method,
        iterations,
        parameter_space: {
          lookback_period: { min: 10, max: 50, step: 5 },
          risk_reward_ratio: { min: 1.5, max: 3.0, step: 0.5 },
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['optimizationJobs'] });
    },
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'running':
        return <Clock className="h-5 w-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Parameter Optimization</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">New Optimization</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Strategy
              </label>
              <select
                value={strategyName}
                onChange={(e) => setStrategyName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value="NBB">NBB</option>
                <option value="JadeCap">JadeCap</option>
                <option value="Fabio">Fabio</option>
                <option value="Tori">Tori</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Method
              </label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as 'grid' | 'random' | 'ai')}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value="grid">Grid Search (Exhaustive)</option>
                <option value="random">Random Search (Monte Carlo)</option>
                <option value="ai">AI-Driven (Bayesian)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Iterations
              </label>
              <input
                type="number"
                value={iterations}
                onChange={(e) => setIterations(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            <Button
              variant="primary"
              onClick={() => startOptimizationMutation.mutate()}
              disabled={startOptimizationMutation.isPending}
              className="w-full"
            >
              <Play className="h-4 w-4 mr-2" />
              {startOptimizationMutation.isPending ? 'Starting...' : 'Start Optimization'}
            </Button>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Optimization Jobs</h2>
          {jobs && jobs.length > 0 ? (
            <div className="space-y-4">
              {jobs.map((job) => (
                <div key={job.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(job.status)}
                      <div>
                        <h3 className="font-semibold text-gray-900 dark:text-white">{job.strategy_name}</h3>
                        <p className="text-sm text-gray-500">{job.method} optimization</p>
                      </div>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      job.status === 'completed' ? 'bg-green-100 text-green-800' :
                      job.status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {job.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-3">
                    <div>
                      <p className="text-xs text-gray-500">Started</p>
                      <p className="text-sm text-gray-900 dark:text-white">
                        {new Date(job.created_at).toLocaleString()}
                      </p>
                    </div>
                    {job.completed_at && (
                      <div>
                        <p className="text-xs text-gray-500">Completed</p>
                        <p className="text-sm text-gray-900 dark:text-white">
                          {new Date(job.completed_at).toLocaleString()}
                        </p>
                      </div>
                    )}
                  </div>

                  {job.status === 'running' && job.progress !== undefined && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-500">Progress</span>
                        <span className="text-xs text-gray-900 dark:text-white">{job.progress}%</span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {job.best_params && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500 mb-1">Best Parameters</p>
                      <pre className="bg-gray-100 dark:bg-gray-800 p-2 rounded text-xs overflow-x-auto">
                        {JSON.stringify(job.best_params, null, 2)}
                      </pre>
                    </div>
                  )}

                  {job.status === 'completed' && (
                    <Button variant="primary" size="sm" className="mt-3">
                      Create Playbook
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-12">No optimization jobs yet</p>
          )}
        </Card>
      </div>
    </div>
  );
}
```

### Mode Behavior
- Both modes: Optimization is always allowed (it's research, not live trading)

### Error Handling
- Failed jobs show error message if available
- Network errors show toast
- Empty jobs list shows helpful empty state

---

## Dashboard 5: Signals

### Purpose
View all trading signals (pending, executed, cancelled) with filtering and manual execution controls.

### File Location
`app/signals/page.tsx`

### Data Sources
- `GET /api/v1/signals` - List all signals with optional filters (refetch every 3s)
- `PUT /api/v1/signals/{id}/execute` - Manually execute pending signal (AUTONOMOUS only)
- `PUT /api/v1/signals/{id}/cancel` - Cancel pending signal (AUTONOMOUS only)

### Visual Layout

**Header:**
- Title: "Signals"
- Filter dropdown: All, Pending, Executed, Cancelled

**Signals List:**

Each signal displays in a Card:

**Signal Header:**
- Symbol (bold) + Signal type badge (LONG=green, SHORT=red)
- Status badge (right): PENDING (yellow), EXECUTED (green), CANCELLED (gray)

**Signal Details:**
- Strategy name
- Entry price, stop loss, take profit
- Risk/reward ratio
- Position size
- Created timestamp

**Actions (if pending and AUTONOMOUS mode):**
- "Execute" button (green)
- "Cancel" button (red)

**Mode Warning (if GUIDE mode):**
- Amber text: "Switch to AUTONOMOUS mode to execute or cancel signals"

### Implementation Code

```typescript
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { useMode } from '@/providers/ModeProvider';
import { Play, X } from 'lucide-react';

export default function SignalsPage() {
  const { mode } = useMode();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<'all' | 'pending' | 'executed' | 'cancelled'>('all');

  const { data: signals } = useQuery({
    queryKey: ['signals', filter],
    queryFn: () => apiClient.listSignals(filter === 'all' ? {} : { status: filter }),
    refetchInterval: 3000,
  });

  const executeMutation = useMutation({
    mutationFn: (signalId: number) => apiClient.executeSignal(signalId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['signals'] }),
  });

  const cancelMutation = useMutation({
    mutationFn: (signalId: number) => apiClient.cancelSignal(signalId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['signals'] }),
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Signals</h1>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as any)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="all">All Signals</option>
          <option value="pending">Pending</option>
          <option value="executed">Executed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      <div className="space-y-4">
        {signals && signals.length > 0 ? (
          signals.map((signal) => (
            <Card key={signal.id}>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{signal.symbol}</h3>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      signal.signal_type === 'long' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {signal.signal_type.toUpperCase()}
                    </span>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    signal.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                    signal.status === 'executed' ? 'bg-green-100 text-green-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {signal.status.toUpperCase()}
                  </span>
                </div>

                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{signal.strategy_name}</p>
                  <p className="text-sm text-gray-900 dark:text-white">
                    Entry: ${signal.entry_price.toFixed(2)} | SL: ${signal.stop_loss.toFixed(2)} | TP: ${signal.take_profit.toFixed(2)}
                  </p>
                  <p className="text-sm text-gray-500">
                    R:R {signal.risk_reward_ratio?.toFixed(2)} | Size: {signal.position_size} units
                  </p>
                  <p className="text-xs text-gray-400">
                    Created: {new Date(signal.created_at).toLocaleString()}
                  </p>
                </div>

                {signal.status === 'pending' && (
                  <div className="flex space-x-2">
                    <Button
                      variant="primary"
                      onClick={() => executeMutation.mutate(signal.id)}
                      disabled={mode === 'guide'}
                      className="flex-1"
                    >
                      <Play className="h-4 w-4 mr-2" />
                      Execute
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => cancelMutation.mutate(signal.id)}
                      disabled={mode === 'guide'}
                      className="flex-1"
                    >
                      <X className="h-4 w-4 mr-2" />
                      Cancel
                    </Button>
                  </div>
                )}

                {mode === 'guide' && signal.status === 'pending' && (
                  <p className="text-xs text-amber-600 dark:text-amber-500">
                    Switch to AUTONOMOUS mode to execute or cancel signals
                  </p>
                )}
              </div>
            </Card>
          ))
        ) : (
          <Card>
            <p className="text-gray-500 text-center py-12">No signals found</p>
          </Card>
        )}
      </div>
    </div>
  );
}
```

### Mode Behavior
- **GUIDE Mode:** Execute and Cancel buttons disabled
- **AUTONOMOUS Mode:** Execute and Cancel buttons enabled

### Error Handling
- Execution failures show error toast with reason
- Network errors retry automatically
- Empty states show filter-aware messages

---

## Dashboard 6: Execution

### Purpose
Monitor active and historical orders, view execution logs, and manage open positions.

### File Location
`app/execution/page.tsx`

### Data Sources
- `GET /api/v1/execution/orders` - List orders with filters (refetch every 3s)
- `GET /api/v1/execution/logs?limit=50` - Execution logs (refetch every 5s)
- `PUT /api/v1/execution/orders/{id}/close` - Close position (AUTONOMOUS only)

### Visual Layout

**Active Orders Table:**

Full-width card with table:

**Columns:**
- Symbol
- Side (BUY/SELL badge)
- Quantity
- Entry Price
- Current Price
- Unrealized P&L (color-coded)
- Actions (Close button if AUTONOMOUS)

**Execution Logs:**

Full-width card below orders:

**Table Columns:**
- Timestamp
- Order ID
- Action (SUBMITTED, FILLED, MODIFIED, CLOSED, FAILED)
- Details
- Broker Response

**Logs color-coded by action:**
- SUBMITTED: Blue
- FILLED: Green
- FAILED: Red
- CLOSED: Gray

### Implementation Code

```typescript
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { useMode } from '@/providers/ModeProvider';
import { X } from 'lucide-react';

export default function ExecutionPage() {
  const { mode } = useMode();
  const queryClient = useQueryClient();

  const { data: orders } = useQuery({
    queryKey: ['orders'],
    queryFn: () => apiClient.listOrders({}),
    refetchInterval: 3000,
  });

  const { data: logs } = useQuery({
    queryKey: ['executionLogs'],
    queryFn: () => apiClient.getExecutionLogs({ limit: 50 }),
    refetchInterval: 5000,
  });

  const closeMutation = useMutation({
    mutationFn: (orderId: number) => apiClient.closeOrder(orderId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] }),
  });

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Execution</h1>

      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Active Orders</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-100 dark:bg-gray-800">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Symbol</th>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Side</th>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Qty</th>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Entry</th>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Current</th>
                <th className="px-4 py-2 text-right text-sm font-semibold text-gray-700 dark:text-gray-300">P&L</th>
                {mode === 'autonomous' && (
                  <th className="px-4 py-2 text-right text-sm font-semibold text-gray-700 dark:text-gray-300">Actions</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {orders && orders.length > 0 ? (
                orders.map((order) => (
                  <tr key={order.id}>
                    <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">{order.symbol}</td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        order.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {order.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">{order.quantity}</td>
                    <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">${order.entry_price?.toFixed(2) || 'N/A'}</td>
                    <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">${order.current_price?.toFixed(2) || 'N/A'}</td>
                    <td className={`px-4 py-2 text-sm text-right font-semibold ${
                      order.unrealized_pnl && order.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      ${order.unrealized_pnl?.toFixed(2) || '0.00'}
                    </td>
                    {mode === 'autonomous' && (
                      <td className="px-4 py-2 text-right">
                        <Button variant="danger" size="sm" onClick={() => closeMutation.mutate(order.id)}>
                          <X className="h-4 w-4 mr-1" />
                          Close
                        </Button>
                      </td>
                    )}
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={mode === 'autonomous' ? 7 : 6} className="px-4 py-8 text-center text-gray-500">
                    No active orders
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Execution Logs</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-100 dark:bg-gray-800">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Timestamp</th>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Order ID</th>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Action</th>
                <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {logs && logs.length > 0 ? (
                logs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">{log.order_id}</td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        log.action === 'FILLED' ? 'bg-green-100 text-green-800' :
                        log.action === 'FAILED' ? 'bg-red-100 text-red-800' :
                        log.action === 'SUBMITTED' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400">{log.details}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                    No execution logs
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
```

### Mode Behavior
- **GUIDE Mode:** Close buttons hidden, read-only view
- **AUTONOMOUS Mode:** Close buttons visible and enabled

---

## Dashboard 7: Performance

### Purpose
Analyze trading performance with charts, metrics, and comparisons.

### File Location
`app/performance/page.tsx`

### Data Sources
- `GET /api/v1/performance/snapshots?limit=200` - Performance snapshots (refetch every 10s)
- `GET /api/v1/performance/summary` - Aggregated metrics (refetch every 10s)

### Visual Layout

**Performance Summary Cards (4-column grid):**
1. Total Profit: Dollar amount with color coding
2. Win Rate: Percentage
3. Sharpe Ratio: Decimal
4. Max Drawdown: Percentage in red

**Equity & Balance Chart:**
- LineChart with two lines:
  - Total Equity (blue)
  - Account Balance (green)
- X-axis: Timestamp
- Y-axis: Dollar value
- Height: 400px

**Monthly Returns Table:**
- Grid showing returns by month
- Color-coded cells (green for positive, red for negative)

### Implementation Code

```typescript
'use client';

import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { apiClient } from '@/services/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function PerformancePage() {
  const { data: snapshots } = useQuery({
    queryKey: ['performanceSnapshots'],
    queryFn: () => apiClient.getPerformanceSnapshots({ limit: 200 }),
    refetchInterval: 10000,
  });

  const { data: summary } = useQuery({
    queryKey: ['performanceSummary'],
    queryFn: () => apiClient.getPerformanceSummary(),
    refetchInterval: 10000,
  });

  const chartData = snapshots?.map(s => ({
    time: new Date(s.snapshot_time).getTime(),
    equity: s.total_equity,
    balance: s.account_balance,
  })) || [];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Performance</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <p className="text-sm text-gray-500">Total Profit</p>
          <p className={`text-2xl font-bold ${summary?.total_profit && summary.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${summary?.total_profit?.toFixed(2) || '0.00'}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Win Rate</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {summary?.win_rate ? (summary.win_rate * 100).toFixed(1) : '0.0'}%
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Sharpe Ratio</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {summary?.sharpe_ratio?.toFixed(2) || 'N/A'}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Max Drawdown</p>
          <p className="text-2xl font-bold text-red-600">
            {summary?.max_drawdown ? (summary.max_drawdown * 100).toFixed(2) : '0.00'}%
          </p>
        </Card>
      </div>

      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Equity & Balance</h2>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="time"
                tickFormatter={(t) => new Date(t).toLocaleDateString()}
                stroke="#9ca3af"
              />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                labelFormatter={(t) => new Date(t).toLocaleString()}
                formatter={(value: number) => `$${value.toFixed(2)}`}
              />
              <Legend />
              <Line type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={2} dot={false} name="Total Equity" />
              <Line type="monotone" dataKey="balance" stroke="#10b981" strokeWidth={2} dot={false} name="Account Balance" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-center py-12">No performance data</p>
        )}
      </Card>
    </div>
  );
}
```

---

## Dashboard 8: Journal

### Purpose
View comprehensive trade journal with market context, AI reasoning, and performance analysis.

### File Location
`app/journal/page.tsx`

### Data Sources
- `GET /api/v1/journal/entries?limit=50` - Journal entries (refetch every 10s)

### Visual Layout

**Filters:**
- Source: All, Live, Paper, Backtest
- Date range picker

**Journal Entries List:**

Each entry displays in Card:

**Entry Header:**
- Symbol + Side badge (LONG/SHORT)
- Source badge (LIVE=green, PAPER=blue, BACKTEST=gray)

**Trade Details:**
- Strategy name
- Entry price → Exit price
- Net P&L (color-coded)
- Hold duration
- R:R achieved

**Market Context (expandable):**
- Market conditions at entry
- Volatility, trend, support/resistance

**AI Reasoning (expandable):**
- Why trade was taken
- Why trade was exited
- Lessons learned

### Implementation Code

```typescript
'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { apiClient } from '@/services/api';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function JournalPage() {
  const [source, setSource] = useState<'all' | 'live' | 'paper' | 'backtest'>('all');
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);

  const { data: entries } = useQuery({
    queryKey: ['journalEntries', source],
    queryFn: () => apiClient.getJournalEntries(source === 'all' ? { limit: 50 } : { source, limit: 50 }),
    refetchInterval: 10000,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Trade Journal</h1>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value as any)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="all">All Sources</option>
          <option value="live">Live</option>
          <option value="paper">Paper</option>
          <option value="backtest">Backtest</option>
        </select>
      </div>

      <div className="space-y-4">
        {entries && entries.length > 0 ? (
          entries.map((entry) => (
            <Card key={entry.entry_id}>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{entry.symbol}</h3>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      entry.side === 'long' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {entry.side?.toUpperCase()}
                    </span>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    entry.source === 'live' ? 'bg-green-100 text-green-800' :
                    entry.source === 'paper' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {entry.source.toUpperCase()}
                  </span>
                </div>

                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{entry.strategy_name}</p>
                  <p className="text-sm text-gray-900 dark:text-white">
                    ${entry.entry_price.toFixed(2)} → ${entry.exit_price?.toFixed(2) || 'Open'}
                  </p>
                  <p className={`text-sm font-semibold ${entry.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    P&L: ${entry.pnl.toFixed(2)}
                  </p>
                  <p className="text-xs text-gray-500">
                    {new Date(entry.entry_time).toLocaleString()} - {entry.exit_time ? new Date(entry.exit_time).toLocaleString() : 'Open'}
                  </p>
                </div>

                <button
                  onClick={() => setExpandedEntry(expandedEntry === entry.entry_id ? null : entry.entry_id)}
                  className="flex items-center text-sm text-blue-600 hover:text-blue-700"
                >
                  {expandedEntry === entry.entry_id ? (
                    <>
                      <ChevronUp className="h-4 w-4 mr-1" />
                      Hide Details
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-4 w-4 mr-1" />
                      Show Details
                    </>
                  )}
                </button>

                {expandedEntry === entry.entry_id && (
                  <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded space-y-3">
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Market Context</h4>
                      <pre className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                        {JSON.stringify(entry.market_context, null, 2)}
                      </pre>
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Strategy Config</h4>
                      <pre className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                        {JSON.stringify(entry.strategy_config, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          ))
        ) : (
          <Card>
            <p className="text-gray-500 text-center py-12">No journal entries</p>
          </Card>
        )}
      </div>
    </div>
  );
}
```

---

## Dashboard 9: AI Chat

### Purpose
Interactive chat with AI agents, view their decisions, and monitor their health.

### File Location
`app/ai-chat/page.tsx`

### Data Sources
- `GET /api/v1/ai/decisions?limit=50` - AI decisions (refetch every 5s)
- `GET /api/v1/ai/agents/health` - Agent health status (refetch every 5s)
- `POST /api/v1/ai/chat` - Send message to AI (future)

### Visual Layout

**Agent Health Cards (top):**

4-column grid showing each agent:
- Supervisor
- Strategy Agent
- Risk Agent
- Execution Agent

Each card shows:
- Agent name
- Status: Healthy (green), Degraded (yellow), Unhealthy (red)
- Last active timestamp

**Decision Feed:**

Scrollable chat-like interface showing AI decisions:

Each decision as a message bubble:
- Agent name (bold)
- Decision type (monospace)
- Reasoning text
- Timestamp

**Chat Input (bottom):**
- Text input (full width)
- Send button with icon
- Placeholder: "Ask AI agents..." (future feature)

### Implementation Code

```typescript
'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { Send, Circle } from 'lucide-react';

export default function AIChatPage() {
  const [message, setMessage] = useState('');

  const { data: decisions } = useQuery({
    queryKey: ['aiDecisions'],
    queryFn: () => apiClient.getAIDecisions({ limit: 50 }),
    refetchInterval: 5000,
  });

  const { data: health } = useQuery({
    queryKey: ['agentHealth'],
    queryFn: () => apiClient.getAgentHealth(),
    refetchInterval: 5000,
  });

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">AI Agent Chat</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {health && health.agents?.map((agent: any) => (
          <Card key={agent.name}>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 dark:text-white">{agent.name}</h3>
                <Circle className={`h-3 w-3 fill-current ${
                  agent.status === 'healthy' ? 'text-green-500' :
                  agent.status === 'degraded' ? 'text-yellow-500' :
                  'text-red-500'
                }`} />
              </div>
              <p className="text-xs text-gray-500">
                Last active: {new Date(agent.last_active).toLocaleTimeString()}
              </p>
            </div>
          </Card>
        ))}
      </div>

      <Card className="h-[600px] flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {decisions && decisions.length > 0 ? (
            decisions.map((decision) => (
              <div key={decision.id} className="bg-gray-50 dark:bg-gray-800 p-3 rounded">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">{decision.agent_name}</p>
                  <p className="text-xs text-gray-400">{new Date(decision.decision_time).toLocaleTimeString()}</p>
                </div>
                <p className="text-xs text-gray-500 mb-1">
                  <code className="bg-gray-200 dark:bg-gray-700 px-1 rounded">{decision.decision_type}</code>
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">{decision.reasoning}</p>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-center py-12">No AI decisions yet</p>
          )}
        </div>
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 flex space-x-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask AI agents..."
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
          />
          <Button variant="primary">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </Card>
    </div>
  );
}
```

---

## Dashboard 10: Settings

### Purpose
Configure system mode, risk limits, broker connections, and user preferences.

### File Location
`app/settings/page.tsx`

### Data Sources
- `GET /api/v1/config` - System configuration
- `PUT /api/v1/config` - Update configuration
- `GET /api/v1/user/profile` - User profile
- `PUT /api/v1/user/profile` - Update profile

### Visual Layout

**System Mode Card:**
- Title: "System Mode"
- Two buttons: GUIDE (left), AUTONOMOUS (right)
- Active mode highlighted in blue
- Description text below explaining current mode

**Risk Limits Card:**
- Title: "Risk Limits"
- Read-only fields showing hard limits:
  - Max Risk Per Trade: 2.0%
  - Max Daily Loss: 5.0%
  - Emergency Drawdown: 15.0%
  - Max Open Positions: 10
- Note: "These are hard limits and cannot be changed"

**Broker Connection Card:**
- Broker type dropdown: MT5, OANDA, Paper
- Connection status indicator
- "Test Connection" button
- API credentials (masked, future feature)

**User Preferences Card:**
- Email notifications toggle
- Dark mode toggle
- Timezone selector

### Implementation Code

```typescript
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/services/api';
import { useMode } from '@/providers/ModeProvider';

export default function SettingsPage() {
  const { mode, setMode } = useMode();
  const queryClient = useQueryClient();

  const { data: config } = useQuery({
    queryKey: ['systemConfig'],
    queryFn: () => apiClient.getSystemConfig(),
  });

  const updateConfigMutation = useMutation({
    mutationFn: (updates: any) => apiClient.updateSystemConfig(updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['systemConfig'] }),
  });

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Settings</h1>

      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">System Mode</h2>
        <div className="flex space-x-4">
          <Button
            variant={mode === 'guide' ? 'primary' : 'secondary'}
            onClick={() => setMode('guide')}
            className="flex-1"
          >
            GUIDE Mode
          </Button>
          <Button
            variant={mode === 'autonomous' ? 'primary' : 'secondary'}
            onClick={() => setMode('autonomous')}
            className="flex-1"
          >
            AUTONOMOUS Mode
          </Button>
        </div>
        <p className="text-sm text-gray-500 mt-3">
          {mode === 'guide'
            ? 'System provides recommendations only. You must manually approve all trades.'
            : 'System can execute trades automatically within defined risk limits.'}
        </p>
      </Card>

      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Risk Limits</h2>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Risk Per Trade (%)
            </label>
            <input
              type="number"
              value={config?.max_risk_per_trade || 2.0}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white"
              disabled
            />
            <p className="text-xs text-gray-500 mt-1">Hard limit: Cannot be changed</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Daily Loss (%)
            </label>
            <input
              type="number"
              value={config?.max_daily_loss || 5.0}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white"
              disabled
            />
            <p className="text-xs text-gray-500 mt-1">Hard limit: Cannot be changed</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Emergency Drawdown (%)
            </label>
            <input
              type="number"
              value={config?.emergency_drawdown || 15.0}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white"
              disabled
            />
            <p className="text-xs text-gray-500 mt-1">Hard limit: Triggers emergency shutdown</p>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Broker Connection</h2>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Broker Type
            </label>
            <select className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
              <option>MT5</option>
              <option>OANDA</option>
              <option>Paper</option>
            </select>
          </div>
          <Button variant="primary">Test Connection</Button>
        </div>
      </Card>
    </div>
  );
}
```

---

## Required Tests

Create test files for each dashboard in `__tests__/app/` directory:

### Example Test: `__tests__/app/page.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import DashboardPage from '@/app/page';
import { apiClient } from '@/services/api';

jest.mock('@/services/api');

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe('Dashboard Page', () => {
  beforeEach(() => {
    (apiClient.getSystemConfig as jest.Mock).mockResolvedValue({ mode: 'guide' });
    (apiClient.getCurrentRiskState as jest.Mock).mockResolvedValue({
      account_balance: 10000,
      total_equity: 10500,
      daily_pnl: 500,
      open_positions: 3,
      emergency_shutdown: false,
    });
    (apiClient.listSignals as jest.Mock).mockResolvedValue([]);
    (apiClient.listOrders as jest.Mock).mockResolvedValue([]);
    (apiClient.getPerformanceSnapshots as jest.Mock).mockResolvedValue([]);
    (apiClient.getAIDecisions as jest.Mock).mockResolvedValue([]);
  });

  it('renders dashboard title', async () => {
    render(<DashboardPage />, { wrapper });
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('displays account balance', async () => {
    render(<DashboardPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/\$10,000.00/)).toBeInTheDocument();
    });
  });

  it('shows emergency alert when shutdown active', async () => {
    (apiClient.getCurrentRiskState as jest.Mock).mockResolvedValue({
      account_balance: 10000,
      total_equity: 8500,
      daily_pnl: -1500,
      open_positions: 0,
      emergency_shutdown: true,
    });

    render(<DashboardPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/EMERGENCY SHUTDOWN ACTIVE/)).toBeInTheDocument();
    });
  });
});
```

Repeat for all dashboards with appropriate test cases.

---

## Validation Checklist

Before proceeding to the next prompt, verify ALL of the following:

### UI Functionality
- [ ] All 10 dashboards render without errors
- [ ] Real-time data updates working (verify refetchInterval)
- [ ] Charts display correctly with sample data
- [ ] Mode indicator visible and functional on all pages
- [ ] GUIDE mode disables appropriate buttons
- [ ] AUTONOMOUS mode enables appropriate buttons
- [ ] Emergency shutdown alert displays when triggered
- [ ] Filter dropdowns work on Signals, Optimization, Journal pages

### Data Integration
- [ ] All API endpoints called with correct parameters
- [ ] TypeScript types match API responses
- [ ] Loading states show spinners or skeletons
- [ ] Error states display user-friendly messages
- [ ] Empty states show helpful guidance
- [ ] Mutations invalidate queries correctly

### Charts & Tables
- [ ] Recharts render without console errors
- [ ] ResponsiveContainer scales properly
- [ ] Tooltips show formatted values
- [ ] Tables are scrollable on mobile
- [ ] Color coding is consistent (green=positive, red=negative)
- [ ] Axes labels are readable

### User Experience
- [ ] Responsive design works on 320px mobile
- [ ] Dark mode styles applied consistently
- [ ] Buttons have appropriate loading states
- [ ] Forms validate input before submission
- [ ] Success/error toasts appear for mutations
- [ ] Navigation between pages is instant

### Accessibility
- [ ] All interactive elements have ARIA labels
- [ ] Keyboard tab order is logical
- [ ] Screen reader friendly
- [ ] Color contrast meets WCAG AA standards
- [ ] Focus states visible on all inputs

### Performance
- [ ] No excessive re-renders (use React DevTools Profiler)
- [ ] React Query caching prevents redundant requests
- [ ] Charts handle 1000+ data points smoothly
- [ ] List virtualization for large datasets (future enhancement)

### Testing
- [ ] Unit tests pass for all dashboards
- [ ] Integration tests verify API interactions
- [ ] Test coverage > 80%
- [ ] No TypeScript compilation errors

---

## Hard Stop Criteria

DO NOT proceed to the next prompt if ANY of the following are true:

1. **Runtime Errors:** Any dashboard throws errors in console
2. **Chart Failures:** Recharts fail to render or display incorrect data
3. **Mode Switching:** Changing mode doesn't update UI behavior
4. **API Mismatch:** API client methods missing or incorrectly typed
5. **Emergency State:** Emergency shutdown not visually distinct
6. **Real-time Updates:** refetchInterval not working
7. **Mobile Broken:** Responsive design fails on < 768px screens
8. **TypeScript Errors:** Compilation errors or type warnings
9. **Accessibility:** Critical WCAG violations (color contrast, missing labels)
10. **Performance:** Dashboards freeze or lag with realistic data volumes
11. **Missing Dashboards:** Any of the 10 dashboards not implemented
12. **Test Failures:** Any test suite fails

---

## Next Prompt

After completing this prompt and passing ALL validation checks, proceed to:

**14_SETTINGS_AND_MODES.md** - Deep dive into system configuration, mode management, broker connections, user preferences, and admin controls.
