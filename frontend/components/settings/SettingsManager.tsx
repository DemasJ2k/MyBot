'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/services/api';
import { useMode } from '@/providers/ModeProvider';
import { AlertTriangle, CheckCircle, Info, Shield, Settings, Clock, Bell, Lock } from 'lucide-react';

interface SystemSettings {
  mode: string;
  broker_type: string;
  broker_connected: boolean;
  data_provider: string;
  max_risk_per_trade_percent: number;
  max_daily_loss_percent: number;
  emergency_drawdown_percent: number;
  max_open_positions: number;
  max_trades_per_day: number;
  auto_disable_strategies: boolean;
  strategy_disable_threshold: number;
  cancel_orders_on_mode_switch: boolean;
  require_confirmation_for_autonomous: boolean;
  health_check_interval_seconds: number;
  agent_timeout_seconds: number;
  email_notifications_enabled: boolean;
  notification_email: string | null;
  version: number;
}

interface HardConstants {
  max_risk_per_trade_percent: number;
  max_daily_loss_percent: number;
  emergency_drawdown_percent: number;
  max_open_positions: number;
  max_trades_per_day: number;
  max_trades_per_hour: number;
  min_risk_reward_ratio: number;
  max_position_size_percent: number;
  strategy_auto_disable_threshold: number;
}

interface AuditEntry {
  id: number;
  settings_version: number;
  changed_by: number | null;
  changed_at: string;
  change_type: string;
  old_value: Record<string, unknown>;
  new_value: Record<string, unknown>;
  reason: string | null;
}

type SettingsTab = 'risk' | 'mode' | 'strategy' | 'notifications' | 'audit';

