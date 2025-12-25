'use client';

import { useState } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useStrategies, useAnalyzeSymbol } from '@/hooks/useStrategies';
import { usePlaybooks, useActivatePlaybook, useDeactivatePlaybook } from '@/hooks/useOptimization';
import { Strategy, Playbook } from '@/types';
import { cn, snakeToTitle } from '@/lib/utils';
import {
  LineChart,
  Settings2,
  Play,
  Pause,
  RefreshCw,
  CheckCircle,
  XCircle,
} from 'lucide-react';

export default function StrategiesPage() {
  const { data: strategies, isLoading: strategiesLoading, refetch: refetchStrategies } = useStrategies();
  const { data: playbooks, isLoading: playbooksLoading } = usePlaybooks();
  const analyzeSymbol = useAnalyzeSymbol();
  const activatePlaybook = useActivatePlaybook();
  const deactivatePlaybook = useDeactivatePlaybook();

  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [analyzeSymbolInput, setAnalyzeSymbolInput] = useState('');

  const handleAnalyze = (strategyName: string) => {
    if (!analyzeSymbolInput.trim()) return;
    analyzeSymbol.mutate({
      symbol: analyzeSymbolInput.toUpperCase(),
      strategyName,
    });
  };

  const handleTogglePlaybook = (playbook: Playbook) => {
    if (playbook.is_active) {
      deactivatePlaybook.mutate(playbook.id);
    } else {
      activatePlaybook.mutate(playbook.id);
    }
  };

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Strategies"
        description="Manage and configure trading strategies"
      >
        {/* Strategy Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {strategiesLoading ? (
            [1, 2, 3].map((i) => (
              <Card key={i} className="animate-pulse">
                <CardHeader>
                  <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4" />
                  <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mt-2" />
                </CardHeader>
                <CardContent>
                  <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded" />
                </CardContent>
              </Card>
            ))
          ) : strategies && strategies.length > 0 ? (
            strategies.map((strategy: Strategy) => (
              <Card
                key={strategy.name}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-lg',
                  selectedStrategy === strategy.name && 'ring-2 ring-blue-500'
                )}
                onClick={() => setSelectedStrategy(
                  selectedStrategy === strategy.name ? null : strategy.name
                )}
              >
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <LineChart className="h-5 w-5 text-blue-500" />
                      <CardTitle className="text-lg">{snakeToTitle(strategy.name)}</CardTitle>
                    </div>
                    <Badge variant="secondary">
                      <Settings2 className="h-3 w-3 mr-1" />
                      Configurable
                    </Badge>
                  </div>
                  <CardDescription>
                    {strategy.description || 'No description available'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Parameters:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {Object.keys(strategy.config || {}).slice(0, 5).map((key) => (
                        <Badge key={key} variant="outline" className="text-xs">
                          {snakeToTitle(key)}
                        </Badge>
                      ))}
                      {Object.keys(strategy.config || {}).length > 5 && (
                        <Badge variant="outline" className="text-xs">
                          +{Object.keys(strategy.config).length - 5} more
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <Card className="col-span-full">
              <CardContent className="py-12 text-center">
                <LineChart className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-500">No strategies configured yet</p>
                <p className="text-sm text-gray-400 mt-2">
                  Strategies are loaded from the backend configuration
                </p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Analyze Symbol Section */}
        {selectedStrategy && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Analyze Symbol with {snakeToTitle(selectedStrategy)}</CardTitle>
              <CardDescription>
                Generate a trading signal for a specific symbol
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4">
                <input
                  type="text"
                  placeholder="Enter symbol (e.g., AAPL)"
                  value={analyzeSymbolInput}
                  onChange={(e) => setAnalyzeSymbolInput(e.target.value)}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <Button
                  onClick={() => handleAnalyze(selectedStrategy)}
                  disabled={analyzeSymbol.isPending || !analyzeSymbolInput.trim()}
                >
                  {analyzeSymbol.isPending ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4 mr-2" />
                  )}
                  Analyze
                </Button>
              </div>
              {analyzeSymbol.isSuccess && (
                <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                  <div className="flex items-center gap-2 text-green-700 dark:text-green-400">
                    <CheckCircle className="h-5 w-5" />
                    <span className="font-medium">Signal generated successfully!</span>
                  </div>
                </div>
              )}
              {analyzeSymbol.isError && (
                <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
                    <XCircle className="h-5 w-5" />
                    <span className="font-medium">Failed to generate signal</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Active Playbooks */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Active Playbooks</CardTitle>
              <CardDescription>
                Optimized strategy configurations saved from optimization runs
              </CardDescription>
            </div>
            <Button variant="outline" onClick={() => refetchStrategies()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </CardHeader>
          <CardContent>
            {playbooksLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : playbooks && playbooks.length > 0 ? (
              <div className="space-y-4">
                {playbooks.map((playbook: Playbook) => (
                  <div
                    key={playbook.id}
                    className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={cn(
                          'h-3 w-3 rounded-full',
                          playbook.is_active ? 'bg-green-500' : 'bg-gray-400'
                        )}
                      />
                      <div>
                        <p className="font-medium">{playbook.name}</p>
                        <p className="text-sm text-gray-500">
                          {snakeToTitle(playbook.strategy_name)} • {playbook.symbol}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <Badge variant={playbook.is_active ? 'success' : 'secondary'}>
                          {playbook.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      <Button
                        variant={playbook.is_active ? 'destructive' : 'default'}
                        size="sm"
                        onClick={() => handleTogglePlaybook(playbook)}
                        disabled={activatePlaybook.isPending || deactivatePlaybook.isPending}
                      >
                        {playbook.is_active ? (
                          <>
                            <Pause className="h-4 w-4 mr-1" />
                            Deactivate
                          </>
                        ) : (
                          <>
                            <Play className="h-4 w-4 mr-1" />
                            Activate
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">
                No playbooks saved yet. Run optimization to create playbooks.
              </p>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
