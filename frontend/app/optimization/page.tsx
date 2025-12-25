'use client';

import { useState } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useStrategies } from '@/hooks/useStrategies';
import {
  useOptimizationJobs,
  useOptimizationJob,
  useCreateOptimizationJob,
  usePlaybooks,
  useCreatePlaybook,
} from '@/hooks/useOptimization';
import { OptimizationJob, Strategy, Playbook } from '@/types';
import { formatShortDate, getRelativeTime, snakeToTitle, cn } from '@/lib/utils';
import {
  Settings2,
  Play,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Save,
  Loader2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

export default function OptimizationPage() {
  const { data: strategies } = useStrategies();
  const { data: jobs, isLoading: jobsLoading, refetch: refetchJobs } = useOptimizationJobs({ limit: 20 });
  const createJob = useCreateOptimizationJob();
  const { data: playbooks } = usePlaybooks();
  const createPlaybook = useCreatePlaybook();

  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const { data: selectedJob } = useOptimizationJob(selectedJobId);

  const [playbookName, setPlaybookName] = useState('');
  const [expandedJob, setExpandedJob] = useState<number | null>(null);

  const [formData, setFormData] = useState({
    strategy_name: '',
    symbol: '',
    interval: '1d',
    start_date: '',
    end_date: '',
    optimization_target: 'sharpe_ratio',
    n_trials: 50,
  });

  // Default parameter space - would be customizable in a full implementation
  const defaultParameterSpace = {
    sma_fast: { low: 5, high: 20 },
    sma_slow: { low: 30, high: 100 },
    rsi_period: { low: 10, high: 20 },
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const value = e.target.type === 'number' ? Number(e.target.value) : e.target.value;
    setFormData({ ...formData, [e.target.name]: value });
  };

  const handleCreateJob = () => {
    if (!formData.strategy_name || !formData.symbol || !formData.start_date || !formData.end_date) {
      return;
    }
    createJob.mutate({
      ...formData,
      parameter_space: defaultParameterSpace,
    });
  };

  const handleSavePlaybook = (jobId: number) => {
    if (!playbookName.trim()) return;
    createPlaybook.mutate({
      jobId,
      name: playbookName,
    });
    setPlaybookName('');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success"><CheckCircle className="h-3 w-3 mr-1" /> Completed</Badge>;
      case 'running':
        return <Badge variant="warning"><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Running</Badge>;
      case 'failed':
        return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" /> Failed</Badge>;
      default:
        return <Badge variant="secondary"><Clock className="h-3 w-3 mr-1" /> {status}</Badge>;
    }
  };

  return (
    <>
      <Sidebar />
      <PageContainer
        title="Optimization"
        description="Optimize strategy parameters using historical data"
      >
        {/* Create Optimization Job */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-orange-500" />
              New Optimization Job
            </CardTitle>
            <CardDescription>
              Find optimal parameters for a strategy using Bayesian optimization
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
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
                <label className="block text-sm font-medium mb-1">Optimization Target</label>
                <select
                  name="optimization_target"
                  value={formData.optimization_target}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="sharpe_ratio">Sharpe Ratio</option>
                  <option value="total_return">Total Return</option>
                  <option value="profit_factor">Profit Factor</option>
                  <option value="win_rate">Win Rate</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Number of Trials</label>
                <input
                  type="number"
                  name="n_trials"
                  value={formData.n_trials}
                  onChange={handleInputChange}
                  min={10}
                  max={200}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <Button
              onClick={handleCreateJob}
              disabled={createJob.isPending || !formData.strategy_name || !formData.symbol}
            >
              {createJob.isPending ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Start Optimization
            </Button>
          </CardContent>
        </Card>

        {/* Optimization Jobs List */}
        <Card className="mb-8">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Optimization Jobs</CardTitle>
              <CardDescription>View and manage optimization runs</CardDescription>
            </div>
            <Button variant="outline" onClick={() => refetchJobs()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </CardHeader>
          <CardContent>
            {jobsLoading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded" />
                ))}
              </div>
            ) : jobs && jobs.length > 0 ? (
              <div className="space-y-4">
                {jobs.map((job: OptimizationJob) => (
                  <div
                    key={job.id}
                    className="border dark:border-gray-700 rounded-lg overflow-hidden"
                  >
                    <div
                      className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-750"
                      onClick={() => {
                        setExpandedJob(expandedJob === job.id ? null : job.id);
                        if (job.status === 'completed') {
                          setSelectedJobId(job.id);
                        }
                      }}
                    >
                      <div className="flex items-center gap-4">
                        {expandedJob === job.id ? (
                          <ChevronDown className="h-4 w-4 text-gray-500" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-gray-500" />
                        )}
                        <div>
                          <p className="font-medium">
                            {snakeToTitle(job.strategy_name)} - {job.symbol}
                          </p>
                          <p className="text-sm text-gray-500">
                            Created {getRelativeTime(job.created_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {getStatusBadge(job.status)}
                        {job.best_score !== null && (
                          <span className="text-sm font-medium">
                            Best: {job.best_score.toFixed(4)}
                          </span>
                        )}
                      </div>
                    </div>

                    {expandedJob === job.id && job.status === 'completed' && job.best_params && (
                      <div className="p-4 border-t dark:border-gray-700">
                        <h4 className="font-medium mb-3">Best Parameters</h4>
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-4">
                          {Object.entries(job.best_params).map(([key, value]) => (
                            <div
                              key={key}
                              className="p-3 bg-gray-100 dark:bg-gray-800 rounded"
                            >
                              <p className="text-xs text-gray-500 uppercase">{snakeToTitle(key)}</p>
                              <p className="font-medium">{String(value)}</p>
                            </div>
                          ))}
                        </div>

                        {/* Save as Playbook */}
                        <div className="flex gap-3 mt-4 pt-4 border-t dark:border-gray-700">
                          <input
                            type="text"
                            value={playbookName}
                            onChange={(e) => setPlaybookName(e.target.value)}
                            placeholder="Playbook name..."
                            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <Button
                            onClick={() => handleSavePlaybook(job.id)}
                            disabled={createPlaybook.isPending || !playbookName.trim()}
                          >
                            <Save className="h-4 w-4 mr-2" />
                            Save Playbook
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">
                No optimization jobs yet. Start your first optimization above.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Saved Playbooks */}
        <Card>
          <CardHeader>
            <CardTitle>Saved Playbooks</CardTitle>
            <CardDescription>
              Optimized parameter sets ready for trading
            </CardDescription>
          </CardHeader>
          <CardContent>
            {playbooks && playbooks.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {playbooks.map((playbook: Playbook) => (
                  <div
                    key={playbook.id}
                    className={cn(
                      'p-4 border rounded-lg',
                      playbook.is_active
                        ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                        : 'border-gray-200 dark:border-gray-700'
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium">{playbook.name}</h4>
                      {playbook.is_active && (
                        <Badge variant="success">Active</Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mb-2">
                      {snakeToTitle(playbook.strategy_name)} • {playbook.symbol}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(playbook.parameters || {}).slice(0, 3).map(([key, value]) => (
                        <Badge key={key} variant="outline" className="text-xs">
                          {snakeToTitle(key)}: {String(value)}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">
                No playbooks saved yet. Complete an optimization and save the results.
              </p>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
