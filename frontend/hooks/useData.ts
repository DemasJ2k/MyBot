'use client';

import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

export function useCandles(symbol: string, interval: string, limit?: number) {
  return useQuery({
    queryKey: ['candles', symbol, interval, limit],
    queryFn: () => apiClient.getCandles(symbol, interval, limit),
    enabled: !!symbol && !!interval,
    refetchInterval: 60000, // Refresh every minute
  });
}

export function useQuote(symbol: string) {
  return useQuery({
    queryKey: ['quote', symbol],
    queryFn: () => apiClient.getQuote(symbol),
    enabled: !!symbol,
    refetchInterval: 5000, // Refresh every 5 seconds
  });
}

export function useSearchSymbols(query: string) {
  return useQuery({
    queryKey: ['symbol-search', query],
    queryFn: () => apiClient.searchSymbols(query),
    enabled: query.length >= 2,
  });
}

export function useSyncCandles() {
  return useMutation({
    mutationFn: ({
      symbol,
      interval,
      startDate,
      endDate,
    }: {
      symbol: string;
      interval: string;
      startDate?: string;
      endDate?: string;
    }) => apiClient.syncCandles(symbol, interval, startDate, endDate),
  });
}
