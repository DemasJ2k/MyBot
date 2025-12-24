'use client';

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

export function useAIDecisions(params?: { agent_role?: string; limit?: number }) {
  return useQuery({
    queryKey: ['ai-decisions', params],
    queryFn: () => apiClient.getAIDecisions(params),
  });
}

export function useAgentMemory(params?: { agent_role?: string; memory_type?: string }) {
  return useQuery({
    queryKey: ['agent-memory', params],
    queryFn: () => apiClient.getAgentMemory(params),
  });
}

export function useCoordinatorState() {
  return useQuery({
    queryKey: ['coordinator-state'],
    queryFn: () => apiClient.getCoordinatorState(),
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}
