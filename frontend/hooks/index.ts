// Auth hooks
export { useAuth } from './useAuth';

// Data fetching hooks
export { useStrategies, useSignals, useAnalyzeSymbol, useCancelSignal } from './useStrategies';
export { useBacktestResults, useBacktestDetail, useRunBacktest } from './useBacktest';
export {
  useOptimizationJobs,
  useOptimizationJob,
  useCreateOptimizationJob,
  usePlaybooks,
  useCreatePlaybook,
  useActivatePlaybook,
  useDeactivatePlaybook,
} from './useOptimization';
export {
  useJournalEntries,
  useJournalEntry,
  useJournalStats,
  useStrategyAnalysis,
  useUnderperformanceCheck,
  useRunFeedbackCycle,
  usePerformanceSnapshots,
} from './useJournal';
export {
  useExecutionMode,
  useSetExecutionMode,
  useOrders,
  useOrder,
  useExecuteSignal,
  useCancelOrder,
  useBrokers,
} from './useExecution';
export { useRiskState, useRiskDecisions, useRiskLimits, useValidateTrade } from './useRisk';
export { useAIDecisions, useAgentMemory, useCoordinatorState } from './useAI';
export { useCandles, useQuote, useSearchSymbols, useSyncCandles } from './useData';
