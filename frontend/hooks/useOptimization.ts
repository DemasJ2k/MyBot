'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { OptimizationQueryParams } from '@/types';

export function useOptimizationJobs(params?: OptimizationQueryParams) {
  return useQuery({
    queryKey: ['optimization-jobs', params],
    queryFn: () => apiClient.getOptimizationJobs(params),
  });
}

export function useOptimizationJob(jobId: number | null) {
  return useQuery({
    queryKey: ['optimization-job', jobId],
    queryFn: () => apiClient.getOptimizationJob(jobId!),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      // Refetch every 5 seconds if job is still running
      const data = query.state.data;
      if (data && data.status === 'running') {
        return 5000;
      }
      return false;
    },
  });
}

export function useCreateOptimizationJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      strategy_name: string;
      symbol: string;
      interval: string;
      start_date: string;
      end_date: string;
      parameter_space: Record<string, unknown>;
      optimization_target?: string;
      n_trials?: number;
    }) => apiClient.createOptimizationJob(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['optimization-jobs'] });
    },
  });
}

export function usePlaybooks(params?: { strategy_name?: string; symbol?: string; is_active?: boolean; limit?: number }) {
  return useQuery({
    queryKey: ['playbooks', params],
    queryFn: () => apiClient.getPlaybooks(params),
  });
}

export function useCreatePlaybook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ jobId, name, notes }: { jobId: number; name: string; notes?: string }) =>
      apiClient.createPlaybook(jobId, name, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] });
    },
  });
}

export function useActivatePlaybook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (playbookId: number) => apiClient.activatePlaybook(playbookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] });
    },
  });
}

export function useDeactivatePlaybook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (playbookId: number) => apiClient.deactivatePlaybook(playbookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] });
    },
  });
}
