'use client'

import Link from 'next/link'
import { Sparkles, LayoutDashboard, FileText, Settings, BarChart3, Book, Tag } from 'lucide-react'
import { AuthButtons } from '@/components/auth/AuthButtons'
import { ThemeToggle } from '@/components/theme-toggle'

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/70 bg-background/80 backdrop-blur-xl">
      <div className="container flex h-20 items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="p-2 bg-foreground/5 rounded-xl border border-foreground/10 group-hover:bg-foreground/10 transition-colors">
            <Sparkles className="h-6 w-6 text-foreground" />
          </div>
          <span className="text-xl font-semibold tracking-tight">
            LatentGEO<span className="text-brand">.ai</span>
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          <Link
            href="/audits"
            className="flex items-center gap-2 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors px-4 py-2 rounded-full hover:bg-foreground/5"
          >
            <LayoutDashboard className="w-4 h-4" />
            Audits
          </Link>
          <Link
            href="/analytics"
            className="flex items-center gap-2 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors px-4 py-2 rounded-full hover:bg-foreground/5"
          >
            <BarChart3 className="w-4 h-4" />
            Insights
          </Link>
          <Link
            href="/exports"
            className="flex items-center gap-2 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors px-4 py-2 rounded-full hover:bg-foreground/5"
          >
            <FileText className="w-4 h-4" />
            Exports
          </Link>
          <Link
            href="/docs"
            className="flex items-center gap-2 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors px-4 py-2 rounded-full hover:bg-foreground/5"
          >
            <Book className="w-4 h-4" />
            Docs
          </Link>
          <Link
            href="/pricing"
            className="flex items-center gap-2 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors px-4 py-2 rounded-full hover:bg-foreground/5"
          >
            <Tag className="w-4 h-4" />
            Pricing
          </Link>
          <Link
            href="/settings"
            className="flex items-center gap-2 text-sm font-medium text-foreground/70 hover:text-foreground transition-colors px-4 py-2 rounded-full hover:bg-foreground/5"
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
