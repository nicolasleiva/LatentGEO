'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Loader2, TrendingUp, Users, AlertTriangle, CheckCircle, ArrowLeft, BarChart3, Target } from 'lucide-react'

export default function AnalyticsPage() {
    const router = useRouter()
    const [loading, setLoading] = useState(true)
    const [dashboardData, setDashboardData] = useState<any>(null)

    useEffect(() => {
        loadDashboard()
    }, [])

    const loadDashboard = async () => {
        try {
            const data = await api.getDashboardData()
            setDashboardData(data)
        } catch (error) {
            console.error('Error loading dashboard:', error)
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="h-12 w-12 animate-spin text-white/60" />
            </div>
        )
    }

    if (!dashboardData) {
        return (
            <div className="min-h-screen flex items-center justify-center p-6">
                <Card className="glass-card p-12 text-center max-w-md">
                    <AlertTriangle className="h-16 w-16 text-yellow-400 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-white mb-2">No Data Available</h3>
                    <p className="text-white/60 mb-6">Unable to load analytics data</p>
                    <Button onClick={loadDashboard} className="glass-button-primary">
                        Retry
                    </Button>
                </Card>
            </div>
        )
    }

    const { summary, recent_audits, metrics } = dashboardData

    return (
        <div className="min-h-screen p-6">
            {/* Header */}
            <div className="max-w-7xl mx-auto mb-8">
                <div className="flex items-center gap-4 mb-2">
                    <Button
                        variant="ghost"
                        onClick={() => router.push('/')}
                        className="text-white/60 hover:text-white hover:bg-white/10"
                    >
                        <ArrowLeft className="h-4 w-4 mr-2" /> Back
                    </Button>
                    <div className="h-6 w-px bg-white/10" />
                    <h1 className="text-3xl font-bold tracking-tight text-white">Analytics Dashboard</h1>
                </div>
                <p className="text-white/60 text-sm">
                    Comprehensive overview of your SEO/GEO audits and performance
                </p>
            </div>

            <div className="max-w-7xl mx-auto space-y-6">
                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <Card className="glass-card p-6">
                        <div className="flex items-center justify-between mb-2">
                            <BarChart3 className="h-5 w-5 text-blue-400" />
                            <Badge className="bg-blue-500/20 text-blue-300 border-blue-500/30">
                                Total
                            </Badge>
                        </div>
                        <div className="text-3xl font-bold text-white mb-1">
                            {summary.total_audits}
                        </div>
                        <div className="text-sm text-white/50">Total Audits</div>
                    </Card>

                    <Card className="glass-card p-6">
                        <div className="flex items-center justify-between mb-2">
                            <CheckCircle className="h-5 w-5 text-green-400" />
                            <Badge className="bg-green-500/20 text-green-300 border-green-500/30">
                                {summary.success_rate.toFixed(0)}%
                            </Badge>
                        </div>
                        <div className="text-3xl font-bold text-white mb-1">
                            {summary.completed_audits}
                        </div>
                        <div className="text-sm text-white/50">Completed</div>
                    </Card>

                    <Card className="glass-card p-6">
                        <div className="flex items-center justify-between mb-2">
                            <Loader2 className="h-5 w-5 text-yellow-400 animate-pulse" />
                            <Badge className="bg-yellow-500/20 text-yellow-300 border-yellow-500/30">
                                Active
                            </Badge>
                        </div>
                        <div className="text-3xl font-bold text-white mb-1">
                            {summary.running_audits}
                        </div>
                        <div className="text-sm text-white/50">Running</div>
                    </Card>

                    <Card className="glass-card p-6">
                        <div className="flex items-center justify-between mb-2">
                            <Users className="h-5 w-5 text-purple-400" />
                            <Badge className="bg-purple-500/20 text-purple-300 border-purple-500/30">
                                Unique
                            </Badge>
                        </div>
                        <div className="text-3xl font-bold text-white mb-1">
                            {metrics.unique_domains}
                        </div>
                        <div className="text-sm text-white/50">Domains</div>
                    </Card>
                </div>

                {/* Metrics Overview */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <Card className="glass-card p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-3 bg-red-500/10 rounded-lg">
                                <AlertTriangle className="h-6 w-6 text-red-400" />
                            </div>
                            <div>
                                <h3 className="font-semibold text-white">Total Issues</h3>
                                <p className="text-xs text-white/50">Across all audits</p>
                            </div>
                        </div>
                        <div className="text-4xl font-bold text-red-400 mb-2">
                            {metrics.total_issues}
                        </div>
                        <div className="text-sm text-white/60">
                            Avg: {metrics.average_issues_per_audit} per audit
                        </div>
                    </Card>

                    <Card className="glass-card p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-3 bg-green-500/10 rounded-lg">
                                <Target className="h-6 w-6 text-green-400" />
                            </div>
                            <div>
                                <h3 className="font-semibold text-white">Success Rate</h3>
                                <p className="text-xs text-white/50">Completion rate</p>
                            </div>
                        </div>
                        <div className="text-4xl font-bold text-green-400 mb-2">
                            {summary.success_rate.toFixed(1)}%
                        </div>
                        <div className="text-sm text-white/60">
                            {summary.completed_audits} of {summary.total_audits} completed
                        </div>
                    </Card>

                    <Card className="glass-card p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-3 bg-blue-500/10 rounded-lg">
                                <TrendingUp className="h-6 w-6 text-blue-400" />
                            </div>
                            <div>
                                <h3 className="font-semibold text-white">Performance</h3>
                                <p className="text-xs text-white/50">Overall health</p>
                            </div>
                        </div>
                        <div className="text-4xl font-bold text-blue-400 mb-2">
                            {summary.failed_audits === 0 ? 'Excellent' : 'Good'}
                        </div>
                        <div className="text-sm text-white/60">
                            {summary.failed_audits} failed audits
                        </div>
                    </Card>
                </div>

                {/* Recent Audits */}
                <Card className="glass-card p-6">
                    <h2 className="text-xl font-semibold text-white mb-6">Recent Audits</h2>
                    <div className="space-y-4">
                        {recent_audits.slice(0, 10).map((audit: any) => (
                            <div
                                key={audit.id}
                                className="flex items-center justify-between p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all cursor-pointer"
                                onClick={() => router.push(`/audits/${audit.id}`)}
                            >
                                <div className="flex-1">
                                    <div className="flex items-center gap-3 mb-1">
                                        <h3 className="font-semibold text-white">{audit.domain}</h3>
                                        <Badge
                                            variant="outline"
                                            className={`text-xs ${audit.status === 'completed'
                                                    ? 'border-green-500/30 bg-green-500/10 text-green-300'
                                                    : audit.status === 'running'
                                                        ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-300'
                                                        : 'border-red-500/30 bg-red-500/10 text-red-300'
                                                }`}
                                        >
                                            {audit.status}
                                        </Badge>
                                    </div>
                                    <p className="text-sm text-white/50">{audit.url}</p>
                                </div>

                                <div className="flex items-center gap-6">
                                    <div className="text-right">
                                        <div className="text-sm text-white/50">Pages</div>
                                        <div className="text-lg font-semibold text-white">
                                            {audit.total_pages}
                                        </div>
                                    </div>

                                    <div className="text-right">
                                        <div className="text-sm text-white/50">Issues</div>
                                        <div className="text-lg font-semibold text-red-400">
                                            {(audit.issues.critical || 0) +
                                                (audit.issues.high || 0) +
                                                (audit.issues.medium || 0) +
                                                (audit.issues.low || 0)}
                                        </div>
                                    </div>

                                    {audit.status === 'running' && (
                                        <div className="text-right">
                                            <div className="text-sm text-white/50">Progress</div>
                                            <div className="text-lg font-semibold text-yellow-400">
                                                {audit.progress}%
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    {recent_audits.length === 0 && (
                        <div className="text-center py-12 text-white/40">
                            <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
                            <p>No audits yet. Start your first audit to see analytics.</p>
                        </div>
                    )}
                </Card>
            </div>
        </div>
    )
}
