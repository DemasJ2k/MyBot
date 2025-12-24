'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

export function useExecutionMode() {
  return useQuery({
    queryKey: ['execution-mode'],
    queryFn: () => apiClient.getExecutionMode(),
  });
}

export function useSetExecutionMode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (mode: 'guide' | 'autonomous') => apiClient.setExecutionMode(mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['execution-mode'] });
    },
  });
}

export function useOrders(params?: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: ['orders', params],
    queryFn: () => apiClient.getOrders(params),
    refetchInterval: 5000, // Refresh every 5 seconds
  });
}

export function useOrder(orderId: number | null) {
  return useQuery({
    queryKey: ['order', orderId],
    queryFn: () => apiClient.getOrder(orderId!),
    enabled: orderId !== null,
  });
}

export function useExecuteSignal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      signalId,
      positionSize,
      brokerType = 'paper',
    }: {
      signalId: number;
      positionSize: number;
      brokerType?: string;
    }) => apiClient.executeSignal(signalId, positionSize, brokerType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (orderId: number) => apiClient.cancelOrder(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });
}

export function useBrokers() {
  return useQuery({
    queryKey: ['brokers'],
    queryFn: () => apiClient.getBrokers(),
  });
}
