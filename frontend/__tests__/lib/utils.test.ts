import { cn, formatCurrency, formatPercent, formatDate, getRelativeTime, getValueColor } from '@/lib/utils';

describe('cn', () => {
  it('should merge class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('should handle conditional classes', () => {
    expect(cn('foo', false && 'bar', 'baz')).toBe('foo baz');
  });

  it('should merge Tailwind classes correctly', () => {
    expect(cn('px-2 py-1', 'px-4')).toBe('py-1 px-4');
  });
});

describe('formatCurrency', () => {
  it('should format positive numbers', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56');
  });

  it('should format negative numbers', () => {
    expect(formatCurrency(-1234.56)).toBe('-$1,234.56');
  });

  it('should format zero', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });
});

describe('formatPercent', () => {
  it('should format with default decimals', () => {
    expect(formatPercent(12.3456)).toBe('12.35%');
  });

  it('should format with custom decimals', () => {
    expect(formatPercent(12.3456, 1)).toBe('12.3%');
  });

  it('should format negative values', () => {
    expect(formatPercent(-5.5)).toBe('-5.50%');
  });
});

describe('formatDate', () => {
  it('should format date string', () => {
    const result = formatDate('2024-01-15T10:30:00Z');
    // Just check that it contains a date format
    expect(result).toMatch(/Jan \d+, 2024/);
  });

  it('should format Date object', () => {
    const date = new Date('2024-06-20T14:00:00Z');
    const result = formatDate(date);
    // Due to timezone differences, could be Jun 20 or Jun 21
    expect(result).toMatch(/Jun \d+, 2024/);
  });
});

describe('getValueColor', () => {
  it('should return green for positive values', () => {
    expect(getValueColor(100)).toContain('green');
  });

  it('should return red for negative values', () => {
    expect(getValueColor(-100)).toContain('red');
  });

  it('should return gray for zero', () => {
    expect(getValueColor(0)).toContain('gray');
  });
});

describe('getRelativeTime', () => {
  it('should return "just now" for recent times', () => {
    const now = new Date();
    expect(getRelativeTime(now)).toBe('just now');
  });

  it('should return minutes ago', () => {
    const date = new Date(Date.now() - 5 * 60 * 1000);
    expect(getRelativeTime(date)).toBe('5 minutes ago');
  });

  it('should return hours ago', () => {
    const date = new Date(Date.now() - 3 * 60 * 60 * 1000);
    expect(getRelativeTime(date)).toBe('3 hours ago');
  });

  it('should return days ago', () => {
    const date = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
    expect(getRelativeTime(date)).toBe('2 days ago');
  });
});
