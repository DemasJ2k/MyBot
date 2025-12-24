'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { JournalQueryParams } from '@/types';

export function useJournalEntries(params?: JournalQueryParams) {
  return useQuery({
    queryKey: ['journal-entries', params],
    queryFn: () => apiClient.getJournalEntries(params),
  });
}

export function useJournalEntry(entryId: string | null) {
  return useQuery({
    queryKey: ['journal-entry', entryId],
    queryFn: () => apiClient.getJournalEntry(entryId!),
    enabled: entryId !== null,
  });
}

export function useJournalStats(params?: { strategy_name?: string; symbol?: string }) {
  return useQuery({
    queryKey: ['journal-stats', params],
    queryFn: () => apiClient.getJournalStats(params),
  });
}

export function useStrategyAnalysis(strategyName: string, symbol: string, lookbackDays = 30) {
  return useQuery({
    queryKey: ['strategy-analysis', strategyName, symbol, lookbackDays],
    queryFn: () => apiClient.analyzeStrategy(strategyName, symbol, lookbackDays),
    enabled: !!strategyName && !!symbol,
  });
}

export function useUnderperformanceCheck(strategyName: string, symbol: string) {
  return useQuery({
    queryKey: ['underperformance', strategyName, symbol],
    queryFn: () => apiClient.detectUnderperformance(strategyName, symbol),
    enabled: !!strategyName && !!symbol,
  });
}

export function useRunFeedbackCycle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ strategyName, symbol }: { strategyName: string; symbol: string }) =>
      apiClient.runFeedbackCycle(strategyName, symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategy-analysis'] });
      queryClient.invalidateQueries({ queryKey: ['underperformance'] });
      queryClient.invalidateQueries({ queryKey: ['performance-snapshots'] });
    },
  });
}

export function usePerformanceSnapshots(params?: { strategy_name?: string; symbol?: string; limit?: number }) {
  return useQuery({
    queryKey: ['performance-snapshots', params],
    queryFn: () => apiClient.getPerformanceSnapshots(params),
  });
}
