'use client';

import { useMode } from '@/providers/ModeProvider';
import { Shield, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ModeIndicatorProps {
  showLabel?: boolean;
  className?: string;
}

export function ModeIndicator({ showLabel = true, className }: ModeIndicatorProps) {
  const { mode, isLoading } = useMode();

  if (isLoading) {
    return <div className="animate-pulse h-6 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>;
  }

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium',
        mode === 'guide'
          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
          : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
        className
      )}
    >
      {mode === 'guide' ? <Shield className="h-4 w-4" /> : <Zap className="h-4 w-4" />}
      {showLabel && <span className="uppercase">{mode}</span>}
    </div>
  );
}

interface ModeSwitchProps {
  className?: string;
}

export function ModeSwitch({ className }: ModeSwitchProps) {
  const { mode, setMode, isLoading } = useMode();

  const handleToggle = async () => {
    const newMode = mode === 'guide' ? 'autonomous' : 'guide';
    try {
      await setMode(newMode);
    } catch (error) {
      console.error('Failed to switch mode:', error);
    }
  };

  return (
    <button
      onClick={handleToggle}
      disabled={isLoading}
      className={cn(
        'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
        mode === 'guide'
          ? 'bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:hover:bg-blue-800'
          : 'bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-900 dark:text-green-200 dark:hover:bg-green-800',
        isLoading && 'opacity-50 cursor-not-allowed',
        className
      )}
    >
      {mode === 'guide' ? (
        <>
          <Shield className="h-4 w-4" />
          <span>GUIDE</span>
        </>
      ) : (
        <>
          <Zap className="h-4 w-4" />
          <span>AUTONOMOUS</span>
        </>
      )}
    </button>
  );
}

interface ModeWarningProps {
  className?: string;
}

export function ModeWarning({ className }: ModeWarningProps) {
  const { mode } = useMode();

  if (mode === 'guide') {
    return null;
  }

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-4 py-2 bg-yellow-100 text-yellow-800 rounded-lg dark:bg-yellow-900 dark:text-yellow-200',
        className
      )}
    >
      <Zap className="h-5 w-5" />
      <span className="font-medium">AUTONOMOUS MODE</span>
      <span className="text-sm">- Trades will be executed automatically</span>
    </div>
  );
}
