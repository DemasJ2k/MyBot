'use client';

import { useState, useMemo, useRef, useEffect } from 'react';
import { Sidebar, PageContainer } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAIDecisions, useAgentMemory, useCoordinatorState } from '@/hooks/useAI';
import { useMode } from '@/providers/ModeProvider';
import { AIDecision } from '@/types';
import { formatDate, getRelativeTime, snakeToTitle } from '@/lib/utils';
import {
  Bot,
  Brain,
  MessageSquare,
  RefreshCw,
  Send,
  User,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  Clock,
  AlertCircle,
  Cpu,
  Target,
  TrendingUp,
  Shield,
} from 'lucide-react';

interface AgentInfo {
  role: string;
  status: 'active' | 'idle' | 'working';
  lastAction?: string;
  icon: React.ReactNode;
  color: string;
}

const AGENTS: AgentInfo[] = [
  { role: 'coordinator', status: 'active', icon: <Cpu className="h-5 w-5" />, color: 'blue' },
  { role: 'analyst', status: 'idle', icon: <Brain className="h-5 w-5" />, color: 'purple' },
  { role: 'executor', status: 'idle', icon: <Target className="h-5 w-5" />, color: 'green' },
  { role: 'risk_manager', status: 'idle', icon: <Shield className="h-5 w-5" />, color: 'red' },
  { role: 'portfolio', status: 'idle', icon: <TrendingUp className="h-5 w-5" />, color: 'orange' },
];

