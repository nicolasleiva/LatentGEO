'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
    LayoutDashboard,
    Search,
    BarChart2,
    Link2,
    Zap,
    Settings,
    Globe,
    Bot,
    FileText,
    Download,
    Github,
    Webhook,
    Activity,
    Radio,
    RotateCcw,
    Wand2
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
    { name: 'Overview', href: '/', icon: LayoutDashboard },
    { name: 'Audits', href: '/audits', icon: Search },
    { name: 'Rank Tracking', href: '/audits/rank-tracking', icon: BarChart2, disabled: true }, // Disabled in main menu, context aware
    { name: 'Link Analysis', href: '/audits/backlinks', icon: Link2, disabled: true },
    { name: 'AI Visibility', href: '/audits/llm-visibility', icon: Bot, disabled: true },
]

export function Sidebar() {
    const pathname = usePathname()

    // Check if we are inside an audit context
    const auditMatch = pathname.match(/\/audits\/(\d+)/)
    const currentAuditId = auditMatch ? auditMatch[1] : null

    return (
        <div className="fixed inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-sidebar-border flex flex-col">
            <div className="h-16 flex items-center px-6 border-b border-sidebar-border">
                <div className="flex items-center gap-2 font-semibold text-lg tracking-tight">
                    <Zap className="h-5 w-5 text-primary" />
                    <span>Audit Studio</span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto py-6 px-3 space-y-1">
                <div className="px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Platform
                </div>

                <Link
                    href="/"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <LayoutDashboard className="h-4 w-4" />
                    Overview
                </Link>

                <Link
                    href="/audits"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/audits"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Search className="h-4 w-4" />
                    Audit History
                </Link>

                <Link
                    href="/reports"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/reports"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <FileText className="h-4 w-4" />
                    Reports
                </Link>

                <Link
                    href="/exports"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/exports"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Download className="h-4 w-4" />
                    Exports
                </Link>

                {currentAuditId && (
                    <>
                        <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Current Audit #{currentAuditId}
                        </div>

                        <Link
                            href={`/audits/${currentAuditId}`}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                pathname === `/audits/${currentAuditId}`
                                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                            )}
                        >
                            <BarChart2 className="h-4 w-4" />
                            Dashboard
                        </Link>

                        <Link
                            href={`/audits/${currentAuditId}/rank-tracking`}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                pathname.includes('rank-tracking')
                                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                            )}
                        >
                            <Globe className="h-4 w-4" />
                            Rank Tracking
                        </Link>

                        <Link
                            href={`/audits/${currentAuditId}/backlinks`}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                pathname.includes('backlinks')
                                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                            )}
                        >
                            <Link2 className="h-4 w-4" />
                            Link Analysis
                        </Link>

                        <Link
                            href={`/audits/${currentAuditId}/llm-visibility`}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                pathname.includes('llm-visibility')
                                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                            )}
                        >
                            <Bot className="h-4 w-4" />
                            AI Visibility
                        </Link>
                    </>
                )}

                <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Tools
                </div>

                <Link
                    href="/tools/content-editor"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname.includes('content-editor')
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Wand2 className="h-4 w-4" />
                    GEO Content Editor
                </Link>

                <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Integrations
                </div>

                <Link
                    href="/integrations/hubspot/connect"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname.includes('/integrations/hubspot')
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Zap className="h-4 w-4" />
                    HubSpot
                </Link>

                <Link
                    href="/integrations/hubspot/rollback"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/integrations/hubspot/rollback"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <RotateCcw className="h-4 w-4" />
                    HubSpot Rollback
                </Link>

                <Link
                    href="/integrations/github"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/integrations/github"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Github className="h-4 w-4" />
                    GitHub Admin
                </Link>

                <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Ops
                </div>

                <Link
                    href="/ops/health"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/ops/health"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Activity className="h-4 w-4" />
                    Health
                </Link>

                <Link
                    href="/ops/webhooks"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/ops/webhooks"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Webhook className="h-4 w-4" />
                    Webhooks
                </Link>

                <Link
                    href="/ops/realtime"
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        pathname === "/ops/realtime"
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
                    )}
                >
                    <Radio className="h-4 w-4" />
                    Realtime
                </Link>
            </div>

            <div className="p-4 border-t border-sidebar-border">
                <div className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-sidebar-accent/50 cursor-pointer transition-colors">
                    <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-medium">
                        JD
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">John Doe</p>
                        <p className="text-xs text-muted-foreground truncate">Pro Plan</p>
                    </div>
                    <Settings className="h-4 w-4 text-muted-foreground" />
                </div>
            </div>
        </div >
    )
}
