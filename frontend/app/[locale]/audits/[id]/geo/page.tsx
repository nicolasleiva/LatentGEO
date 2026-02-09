'use client';

import { useEffect, useState, Suspense, lazy, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { ArrowLeft, TrendingUp, Target, Award, FileText, Sparkles, Copy, Check, BarChart3, Search, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { API_URL } from '@/lib/api';
import { GEOSkeleton } from './loading';
import {
  CitationsTableSkeleton,
  HistorySkeleton,
  QueryDiscoverySkeleton,
  CompetitorAnalysisSkeleton,
  SchemaGeneratorSkeleton,
  ContentTemplatesSkeleton,
  ContentAnalyzeSkeleton,
} from './components/skeletons';

// Lazy load heavy tab components with optimized loading states
const RecentCitationsTable = dynamic(() => import('./components/RecentCitationsTable'), {
  ssr: false,
  loading: () => <CitationsTableSkeleton />
});
const CitationHistory = dynamic(() => import('./components/CitationHistory'), {
  ssr: false,
  loading: () => <HistorySkeleton />
});
const QueryDiscovery = dynamic(() => import('./components/QueryDiscovery'), {
  ssr: false,
  loading: () => <QueryDiscoverySkeleton />
});
const CompetitorAnalysis = dynamic(() => import('./components/CompetitorAnalysis'), {
  ssr: false,
  loading: () => <CompetitorAnalysisSkeleton />
});
const SchemaGenerator = dynamic(() => import('./components/SchemaGenerator'), {
  ssr: false,
  loading: () => <SchemaGeneratorSkeleton />
});
const SchemaMultipleGenerator = dynamic(() => import('./components/SchemaMultipleGenerator'), {
  ssr: false,
  loading: () => <SchemaGeneratorSkeleton />
});
const ContentTemplates = dynamic(() => import('./components/ContentTemplates'), {
  ssr: false,
  loading: () => <ContentTemplatesSkeleton />
});
const ContentAnalyze = dynamic(() => import('./components/ContentAnalyze'), {
  ssr: false,
  loading: () => <ContentAnalyzeSkeleton />
});

interface GEODashboardData {
    audit_id: number;
    citation_tracking: {
        citation_rate: number;
        total_queries: number;
        mentions: number;
        sentiment_breakdown: {
            positive?: number;
            neutral?: number;
            negative?: number;
        };
    };
    top_opportunities: Array<{
        query: string;
        intent: string;
        potential_score: number;
        sample_response?: string;
    }>;
    competitor_benchmark: {
        has_data: boolean;
        your_mentions: number;
        top_competitor?: string;
        gap_analysis?: any;
    };
}

// Cache key helper
const getCacheKey = (auditId: string) => `geo-dashboard-${auditId}`;

export default function GEODashboardPage() {
    const params = useParams();
    const auditId = params.id as string;

    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<GEODashboardData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const hasPreloaded = useRef(false);

    const backendUrl = API_URL;

    // Pre-load components after initial render for instant tab switching
    useEffect(() => {
        if (hasPreloaded.current) return;
        
        // Wait for main content to render, then preload in background
        const preloadTimer = setTimeout(() => {
            hasPreloaded.current = true;
            // Preload components in order of likelihood of use
            requestIdleCallback?.(() => {
                import('./components/RecentCitationsTable');
                import('./components/CitationHistory');
                import('./components/QueryDiscovery');
                import('./components/CompetitorAnalysis');
                import('./components/SchemaGenerator');
                import('./components/SchemaMultipleGenerator');
                import('./components/ContentTemplates');
                import('./components/ContentAnalyze');
            }) || setTimeout(() => {
                import('./components/RecentCitationsTable');
                import('./components/CitationHistory');
                import('./components/QueryDiscovery');
                import('./components/CompetitorAnalysis');
                import('./components/SchemaGenerator');
                import('./components/SchemaMultipleGenerator');
                import('./components/ContentTemplates');
                import('./components/ContentAnalyze');
            }, 100);
        }, 1500);

        return () => clearTimeout(preloadTimer);
    }, []);

    useEffect(() => {
        // Try to get cached data first (stale-while-revalidate pattern)
        const cacheKey = getCacheKey(auditId);
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
            try {
                const parsed = JSON.parse(cached);
                setData(parsed);
                setLoading(false); // Show cached data immediately
            } catch (e) {
                // Invalid cache, continue to fetch
            }
        }

        const fetchData = async () => {
            try {
                const res = await fetch(`${backendUrl}/api/geo/dashboard/${auditId}`, {
                    // Add cache headers for HTTP caching
                    headers: {
                        'Cache-Control': 'max-age=300', // 5 minutes
                    }
                });
                if (!res.ok) throw new Error('Failed to fetch GEO data');
                const geoData = await res.json();
                setData(geoData);
                // Cache the fresh data
                localStorage.setItem(cacheKey, JSON.stringify(geoData));
            } catch (err: any) {
                // Only show error if we don't have cached data
                if (!data) {
                    setError(err.message);
                }
            } finally {
                setLoading(false);
            }
        };

        if (auditId) {
            fetchData();
        }
    }, [auditId, backendUrl, data]);

    const startCitationTracking = async () => {
        try {
            const res = await fetch(`${backendUrl}/api/geo/citation-tracking/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    audit_id: Number(auditId),
                    industry: 'general',
                    keywords: [],
                    llm_name: 'kimi',
                }),
            });
            if (res.ok) {
                alert('Citation tracking started! Refresh in a few minutes.');
            }
        } catch (err) {
            console.error(err);
        }
    };

    // Show skeleton while loading - instant visual feedback
    if (loading && !data) {
        return <GEOSkeleton auditId={auditId} />;
    }

    if (error || !data) {
        return (
            <div className="min-h-screen p-8 flex items-center justify-center">
                <div className="glass-card p-8 max-w-lg w-full border-red-500/30">
                    <h2 className="text-2xl font-bold text-red-400 mb-2">Error Loading Data</h2>
                    <p className="text-white/70 mb-6">{error || 'Unable to load GEO dashboard data'}</p>
                    <Button onClick={() => window.location.reload()} className="glass-button w-full">
                        Try Again
                    </Button>
                </div>
            </div>
        );
    }

    const citationRate = data.citation_tracking.citation_rate;
    const totalMentions = data.citation_tracking.mentions;
    const opportunities = data.top_opportunities || [];

    return (
        <div className="min-h-screen pb-20">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-12">
                    <Link href={`/audits/${auditId}`}>
                        <Button variant="ghost" className="text-white/50 hover:text-white hover:bg-white/10 mb-6 pl-0">
                            <ArrowLeft className="w-4 h-4 mr-2" />
                            Back to Audit
                        </Button>
                    </Link>

                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                        <div>
                            <h1 className="text-5xl font-bold mb-2 text-transparent bg-clip-text bg-gradient-to-r from-white via-white to-white/50">
                                GEO Dashboard
                            </h1>
                            <p className="text-xl text-white/60 font-light tracking-wide">
                                Generative Engine Optimization Analytics
                            </p>
                        </div>

                        <Button onClick={startCitationTracking} className="glass-button-primary px-8 py-6 text-lg">
                            <Sparkles className="w-5 h-5 mr-3" />
                            Start Tracking
                        </Button>
                    </div>
                </div>

                {/* Key Metrics Grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
                    <div className="glass-card p-6 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Target className="w-24 h-24 text-white" />
                        </div>
                        <h3 className="text-sm font-medium text-white/50 uppercase tracking-wider mb-2">Citation Rate</h3>
                        <div className="text-4xl font-bold text-white mb-1">{citationRate.toFixed(1)}%</div>
                        <p className="text-xs text-white/40">of queries mention you</p>
                    </div>

                    <div className="glass-card p-6 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <TrendingUp className="w-24 h-24 text-green-400" />
                        </div>
                        <h3 className="text-sm font-medium text-white/50 uppercase tracking-wider mb-2">Total Mentions</h3>
                        <div className="text-4xl font-bold text-green-400 mb-1">{totalMentions}</div>
                        <p className="text-xs text-white/40">in last 30 days</p>
                    </div>

                    <div className="glass-card p-6 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Search className="w-24 h-24 text-blue-400" />
                        </div>
                        <h3 className="text-sm font-medium text-white/50 uppercase tracking-wider mb-2">Opportunities</h3>
                        <div className="text-4xl font-bold text-blue-400 mb-1">{opportunities.length}</div>
                        <p className="text-xs text-white/40">high potential queries</p>
                    </div>

                    <div className="glass-card p-6 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <BarChart3 className="w-24 h-24 text-purple-400" />
                        </div>
                        <h3 className="text-sm font-medium text-white/50 uppercase tracking-wider mb-2">Sentiment</h3>
                        <div className="flex gap-4 items-end h-10">
                            <div className="flex flex-col items-center">
                                <div className="h-1 w-8 bg-green-500/20 rounded-full overflow-hidden mb-1">
                                    <div className="h-full bg-green-500" style={{ width: '100%' }}></div>
                                </div>
                                <span className="text-lg font-bold text-green-400">{data.citation_tracking.sentiment_breakdown.positive || 0}</span>
                            </div>
                            <div className="flex flex-col items-center">
                                <div className="h-1 w-8 bg-white/10 rounded-full overflow-hidden mb-1">
                                    <div className="h-full bg-white/50" style={{ width: '100%' }}></div>
                                </div>
                                <span className="text-lg font-bold text-white/60">{data.citation_tracking.sentiment_breakdown.neutral || 0}</span>
                            </div>
                            <div className="flex flex-col items-center">
                                <div className="h-1 w-8 bg-red-500/20 rounded-full overflow-hidden mb-1">
                                    <div className="h-full bg-red-500" style={{ width: '100%' }}></div>
                                </div>
                                <span className="text-lg font-bold text-red-400">{data.citation_tracking.sentiment_breakdown.negative || 0}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Main Content Tabs */}
                <Tabs defaultValue="opportunities" className="space-y-8">
                    <TabsList className="bg-white/5 p-1 rounded-2xl border border-white/10 w-full md:w-auto inline-flex">
                        <TabsTrigger value="opportunities" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Top Opportunities</TabsTrigger>
                        <TabsTrigger value="citations" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Recent Citations</TabsTrigger>
                        <TabsTrigger value="history" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Citation History</TabsTrigger>
                        <TabsTrigger value="query" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Query Discovery</TabsTrigger>
                        <TabsTrigger value="competitors" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Competitors</TabsTrigger>
                        <TabsTrigger value="schema" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Schema Generator</TabsTrigger>
                        <TabsTrigger value="schema-multiple" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Schema Multiple</TabsTrigger>
                        <TabsTrigger value="templates" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Content Templates</TabsTrigger>
                        <TabsTrigger value="content-analyze" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Analyze Content</TabsTrigger>
                    </TabsList>

                    <TabsContent value="opportunities" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-blue-500/20 rounded-xl">
                                    <Target className="w-6 h-6 text-blue-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Query Opportunities</h2>
                                    <p className="text-white/50">Queries that don&apos;t mention you yet but have high potential</p>
                                </div>
                            </div>

                            {opportunities.length === 0 ? (
                                <div className="text-center py-12 bg-white/5 rounded-2xl border border-dashed border-white/10">
                                    <p className="text-white/40">No opportunities discovered yet. Run Query Discovery to find them.</p>
                                </div>
                            ) : (
                                <div className="grid gap-4">
                                    {opportunities.map((opp, idx) => (
                                        <div
                                            key={idx}
                                            className="group bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/20 rounded-2xl p-6 transition-all duration-300"
                                        >
                                            <div className="flex justify-between items-start mb-3">
                                                <h4 className="font-semibold text-xl text-white group-hover:text-blue-300 transition-colors">{opp.query}</h4>
                                                <div className="flex items-center gap-2">
                                                    <span className="bg-blue-500/20 text-blue-300 px-3 py-1 rounded-lg text-sm font-bold border border-blue-500/30">
                                                        Score: {opp.potential_score}
                                                    </span>
                                                    <span className="bg-white/10 text-white/70 px-3 py-1 rounded-lg text-sm capitalize border border-white/10">
                                                        {opp.intent}
                                                    </span>
                                                </div>
                                            </div>
                                            {opp.sample_response && (
                                                <div className="bg-black/20 rounded-xl p-4 border border-white/5">
                                                    <p className="text-sm text-white/60 italic leading-relaxed">
                                                        &quot;{opp.sample_response}&quot;
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </TabsContent>

                    <TabsContent value="citations" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-green-500/20 rounded-xl">
                                    <TrendingUp className="w-6 h-6 text-green-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Recent Citations</h2>
                                    <p className="text-white/50">Where your brand was mentioned in LLM responses</p>
                                </div>
                            </div>
                            <RecentCitationsTable auditId={Number(auditId)} backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="history" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-green-500/20 rounded-xl">
                                    <TrendingUp className="w-6 h-6 text-green-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Citation History</h2>
                                    <p className="text-white/50">Histórico agregado para seguimiento mensual</p>
                                </div>
                            </div>
                            <CitationHistory auditId={Number(auditId)} backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="query" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-blue-500/20 rounded-xl">
                                    <Search className="w-6 h-6 text-blue-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Query Discovery</h2>
                                    <p className="text-white/50">Descubrí queries y oportunidades para que te citen los LLMs</p>
                                </div>
                            </div>
                            <QueryDiscovery auditId={Number(auditId)} backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="competitors" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-purple-500/20 rounded-xl">
                                    <BarChart3 className="w-6 h-6 text-purple-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Competitor Analysis</h2>
                                    <p className="text-white/50">Arrancar análisis y ver benchmark vs competidores</p>
                                </div>
                            </div>
                            <CompetitorAnalysis auditId={Number(auditId)} backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="schema" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-purple-500/20 rounded-xl">
                                    <FileText className="w-6 h-6 text-purple-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Schema.org Generator</h2>
                                    <p className="text-white/50">Generate optimized Schema.org for better LLM understanding</p>
                                </div>
                            </div>
                            <SchemaGenerator backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="schema-multiple" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-purple-500/20 rounded-xl">
                                    <FileText className="w-6 h-6 text-purple-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Multiple Schemas</h2>
                                    <p className="text-white/50">Generar múltiples schemas sugeridos para una página</p>
                                </div>
                            </div>
                            <SchemaMultipleGenerator backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="templates" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-pink-500/20 rounded-xl">
                                    <Award className="w-6 h-6 text-pink-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Content Templates</h2>
                                    <p className="text-white/50">GEO-optimized content templates for maximum visibility</p>
                                </div>
                            </div>
                            <ContentTemplates backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="content-analyze" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-pink-500/20 rounded-xl">
                                    <Award className="w-6 h-6 text-pink-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white">Analyze Content for GEO</h2>
                                    <p className="text-white/50">Analizar contenido libre para detectar gaps GEO</p>
                                </div>
                            </div>
                            <ContentAnalyze backendUrl={backendUrl} />
                        </div>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
}

