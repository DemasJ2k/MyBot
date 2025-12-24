'use client';

import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

export function useRiskState() {
  return useQuery({
    queryKey: ['risk-state'],
    queryFn: () => apiClient.getRiskState(),
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}

export function useRiskDecisions(limit = 50) {
  return useQuery({
    queryKey: ['risk-decisions', limit],
    queryFn: () => apiClient.getRiskDecisions(limit),
  });
}

export function useRiskLimits() {
  return useQuery({
    queryKey: ['risk-limits'],
    queryFn: () => apiClient.getRiskLimits(),
  });
}

export function useValidateTrade() {
  return useMutation({
    mutationFn: (data: {
      symbol: string;
      side: string;
      quantity: number;
      entry_price: number;
      stop_loss: number;
    }) => apiClient.validateTrade(data),
  });
}