export default function SettingsManager() {
  const { mode, setMode, switchError } = useMode();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<SettingsTab>('risk');
  const [editedSettings, setEditedSettings] = useState<Partial<SystemSettings>>({});
  const [showModeConfirmation, setShowModeConfirmation] = useState(false);
  const [pendingMode, setPendingMode] = useState<'guide' | 'autonomous' | null>(null);
  const [saveReason, setSaveReason] = useState('');
  const [saveStatus, setSaveStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Fetch system settings
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['systemSettings'],
    queryFn: () => apiClient.getSystemSettings(),
  });

  // Fetch hard constants
  const { data: constants } = useQuery({
    queryKey: ['hardConstants'],
    queryFn: () => apiClient.getHardConstants(),
  });

  // Fetch audit trail
  const { data: auditTrail } = useQuery({
    queryKey: ['settingsAudit'],
    queryFn: () => apiClient.getSettingsAudit(50),
    enabled: activeTab === 'audit',
  });

  // Update settings mutation
  const updateSettingsMutation = useMutation({
    mutationFn: (data: { updates: Partial<SystemSettings>; reason?: string }) =>
      apiClient.updateSystemSettings(data.updates, data.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['systemSettings'] });
      queryClient.invalidateQueries({ queryKey: ['settingsAudit'] });
      setEditedSettings({});
      setSaveReason('');
      setSaveStatus({ type: 'success', message: 'Settings saved successfully' });
      setTimeout(() => setSaveStatus(null), 3000);
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      const message = error.response?.data?.detail || 'Failed to save settings';
      setSaveStatus({ type: 'error', message });
    },
  });

  // Clear status on tab change
  useEffect(() => {
    setSaveStatus(null);
  }, [activeTab]);

  const handleModeChange = async (newMode: 'guide' | 'autonomous') => {
    if (newMode === 'autonomous' && settings?.require_confirmation_for_autonomous) {
      setPendingMode(newMode);
      setShowModeConfirmation(true);
    } else {
      try {
        await setMode(newMode, 'User changed mode');
        queryClient.invalidateQueries({ queryKey: ['systemSettings'] });
        queryClient.invalidateQueries({ queryKey: ['settingsAudit'] });
      } catch {
        // Error handled by ModeProvider
      }
    }
  };

  const confirmModeChange = async () => {
    if (pendingMode) {
      try {
        await setMode(pendingMode, 'User confirmed autonomous mode activation');
        queryClient.invalidateQueries({ queryKey: ['systemSettings'] });
        queryClient.invalidateQueries({ queryKey: ['settingsAudit'] });
      } catch {
        // Error handled by ModeProvider
      }
      setPendingMode(null);
      setShowModeConfirmation(false);
    }
  };

  const cancelModeChange = () => {
    setPendingMode(null);
    setShowModeConfirmation(false);
  };

  const handleSettingChange = (key: keyof SystemSettings, value: unknown) => {
    setEditedSettings(prev => ({ ...prev, [key]: value }));
  };

  const hasChanges = Object.keys(editedSettings).length > 0;

  const saveSettings = () => {
    if (!hasChanges) return;
    updateSettingsMutation.mutate({ updates: editedSettings, reason: saveReason || undefined });
  };

  const discardChanges = () => {
    setEditedSettings({});
    setSaveReason('');
    setSaveStatus(null);
  };

  const getCurrentValue = <K extends keyof SystemSettings>(key: K): SystemSettings[K] => {
    return (editedSettings[key] ?? settings?.[key]) as SystemSettings[K];
  };

  if (settingsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const tabs: { id: SettingsTab; label: string; icon: typeof Shield }[] = [
    { id: 'risk', label: 'Risk Limits', icon: Shield },
    { id: 'mode', label: 'Mode & Behavior', icon: Settings },
    { id: 'strategy', label: 'Strategy', icon: Clock },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'audit', label: 'Audit Log', icon: Lock },
  ];

  return (
    <div className="space-y-6">
      {/* Mode Confirmation Dialog */}
      {showModeConfirmation && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="max-w-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="h-8 w-8 text-yellow-500" />
              <h3 className="text-lg font-semibold">Confirm Autonomous Mode</h3>
            </div>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              You are about to enable <strong>AUTONOMOUS</strong> mode. In this mode:
            </p>
            <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400 mb-4 space-y-1">
              <li>AI can execute trades automatically</li>
              <li>AI can enable/disable strategies</li>
              <li>All risk limits still apply</li>
              <li>Emergency shutdown can override at any time</li>
            </ul>
            <div className="flex gap-3">
              <Button variant="outline" onClick={cancelModeChange} className="flex-1">
                Cancel
              </Button>
              <Button onClick={confirmModeChange} className="flex-1 bg-yellow-600 hover:bg-yellow-700">
                Confirm Autonomous
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Status Messages */}
      {saveStatus && (
        <div
          className={`flex items-center gap-2 p-3 rounded-lg ${
            saveStatus.type === 'success'
              ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
              : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
          }`}
        >
          {saveStatus.type === 'success' ? (
            <CheckCircle className="h-5 w-5" />
          ) : (
            <AlertTriangle className="h-5 w-5" />
          )}
          {saveStatus.message}
        </div>
      )}

      {switchError && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
          <AlertTriangle className="h-5 w-5" />
          Mode switch error: {switchError}
        </div>
      )}

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex space-x-4">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {/* Risk Limits Tab */}
        {activeTab === 'risk' && (
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Configurable Risk Limits</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                These limits can be adjusted within the hard-coded maximums.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Max Risk Per Trade (%)
                    <span className="text-gray-400 ml-2">
                      (max: {constants?.max_risk_per_trade_percent}%)
                    </span>
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max={constants?.max_risk_per_trade_percent}
                    value={getCurrentValue('max_risk_per_trade_percent')}
                    onChange={e =>
                      handleSettingChange('max_risk_per_trade_percent', parseFloat(e.target.value))
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Max Daily Loss (%)
                    <span className="text-gray-400 ml-2">
                      (max: {constants?.max_daily_loss_percent}%)
                    </span>
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max={constants?.max_daily_loss_percent}
                    value={getCurrentValue('max_daily_loss_percent')}
                    onChange={e =>
                      handleSettingChange('max_daily_loss_percent', parseFloat(e.target.value))
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Emergency Drawdown (%)
                    <span className="text-gray-400 ml-2">
                      (max: {constants?.emergency_drawdown_percent}%)
                    </span>
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="5"
                    max={constants?.emergency_drawdown_percent}
                    value={getCurrentValue('emergency_drawdown_percent')}
                    onChange={e =>
                      handleSettingChange('emergency_drawdown_percent', parseFloat(e.target.value))
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Max Open Positions
                    <span className="text-gray-400 ml-2">(max: {constants?.max_open_positions})</span>
                  </label>
                  <input
                    type="number"
                    min="1"
                    max={constants?.max_open_positions}
                    value={getCurrentValue('max_open_positions')}
                    onChange={e =>
                      handleSettingChange('max_open_positions', parseInt(e.target.value))
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Max Trades Per Day
                    <span className="text-gray-400 ml-2">(max: {constants?.max_trades_per_day})</span>
                  </label>
                  <input
                    type="number"
                    min="1"
                    max={constants?.max_trades_per_day}
                    value={getCurrentValue('max_trades_per_day')}
                    onChange={e =>
                      handleSettingChange('max_trades_per_day', parseInt(e.target.value))
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                  />
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Lock className="h-5 w-5 text-red-500" />
                Hard-Coded Constants (Immutable)
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                These values cannot be modified. They represent absolute limits.
              </p>

              <div className="space-y-3 text-sm">
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Max Risk Per Trade</span>
                  <span className="font-mono">{constants?.max_risk_per_trade_percent}%</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Max Daily Loss</span>
                  <span className="font-mono">{constants?.max_daily_loss_percent}%</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Emergency Drawdown</span>
                  <span className="font-mono">{constants?.emergency_drawdown_percent}%</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Max Open Positions</span>
                  <span className="font-mono">{constants?.max_open_positions}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Max Trades Per Day</span>
                  <span className="font-mono">{constants?.max_trades_per_day}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Max Trades Per Hour</span>
                  <span className="font-mono">{constants?.max_trades_per_hour}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Min Risk/Reward Ratio</span>
                  <span className="font-mono">{constants?.min_risk_reward_ratio}:1</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-gray-600 dark:text-gray-400">Max Position Size</span>
                  <span className="font-mono">{constants?.max_position_size_percent}%</span>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Mode Tab */}
        {activeTab === 'mode' && (
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">System Mode</h3>

              <div className="space-y-4">
                <div
                  onClick={() => handleModeChange('guide')}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    mode === 'guide'
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-4 h-4 rounded-full border-2 ${
                        mode === 'guide'
                          ? 'border-blue-500 bg-blue-500'
                          : 'border-gray-400'
                      }`}
                    >
                      {mode === 'guide' && (
                        <div className="w-2 h-2 bg-white rounded-full m-0.5" />
                      )}
                    </div>
                    <div>
                      <h4 className="font-semibold">GUIDE Mode</h4>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        AI generates signals, user approves all actions
                      </p>
                    </div>
                  </div>
                </div>

                <div
                  onClick={() => handleModeChange('autonomous')}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    mode === 'autonomous'
                      ? 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-4 h-4 rounded-full border-2 ${
                        mode === 'autonomous'
                          ? 'border-yellow-500 bg-yellow-500'
                          : 'border-gray-400'
                      }`}
                    >
                      {mode === 'autonomous' && (
                        <div className="w-2 h-2 bg-white rounded-full m-0.5" />
                      )}
                    </div>
                    <div>
                      <h4 className="font-semibold">AUTONOMOUS Mode</h4>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        AI can execute trades automatically within limits
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Mode Transition Behavior</h3>

              <div className="space-y-4">
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={getCurrentValue('cancel_orders_on_mode_switch')}
                    onChange={e =>
                      handleSettingChange('cancel_orders_on_mode_switch', e.target.checked)
                    }
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <div>
                    <span className="font-medium">Cancel Orders on Mode Switch</span>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Cancel all pending orders when switching modes
                    </p>
                  </div>
                </label>

                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={getCurrentValue('require_confirmation_for_autonomous')}
                    onChange={e =>
                      handleSettingChange('require_confirmation_for_autonomous', e.target.checked)
                    }
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <div>
                    <span className="font-medium">Require Confirmation for Autonomous</span>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Show confirmation dialog before enabling autonomous mode
                    </p>
                  </div>
                </label>
              </div>

              <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <h4 className="font-medium mb-3">System Health Monitoring</h4>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Health Check Interval (seconds)
                    </label>
                    <input
                      type="number"
                      min="10"
                      max="300"
                      value={getCurrentValue('health_check_interval_seconds')}
                      onChange={e =>
                        handleSettingChange('health_check_interval_seconds', parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Agent Timeout (seconds)
                    </label>
                    <input
                      type="number"
                      min="10"
                      max="300"
                      value={getCurrentValue('agent_timeout_seconds')}
                      onChange={e =>
                        handleSettingChange('agent_timeout_seconds', parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                    />
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Strategy Tab */}
        {activeTab === 'strategy' && (
          <Card className="p-6 max-w-2xl">
            <h3 className="text-lg font-semibold mb-4">Strategy Management</h3>

            <div className="space-y-4">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={getCurrentValue('auto_disable_strategies')}
                  onChange={e =>
                    handleSettingChange('auto_disable_strategies', e.target.checked)
                  }
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <div>
                  <span className="font-medium">Auto-Disable Underperforming Strategies</span>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Automatically disable strategies after consecutive losses
                  </p>
                </div>
              </label>

              {getCurrentValue('auto_disable_strategies') && (
                <div className="ml-7">
                  <label className="block text-sm font-medium mb-1">
                    Consecutive Losses Threshold
                    <span className="text-gray-400 ml-2">
                      (max: {constants?.strategy_auto_disable_threshold})
                    </span>
                  </label>
                  <input
                    type="number"
                    min="1"
                    max={constants?.strategy_auto_disable_threshold}
                    value={getCurrentValue('strategy_disable_threshold')}
                    onChange={e =>
                      handleSettingChange('strategy_disable_threshold', parseInt(e.target.value))
                    }
                    className="w-full max-w-xs px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                  />
                </div>
              )}

              <div className="pt-6 border-t border-gray-200 dark:border-gray-700">
                <h4 className="font-medium mb-3">Broker Configuration</h4>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Broker Type</label>
                    <select
                      value={getCurrentValue('broker_type')}
                      onChange={e => handleSettingChange('broker_type', e.target.value)}
                      className="w-full max-w-xs px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                    >
                      <option value="paper">Paper Trading</option>
                      <option value="mt5">MetaTrader 5</option>
                      <option value="oanda">OANDA</option>
                      <option value="binance">Binance</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-sm">Broker Status:</span>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        settings?.broker_connected
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400'
                      }`}
                    >
                      {settings?.broker_connected ? 'Connected' : 'Disconnected'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* Notifications Tab */}
        {activeTab === 'notifications' && (
          <Card className="p-6 max-w-2xl">
            <h3 className="text-lg font-semibold mb-4">Notification Settings</h3>

            <div className="space-y-4">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={getCurrentValue('email_notifications_enabled')}
                  onChange={e =>
                    handleSettingChange('email_notifications_enabled', e.target.checked)
                  }
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <div>
                  <span className="font-medium">Enable Email Notifications</span>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Receive email alerts for important system events
                  </p>
                </div>
              </label>

              {getCurrentValue('email_notifications_enabled') && (
                <div className="ml-7">
                  <label className="block text-sm font-medium mb-1">Notification Email</label>
                  <input
                    type="email"
                    value={getCurrentValue('notification_email') || ''}
                    onChange={e => handleSettingChange('notification_email', e.target.value)}
                    placeholder="your@email.com"
                    className="w-full max-w-md px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                  />
                </div>
              )}

              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="flex items-start gap-2">
                  <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                  <div className="text-sm text-blue-800 dark:text-blue-300">
                    <strong>Note:</strong> Per-user notification preferences can be configured in your
                    user preferences. System notifications apply to all users.
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* Audit Tab */}
        {activeTab === 'audit' && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Settings Audit Trail</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Complete history of all settings changes for compliance and debugging.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-3 px-2">Version</th>
                    <th className="text-left py-3 px-2">Date</th>
                    <th className="text-left py-3 px-2">Type</th>
                    <th className="text-left py-3 px-2">Changes</th>
                    <th className="text-left py-3 px-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {auditTrail?.map((entry: AuditEntry) => (
                    <tr
                      key={entry.id}
                      className="border-b border-gray-100 dark:border-gray-800"
                    >
                      <td className="py-3 px-2 font-mono">v{entry.settings_version}</td>
                      <td className="py-3 px-2 text-gray-500">
                        {new Date(entry.changed_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-2">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            entry.change_type === 'mode_change'
                              ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                              : entry.change_type === 'risk_update'
                              ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400'
                          }`}
                        >
                          {entry.change_type}
                        </span>
                      </td>
                      <td className="py-3 px-2 font-mono text-xs">
                        {Object.keys(entry.new_value).join(', ')}
                      </td>
                      <td className="py-3 px-2 text-gray-500 max-w-xs truncate">
                        {entry.reason || '-'}
                      </td>
                    </tr>
                  ))}
                  {(!auditTrail || auditTrail.length === 0) && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-gray-500">
                        No audit entries yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Save Bar */}
        {hasChanges && activeTab !== 'audit' && (
          <div className="sticky bottom-4 p-4 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1 max-w-md">
                <input
                  type="text"
                  value={saveReason}
                  onChange={e => setSaveReason(e.target.value)}
                  placeholder="Reason for change (optional)"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={discardChanges}>
                  Discard
                </Button>
                <Button
                  onClick={saveSettings}
                  disabled={updateSettingsMutation.isPending}
                >
                  {updateSettingsMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
