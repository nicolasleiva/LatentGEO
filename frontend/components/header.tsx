'use client'

import Link from 'next/link'
import { Zap, LayoutDashboard, FileText, Settings, BarChart3, Book } from 'lucide-react'
import { AuthButtons } from '@/components/auth/AuthButtons'
import { ThemeToggle } from '@/components/theme-toggle'

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-black/5 dark:border-white/5 bg-white/80 dark:bg-black/20 backdrop-blur-xl">
      <div className="container flex h-20 items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="p-2 bg-black/5 dark:bg-white/5 rounded-xl border border-black/10 dark:border-white/10 group-hover:bg-black/10 dark:group-hover:bg-white/10 transition-colors">
            <Zap className="h-6 w-6 text-black dark:text-white" />
          </div>
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-black via-black to-black/60 dark:from-white dark:via-white dark:to-white/60">
            AI Audit Studio
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          <Link
            href="/audits"
            className="flex items-center gap-2 text-sm font-medium text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5"
          >
            <LayoutDashboard className="w-4 h-4" />
            Audits
          </Link>
          <Link
            href="/analytics"
            className="flex items-center gap-2 text-sm font-medium text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5"
          >
            <BarChart3 className="w-4 h-4" />
            Analytics
          </Link>
          <Link
            href="/exports"
            className="flex items-center gap-2 text-sm font-medium text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5"
          >
            <FileText className="w-4 h-4" />
            Exports
          </Link>
          <Link
            href="/docs"
            className="flex items-center gap-2 text-sm font-medium text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5"
          >
            <Book className="w-4 h-4" />
            Docs
          </Link>
          <Link
            href="/settings"
            className="flex items-center gap-2 text-sm font-medium text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5"
          >
            <Settings className="w-4 h-4" />
            Settings
          </Link>
        </nav>

        <div className="flex items-center gap-4">
          <ThemeToggle />
          <AuthButtons />
        </div>
      </div>
    </header>
  )
}
