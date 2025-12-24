'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { BacktestQueryParams, BacktestRequest } from '@/types';

export function useBacktestResults(params?: BacktestQueryParams) {
  return useQuery({
    queryKey: ['backtest-results', params],
    queryFn: () => apiClient.getBacktestResults(params),
  });
}

export function useBacktestDetail(backtestId: number | null) {
  return useQuery({
    queryKey: ['backtest', backtestId],
    queryFn: () => apiClient.getBacktestDetail(backtestId!),
    enabled: backtestId !== null,
  });
}

export function useRunBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BacktestRequest) => apiClient.runBacktest(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-results'] });
    },
  });
}
