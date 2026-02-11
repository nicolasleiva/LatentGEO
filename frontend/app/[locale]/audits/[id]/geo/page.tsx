'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { ArrowLeft, TrendingUp, Target, Award, FileText, Sparkles, BarChart3, Search } from 'lucide-react';
import { Header } from '@/components/header';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { API_URL } from '@/lib/api';
import { fetchWithBackendAuth } from '@/lib/backend-auth';
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
            const preload = () => {
                import('./components/RecentCitationsTable');
                import('./components/CitationHistory');
                import('./components/QueryDiscovery');
                import('./components/CompetitorAnalysis');
                import('./components/SchemaGenerator');
                import('./components/SchemaMultipleGenerator');
                import('./components/ContentTemplates');
                import('./components/ContentAnalyze');
            };

            if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
                (window as Window & { requestIdleCallback?: (cb: () => void) => void }).requestIdleCallback?.(preload);
            } else {
                setTimeout(preload, 100);
            }
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
                const res = await fetchWithBackendAuth(`${backendUrl}/api/geo/dashboard/${auditId}`);
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
            const res = await fetchWithBackendAuth(`${backendUrl}/api/geo/citation-tracking/start`, {
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
            <div className="min-h-screen p-8 flex items-center justify-center bg-background text-foreground">
                <div className="glass-card p-8 max-w-lg w-full border-red-500/30">
                    <h2 className="text-2xl font-bold text-red-600 mb-2">Error Loading Data</h2>
                    <p className="text-muted-foreground mb-6">{error || 'Unable to load GEO dashboard data'}</p>
                    <Button onClick={() => window.location.reload()} className="glass-button w-full">
                        Try Again
                    </Button>
                </div>
            </div>
        );
    }

    const citationTracking = data?.citation_tracking ?? {
        citation_rate: 0,
        total_queries: 0,
        mentions: 0,
        sentiment_breakdown: {},
    };
    const sentiment = citationTracking.sentiment_breakdown || {};
    const citationRate = citationTracking.citation_rate || 0;
    const totalMentions = citationTracking.mentions || 0;
    const opportunities = data?.top_opportunities || [];

    return (
        <div className="min-h-screen bg-background text-foreground pb-20">
            <Header />
            <main className="max-w-7xl mx-auto px-6 py-10">
                {/* Header */}
                <div className="mb-12">
                    <Link href={`/audits/${auditId}`}>
                        <Button variant="ghost" className="text-muted-foreground hover:text-foreground hover:bg-muted/40 mb-6 pl-0">
                            <ArrowLeft className="w-4 h-4 mr-2" />
                            Back to Audit
                        </Button>
                    </Link>

                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                        <div>
                            <h1 className="text-4xl md:text-5xl font-semibold mb-2 text-foreground">
                                GEO Dashboard
                            </h1>
                            <p className="text-lg text-muted-foreground">
                                Generative Engine Optimization analytics for LLM visibility.
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
                            <Target className="w-24 h-24 text-brand" />
                        </div>
                        <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Citation Rate</h3>
                        <div className="text-4xl font-bold text-foreground mb-1">{citationRate.toFixed(1)}%</div>
                        <p className="text-xs text-muted-foreground">of queries mention you</p>
                    </div>

                    <div className="glass-card p-6 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <TrendingUp className="w-24 h-24 text-emerald-600" />
                        </div>
                        <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Total Mentions</h3>
                        <div className="text-4xl font-bold text-emerald-600 mb-1">{totalMentions}</div>
                        <p className="text-xs text-muted-foreground">in last 30 days</p>
                    </div>

                    <div className="glass-card p-6 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Search className="w-24 h-24 text-sky-600" />
                        </div>
                        <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Opportunities</h3>
                        <div className="text-4xl font-bold text-sky-600 mb-1">{opportunities.length}</div>
                        <p className="text-xs text-muted-foreground">high potential queries</p>
                    </div>

                    <div className="glass-card p-6 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <BarChart3 className="w-24 h-24 text-brand" />
                        </div>
                        <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Sentiment</h3>
                        <div className="flex gap-4 items-end h-10">
                            <div className="flex flex-col items-center">
                                <div className="h-1 w-8 bg-green-500/20 rounded-full overflow-hidden mb-1">
                                    <div className="h-full bg-green-500" style={{ width: '100%' }}></div>
                                </div>
                                <span className="text-lg font-bold text-emerald-600">{sentiment.positive || 0}</span>
                            </div>
                            <div className="flex flex-col items-center">
                                <div className="h-1 w-8 bg-muted/40 rounded-full overflow-hidden mb-1">
                                    <div className="h-full bg-muted-foreground/60" style={{ width: '100%' }}></div>
                                </div>
                                <span className="text-lg font-bold text-muted-foreground">{sentiment.neutral || 0}</span>
                            </div>
                            <div className="flex flex-col items-center">
                                <div className="h-1 w-8 bg-red-500/20 rounded-full overflow-hidden mb-1">
                                    <div className="h-full bg-red-500" style={{ width: '100%' }}></div>
                                </div>
                                <span className="text-lg font-bold text-red-600">{sentiment.negative || 0}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Main Content Tabs */}
                <Tabs defaultValue="opportunities" className="space-y-8">
                    <TabsList className="bg-muted/40 p-1 rounded-2xl border border-border w-full md:w-auto inline-flex">
                        <TabsTrigger value="opportunities" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Top Opportunities</TabsTrigger>
                        <TabsTrigger value="citations" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Recent Citations</TabsTrigger>
                        <TabsTrigger value="history" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Citation History</TabsTrigger>
                        <TabsTrigger value="query" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Query Discovery</TabsTrigger>
                        <TabsTrigger value="competitors" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Competitors</TabsTrigger>
                        <TabsTrigger value="schema" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Schema Generator</TabsTrigger>
                        <TabsTrigger value="schema-multiple" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Schema Multiple</TabsTrigger>
                        <TabsTrigger value="templates" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Content Templates</TabsTrigger>
                        <TabsTrigger value="content-analyze" className="rounded-xl data-[state=active]:bg-background data-[state=active]:text-foreground text-muted-foreground px-6 py-3">Analyze Content</TabsTrigger>
                    </TabsList>

                    <TabsContent value="opportunities" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-blue-500/20 rounded-xl">
                                    <Target className="w-6 h-6 text-blue-400" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-foreground">Query Opportunities</h2>
                                    <p className="text-muted-foreground">Queries that don&apos;t mention you yet but have high potential</p>
                                </div>
                            </div>

                            {opportunities.length === 0 ? (
                                <div className="text-center py-12 bg-muted/30 rounded-2xl border border-dashed border-border">
                                    <p className="text-muted-foreground">No opportunities discovered yet. Run Query Discovery to find them.</p>
                                </div>
                            ) : (
                                <div className="grid gap-4">
                                    {opportunities.map((opp, idx) => (
                                        <div
                                            key={idx}
                                            className="group bg-muted/30 hover:bg-muted/50 border border-border rounded-2xl p-6 transition-all duration-300"
                                        >
                                            <div className="flex justify-between items-start mb-3">
                                                <h4 className="font-semibold text-xl text-foreground group-hover:text-brand transition-colors">{opp.query}</h4>
                                                <div className="flex items-center gap-2">
                                                    <span className="bg-brand/10 text-brand px-3 py-1 rounded-lg text-sm font-bold border border-brand/20">
                                                        Score: {opp.potential_score}
                                                    </span>
                                                    <span className="bg-muted/40 text-muted-foreground px-3 py-1 rounded-lg text-sm capitalize border border-border">
                                                        {opp.intent}
                                                    </span>
                                                </div>
                                            </div>
                                            {opp.sample_response && (
                                                <div className="bg-muted/30 rounded-xl p-4 border border-border">
                                                    <p className="text-sm text-muted-foreground italic leading-relaxed">
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
                                    <h2 className="text-2xl font-bold text-foreground">Recent Citations</h2>
                                    <p className="text-muted-foreground">Where your brand was mentioned in LLM responses</p>
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
                                    <h2 className="text-2xl font-bold text-foreground">Citation History</h2>
                                    <p className="text-muted-foreground">Aggregated history for monthly tracking</p>
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
                                    <h2 className="text-2xl font-bold text-foreground">Query Discovery</h2>
                                    <p className="text-muted-foreground">Discover queries and opportunities for LLM citations</p>
                                </div>
                            </div>
                            <QueryDiscovery auditId={Number(auditId)} backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="competitors" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-brand/10 rounded-xl">
                                    <BarChart3 className="w-6 h-6 text-brand" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-foreground">Competitor Analysis</h2>
                                    <p className="text-muted-foreground">Run analysis and benchmark against competitors</p>
                                </div>
                            </div>
                            <CompetitorAnalysis auditId={Number(auditId)} backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="schema" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-brand/10 rounded-xl">
                                    <FileText className="w-6 h-6 text-brand" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-foreground">Schema.org Generator</h2>
                                    <p className="text-muted-foreground">Generate optimized Schema.org for better LLM understanding</p>
                                </div>
                            </div>
                            <SchemaGenerator backendUrl={backendUrl} />
                        </div>
                    </TabsContent>

                    <TabsContent value="schema-multiple" className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100">
                        <div className="glass-card p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-brand/10 rounded-xl">
                                    <FileText className="w-6 h-6 text-brand" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-foreground">Multiple Schemas</h2>
                                    <p className="text-muted-foreground">Generate multiple suggested schemas for a page</p>
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
                                    <h2 className="text-2xl font-bold text-foreground">Content Templates</h2>
                                    <p className="text-muted-foreground">GEO-optimized content templates for maximum visibility</p>
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
                                    <h2 className="text-2xl font-bold text-foreground">Analyze Content for GEO</h2>
                                    <p className="text-muted-foreground">Analyze freeform content to identify GEO gaps.</p>
                                </div>
                            </div>
                            <ContentAnalyze backendUrl={backendUrl} />
                        </div>
                    </TabsContent>
                </Tabs>
            </main>
        </div>
    );
}
