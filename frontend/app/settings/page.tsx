'use client';

import { useState } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useMode } from '@/providers/ModeProvider';
import { useAuth } from '@/hooks/useAuth';
import { useRiskLimits } from '@/hooks/useRisk';
import { useBrokers } from '@/hooks/useExecution';
import { snakeToTitle } from '@/lib/utils';
import {
  Settings,
  Shield,
  Zap,
  User,
  Bell,
  Key,
  Database,
  Server,
  RefreshCw,
  Check,
  AlertTriangle,
  Moon,
  Sun,
  Monitor,
} from 'lucide-react';

export default function SettingsPage() {
  const { mode, setMode, isLoading: modeLoading } = useMode();
  const { user, logout } = useAuth();
  const { data: riskLimits, isLoading: limitsLoading } = useRiskLimits();
  const { data: brokers } = useBrokers();

  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  const [notifications, setNotifications] = useState({
    signals: true,
    executions: true,
    riskAlerts: true,
    dailySummary: false,
  });

  const handleModeChange = async (newMode: 'guide' | 'autonomous') => {
    try {
      await setMode(newMode);
    } catch (error) {
      console.error('Failed to change mode:', error);
    }
  };

  const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme);
    // In a real implementation, this would apply the theme
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else if (newTheme === 'light') {
      document.documentElement.classList.remove('dark');
    }
  };

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Settings"
        description="Configure your trading platform"
      >
        {/* Account Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5 text-gray-500" />
              Account
            </CardTitle>
            <CardDescription>Manage your account settings</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div>
                  <p className="font-medium">{user?.email || 'user@example.com'}</p>
                  <p className="text-sm text-gray-500">Account Email</p>
                </div>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex gap-4">
                <Button variant="outline" disabled>
                  <Key className="h-4 w-4 mr-2" />
                  Change Password
                </Button>
                <Button variant="destructive" onClick={logout}>
                  Sign Out
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Trading Mode Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {mode === 'guide' ? (
                <Shield className="h-5 w-5 text-blue-500" />
              ) : (
                <Zap className="h-5 w-5 text-green-500" />
              )}
              Trading Mode
            </CardTitle>
            <CardDescription>
              Control how signals are executed
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
                  mode === 'guide'
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                }`}
                onClick={() => handleModeChange('guide')}
              >
                <div className="flex items-center gap-3 mb-3">
                  <Shield className="h-8 w-8 text-blue-500" />
                  <div>
                    <h3 className="font-bold text-lg">GUIDE Mode</h3>
                    {mode === 'guide' && (
                      <Badge variant="default" className="mt-1">Active</Badge>
                    )}
                  </div>
                </div>
                <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-500" />
                    Manual approval for all trades
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-500" />
                    Review signals before execution
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-500" />
                    Full control over position sizing
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-500" />
                    Recommended for beginners
                  </li>
                </ul>
              </div>

              <div
                className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
                  mode === 'autonomous'
                    ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                }`}
                onClick={() => handleModeChange('autonomous')}
              >
                <div className="flex items-center gap-3 mb-3">
                  <Zap className="h-8 w-8 text-green-500" />
                  <div>
                    <h3 className="font-bold text-lg">AUTONOMOUS Mode</h3>
                    {mode === 'autonomous' && (
                      <Badge variant="success" className="mt-1">Active</Badge>
                    )}
                  </div>
                </div>
                <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-500" />
                    Automatic trade execution
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-500" />
                    AI-managed position sizing
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-500" />
                    24/7 operation capability
                  </li>
                  <li className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                    Requires validated strategies
                  </li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Risk Management Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              Risk Management
            </CardTitle>
            <CardDescription>
              Configure risk limits and controls
            </CardDescription>
          </CardHeader>
          <CardContent>
            {limitsLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-12 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : riskLimits ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(riskLimits).map(([key, value]) => (
                  <div key={key} className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">{snakeToTitle(key)}</p>
                        <p className="text-sm text-gray-500">Current limit</p>
                      </div>
                      <span className="text-lg font-bold">
                        {typeof value === 'number'
                          ? value.toString().includes('.')
                            ? `${(value * 100).toFixed(1)}%`
                            : value
                          : String(value)
                        }
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">
                Risk limits are configured in the backend
              </p>
            )}
          </CardContent>
        </Card>

        {/* Appearance Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sun className="h-5 w-5 text-yellow-500" />
              Appearance
            </CardTitle>
            <CardDescription>Customize the look and feel</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <Button
                variant={theme === 'light' ? 'default' : 'outline'}
                onClick={() => handleThemeChange('light')}
                className="flex-1"
              >
                <Sun className="h-4 w-4 mr-2" />
                Light
              </Button>
              <Button
                variant={theme === 'dark' ? 'default' : 'outline'}
                onClick={() => handleThemeChange('dark')}
                className="flex-1"
              >
                <Moon className="h-4 w-4 mr-2" />
                Dark
              </Button>
              <Button
                variant={theme === 'system' ? 'default' : 'outline'}
                onClick={() => handleThemeChange('system')}
                className="flex-1"
              >
                <Monitor className="h-4 w-4 mr-2" />
                System
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Notifications Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-purple-500" />
              Notifications
            </CardTitle>
            <CardDescription>Configure alert preferences</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(notifications).map(([key, enabled]) => (
                <div
                  key={key}
                  className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg"
                >
                  <div>
                    <p className="font-medium">{snakeToTitle(key)}</p>
                    <p className="text-sm text-gray-500">
                      {key === 'signals' && 'Get notified when new signals are generated'}
                      {key === 'executions' && 'Get notified when trades are executed'}
                      {key === 'riskAlerts' && 'Get notified about risk limit warnings'}
                      {key === 'dailySummary' && 'Receive daily performance summary'}
                    </p>
                  </div>
                  <button
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                    onClick={() => setNotifications({ ...notifications, [key]: !enabled })}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        enabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Connected Brokers Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-blue-500" />
              Connected Brokers
            </CardTitle>
            <CardDescription>Manage broker connections</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Paper Trading - Always Available */}
              <div className="flex items-center justify-between p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="h-3 w-3 rounded-full bg-green-500" />
                  <div>
                    <p className="font-medium">Paper Trading</p>
                    <p className="text-sm text-gray-500">Simulated trading (always available)</p>
                  </div>
                </div>
                <Badge variant="success">Connected</Badge>
              </div>

              {/* Other Brokers */}
              {brokers && brokers.length > 0 ? (
                brokers.map((broker: { name: string; type: string; is_connected: boolean }, idx: number) => (
                  <div
                    key={idx}
                    className={`flex items-center justify-between p-4 rounded-lg ${
                      broker.is_connected
                        ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                        : 'bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`h-3 w-3 rounded-full ${
                        broker.is_connected ? 'bg-green-500' : 'bg-gray-400'
                      }`} />
                      <div>
                        <p className="font-medium">{snakeToTitle(broker.name)}</p>
                        <p className="text-sm text-gray-500">{broker.type}</p>
                      </div>
                    </div>
                    <Badge variant={broker.is_connected ? 'success' : 'secondary'}>
                      {broker.is_connected ? 'Connected' : 'Disconnected'}
                    </Badge>
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">
                  No additional brokers configured
                </p>
              )}

              <Button variant="outline" className="w-full" disabled>
                <Database className="h-4 w-4 mr-2" />
                Add Broker Connection (Coming Soon)
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* System Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-gray-500" />
              System Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Version</p>
                <p className="font-medium">1.0.0</p>
              </div>
              <div>
                <p className="text-gray-500">Environment</p>
                <p className="font-medium">Development</p>
              </div>
              <div>
                <p className="text-gray-500">API Status</p>
                <Badge variant="success">Online</Badge>
              </div>
              <div>
                <p className="text-gray-500">Last Updated</p>
                <p className="font-medium">{new Date().toLocaleDateString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
