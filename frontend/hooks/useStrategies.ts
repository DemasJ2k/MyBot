'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { SignalQueryParams } from '@/types';

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiClient.listStrategies(),
  });
}

export function useSignals(params?: SignalQueryParams) {
  return useQuery({
    queryKey: ['signals', params],
    queryFn: () => apiClient.getSignals(params),
    refetchInterval: 5000, // Refresh every 5 seconds
  });
}

export function useAnalyzeSymbol() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      symbol,
      strategyName,
      interval,
    }: {
      symbol: string;
      strategyName?: string;
      interval?: string;
    }) => apiClient.analyzeSymbol(symbol, strategyName, interval),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

export function useCancelSignal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (signalId: number) => apiClient.cancelSignal(signalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}
