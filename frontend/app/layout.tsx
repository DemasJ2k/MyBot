import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/providers/QueryProvider';
import { ModeProvider } from '@/providers/ModeProvider';
import { ErrorBoundary } from '@/components/ErrorBoundary';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Flowrex - AI Trading Platform',
  description: 'Institutional-grade AI-powered trading platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ErrorBoundary>
          <QueryProvider>
            <ModeProvider>
              {children}
            </ModeProvider>
          </QueryProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