export default function AIChatPage() {
  const { mode } = useMode();
  const { data: decisions, isLoading: decisionsLoading, refetch: refetchDecisions } = useAIDecisions({ limit: 50 });
  const { data: coordinatorState, refetch: refetchState } = useCoordinatorState();
  const { data: agentMemory } = useAgentMemory();

  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [expandedDecision, setExpandedDecision] = useState<number | null>(null);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [decisions]);

  // Filter decisions by agent
  const filteredDecisions = useMemo(() => {
    if (!decisions) return [];
    if (!selectedAgent) return decisions;
    return decisions.filter((d: AIDecision) => d.agent_role === selectedAgent);
  }, [decisions, selectedAgent]);

  // Agent status from coordinator
  const agentStatus = useMemo(() => {
    if (!coordinatorState) return {};
    return coordinatorState.agent_status || {};
  }, [coordinatorState]);

  // Stats
  const stats = useMemo(() => {
    if (!decisions || decisions.length === 0) return { total: 0, executed: 0, pending: 0 };
    const executed = decisions.filter((d: AIDecision) => d.executed).length;
    return {
      total: decisions.length,
      executed,
      pending: decisions.length - executed,
    };
  }, [decisions]);

  const handleSendMessage = () => {
    // In a real implementation, this would send to the AI agent API
    if (!chatInput.trim()) return;
    console.log('Sending message:', chatInput);
    setChatInput('');
    // Refetch decisions to see any new responses
    refetchDecisions();
  };

  const getAgentColor = (role: string) => {
    const colors: Record<string, string> = {
      coordinator: 'blue',
      analyst: 'purple',
      executor: 'green',
      risk_manager: 'red',
      portfolio: 'orange',
    };
    return colors[role] || 'gray';
  };

  const getAgentBgClass = (role: string) => {
    const color = getAgentColor(role);
    return `bg-${color}-100 dark:bg-${color}-900/30`;
  };

  const handleRefresh = () => {
    refetchDecisions();
    refetchState();
  };

  return (
    <>
      <Sidebar />
      <PageContainer
        title="AI Assistant"
        description="Interact with AI trading agents"
      >
        {/* Agent Status Overview */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          {AGENTS.map((agent) => {
            const status = agentStatus[agent.role] || agent.status;
            const isSelected = selectedAgent === agent.role;
            
            return (
              <Card
                key={agent.role}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  isSelected ? 'ring-2 ring-blue-500' : ''
                }`}
                onClick={() => setSelectedAgent(isSelected ? null : agent.role)}
              >
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg bg-${agent.color}-100 dark:bg-${agent.color}-900/30 text-${agent.color}-600 dark:text-${agent.color}-400`}>
                      {agent.icon}
                    </div>
                    <div>
                      <p className="font-medium text-sm">{snakeToTitle(agent.role)}</p>
                      <div className="flex items-center gap-1">
                        <div className={`h-2 w-2 rounded-full ${
                          status === 'active' ? 'bg-green-500' :
                          status === 'working' ? 'bg-yellow-500 animate-pulse' :
                          'bg-gray-400'
                        }`} />
                        <span className="text-xs text-gray-500">{snakeToTitle(status)}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Decision Feed */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Bot className="h-5 w-5 text-blue-500" />
                    AI Decisions
                    {selectedAgent && (
                      <Badge variant="secondary" className="ml-2">
                        {snakeToTitle(selectedAgent)}
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription>
                    Real-time decisions from AI trading agents
                  </CardDescription>
                </div>
                <Button variant="outline" onClick={handleRefresh}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </CardHeader>
              <CardContent>
                {decisionsLoading ? (
                  <div className="animate-pulse space-y-4">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded" />
                    ))}
                  </div>
                ) : filteredDecisions.length > 0 ? (
                  <div className="space-y-3 max-h-[600px] overflow-y-auto">
                    {filteredDecisions.map((decision: AIDecision) => (
                      <div
                        key={decision.id}
                        className="border dark:border-gray-700 rounded-lg overflow-hidden"
                      >
                        <div
                          className="flex items-start gap-3 p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                          onClick={() => setExpandedDecision(
                            expandedDecision === decision.id ? null : decision.id
                          )}
                        >
                          <div className={`p-2 rounded-lg bg-${getAgentColor(decision.agent_role)}-100 dark:bg-${getAgentColor(decision.agent_role)}-900/30`}>
                            <Bot className={`h-4 w-4 text-${getAgentColor(decision.agent_role)}-600`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium">{snakeToTitle(decision.agent_role)}</span>
                              <Badge variant="outline" className="text-xs">
                                {snakeToTitle(decision.decision_type)}
                              </Badge>
                              {decision.executed ? (
                                <CheckCircle className="h-4 w-4 text-green-500" />
                              ) : (
                                <Clock className="h-4 w-4 text-yellow-500" />
                              )}
                            </div>
                            <p className="text-sm text-gray-700 dark:text-gray-300 truncate">
                              {decision.decision}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              {getRelativeTime(decision.decision_time)}
                            </p>
                          </div>
                          {expandedDecision === decision.id ? (
                            <ChevronDown className="h-4 w-4 text-gray-500" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-gray-500" />
                          )}
                        </div>

                        {expandedDecision === decision.id && (
                          <div className="p-4 bg-gray-50 dark:bg-gray-800 border-t dark:border-gray-700">
                            <div className="mb-3">
                              <p className="text-xs text-gray-500 uppercase mb-1">Decision</p>
                              <p className="text-sm">{decision.decision}</p>
                            </div>
                            <div className="mb-3">
                              <p className="text-xs text-gray-500 uppercase mb-1">Reasoning</p>
                              <p className="text-sm text-gray-600 dark:text-gray-400">
                                {decision.reasoning || 'No reasoning provided'}
                              </p>
                            </div>
                            {decision.context && Object.keys(decision.context).length > 0 && (
                              <div>
                                <p className="text-xs text-gray-500 uppercase mb-1">Context</p>
                                <div className="bg-gray-100 dark:bg-gray-900 rounded p-2 text-xs font-mono overflow-x-auto">
                                  <pre>{JSON.stringify(decision.context, null, 2)}</pre>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                    <div ref={chatEndRef} />
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Bot className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                    <p className="text-gray-500">No AI decisions yet</p>
                    <p className="text-sm text-gray-400 mt-2">
                      AI agents will make decisions based on market conditions and strategy rules
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sidebar - Stats and Memory */}
          <div className="space-y-6">
            {/* Decision Stats */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Decision Stats</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Total Decisions</span>
                    <span className="font-bold">{stats.total}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Executed</span>
                    <span className="font-bold text-green-600">{stats.executed}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Pending</span>
                    <span className="font-bold text-yellow-600">{stats.pending}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Mode Awareness */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Current Mode</CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`p-4 rounded-lg ${
                  mode === 'guide'
                    ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                    : 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                }`}>
                  <div className="flex items-center gap-3">
                    {mode === 'guide' ? (
                      <Shield className="h-6 w-6 text-blue-600" />
                    ) : (
                      <Bot className="h-6 w-6 text-green-600" />
                    )}
                    <div>
                      <p className="font-bold">{mode === 'guide' ? 'GUIDE' : 'AUTONOMOUS'}</p>
                      <p className="text-xs text-gray-500">
                        {mode === 'guide'
                          ? 'AI suggests, you decide'
                          : 'AI executes automatically'
                        }
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Agent Memory */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Agent Memory</CardTitle>
                <CardDescription>Recent learnings and patterns</CardDescription>
              </CardHeader>
              <CardContent>
                {agentMemory && agentMemory.length > 0 ? (
                  <div className="space-y-3">
                    {agentMemory.slice(0, 5).map((memory: { id: number; memory_type: string; content: string }, idx: number) => (
                      <div key={idx} className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
                        <Badge variant="outline" className="text-xs mb-1">
                          {snakeToTitle(memory.memory_type)}
                        </Badge>
                        <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                          {memory.content}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 text-center py-4">
                    No memories recorded yet
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Chat Input - Future Feature */}
        <Card className="mt-6">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Ask the AI about trading decisions, strategies, or analysis... (Coming soon)"
                  className="w-full px-4 py-3 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled
                />
                <MessageSquare className="absolute right-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              </div>
              <Button disabled>
                <Send className="h-4 w-4 mr-2" />
                Send
              </Button>
            </div>
            <p className="text-xs text-gray-500 mt-2 text-center">
              Interactive AI chat coming in a future update
            </p>
          </CardContent>
        </Card>
      </PageContainer>
    </>
  );
}
