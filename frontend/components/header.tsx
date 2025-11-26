import Link from 'next/link'
import { Search, Zap, LayoutDashboard, FileText, Settings, BarChart3 } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/5 bg-black/20 backdrop-blur-xl supports-[backdrop-filter]:bg-black/20">
      <div className="container flex h-20 items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="p-2 bg-white/5 rounded-xl border border-white/10 group-hover:bg-white/10 transition-colors">
            <Zap className="h-6 w-6 text-white" />
          </div>
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-white to-white/60">
            AI Audit Studio
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          <Link
            href="/audits"
            className="flex items-center gap-2 text-sm font-medium text-white/60 hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-white/5"
          >
            <LayoutDashboard className="w-4 h-4" />
            Audits
          </Link>
          <Link
            href="/analytics"
            className="flex items-center gap-2 text-sm font-medium text-white/60 hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-white/5"
          >
            <BarChart3 className="w-4 h-4" />
            Analytics
          </Link>
          <Link
            href="/exports"
            className="flex items-center gap-2 text-sm font-medium text-white/60 hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-white/5"
          >
            <FileText className="w-4 h-4" />
            Exports
          </Link>
          <Link
            href="/settings"
            className="flex items-center gap-2 text-sm font-medium text-white/60 hover:text-white transition-colors px-4 py-2 rounded-full hover:bg-white/5"
          >
            <Settings className="w-4 h-4" />
            Settings
          </Link>
        </nav>

        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" className="text-white/70 hover:text-white hover:bg-white/10 rounded-xl">
            Sign in
          </Button>
          <Button size="sm" className="bg-white text-black hover:bg-white/90 rounded-xl font-medium px-6 shadow-lg shadow-white/10">
            Get Started
          </Button>
        </div>
      </div>
    </header>
  )
}
