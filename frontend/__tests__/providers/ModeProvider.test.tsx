import React from 'react';
import { render, screen } from '@testing-library/react';
import { ModeProvider, useMode } from '@/providers/ModeProvider';

// Mock API client
jest.mock('@/services/api', () => ({
  apiClient: {
    getSystemMode: jest.fn().mockResolvedValue({ mode: 'guide' }),
    setSystemMode: jest.fn().mockResolvedValue({ mode: 'autonomous' }),
  },
}));

// Test component to access the hook
function TestComponent() {
  const { mode, isLoading, error } = useMode();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="loading">{isLoading ? 'loading' : 'loaded'}</span>
      <span data-testid="error">{error || 'no-error'}</span>
    </div>
  );
}

describe('ModeProvider', () => {
  it('provides mode context to children', async () => {
    render(
      <ModeProvider>
        <TestComponent />
      </ModeProvider>
    );

    // Should show loading initially
    expect(screen.getByTestId('loading')).toHaveTextContent('loading');

    // Wait for mode to load
    await screen.findByText('loaded');
    expect(screen.getByTestId('mode')).toHaveTextContent('guide');
  });

  it('throws error when useMode is used outside provider', () => {
    // Suppress console.error for this test
    const originalError = console.error;
    console.error = jest.fn();

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useMode must be used within a ModeProvider');

    console.error = originalError;
  });
});
