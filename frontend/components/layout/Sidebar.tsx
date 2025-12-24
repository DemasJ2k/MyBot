'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { ModeIndicator, ModeSwitch } from './ModeIndicator';
import {
  LayoutDashboard,
  LineChart,
  FlaskConical,
  Settings2,
  Zap,
  BookOpen,
  Shield,
  Bot,
  Settings,
  Menu,
  X,
  LogOut,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Strategies', href: '/strategies', icon: LineChart },
  { name: 'Backtest', href: '/backtest', icon: FlaskConical },
  { name: 'Optimization', href: '/optimization', icon: Settings2 },
  { name: 'Signals', href: '/signals', icon: Zap },
  { name: 'Execution', href: '/execution', icon: Shield },
  { name: 'Performance', href: '/performance', icon: LineChart },
  { name: 'Journal', href: '/journal', icon: BookOpen },
  { name: 'AI Chat', href: '/ai-chat', icon: Bot },
  { name: 'Settings', href: '/settings', icon: Settings },
];

interface SidebarProps {
  onLogout?: () => void;
}

export function Sidebar({ onLogout }: SidebarProps) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-50 p-2 rounded-md bg-white dark:bg-gray-800 shadow-md lg:hidden"
      >
        {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-40 h-screen w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 transform transition-transform duration-300 lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-200 dark:border-gray-800">
            <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <LineChart className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900 dark:text-white">Flowrex</span>
          </div>

          {/* Mode indicator */}
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
            <ModeSwitch className="w-full justify-center" />
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-4 overflow-y-auto">
            <ul className="space-y-1">
              {navigation.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;

                return (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      onClick={() => setIsOpen(false)}
                      className={cn(
                        'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                          : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
                      )}
                    >
                      <Icon className="h-5 w-5" />
                      {item.name}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Footer */}
          <div className="px-4 py-4 border-t border-gray-200 dark:border-gray-800">
            {onLogout && (
              <button
                onClick={onLogout}
                className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800 transition-colors"
              >
                <LogOut className="h-5 w-5" />
                Logout
              </button>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

interface HeaderProps {
  title?: string;
  children?: React.ReactNode;
}

export function Header({ title, children }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-4 ml-12 lg:ml-0">
          {title && <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{title}</h1>}
        </div>
        <div className="flex items-center gap-4">
          <ModeIndicator />
          {children}
        </div>
      </div>
    </header>
  );
}

interface PageContainerProps {
  children: React.ReactNode;
  title?: string;
  actions?: React.ReactNode;
}

export function PageContainer({ children, title, actions }: PageContainerProps) {
  return (
    <div className="lg:pl-64 min-h-screen bg-gray-50 dark:bg-gray-950">
      <Header title={title}>{actions}</Header>
      <main className="p-6">{children}</main>
    </div>
  );
}
