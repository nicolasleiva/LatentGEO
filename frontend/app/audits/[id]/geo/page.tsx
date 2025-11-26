'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, TrendingUp, Target, Award, FileText, Sparkles, Copy, Check, BarChart3, Search, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

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

export default function GEODashboardPage() {
    const params = useParams();
    const auditId = params.id as string;

    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<GEODashboardData | null>(null);
    const [error, setError] = useState<string | null>(null);

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch(`${backendUrl}/api/geo/dashboard/${auditId}`);
                if (!res.ok) throw new Error('Failed to fetch GEO data');
                const geoData = await res.json();
                setData(geoData);
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        if (auditId) {
            fetchData();
        }
    }, [auditId, backendUrl]);

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

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
                    <p className="text-white/70">Loading GEO Intelligence...</p>
                </div>
            </div>
        );
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
                        <TabsTrigger value="schema" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Schema Generator</TabsTrigger>
                        <TabsTrigger value="templates" className="rounded-xl data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 px-6 py-3">Content Templates</TabsTrigger>
                    </TabsList>

                    <TabsContent value="opportunities">
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

                    <TabsContent value="citations">
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

                    <TabsContent value="schema">
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

                    <TabsContent value="templates">
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
                </Tabs>
            </div>
        </div>
    );
}

// Sub-components
function RecentCitationsTable({ auditId, backendUrl }: { auditId: number; backendUrl: string }) {
    const [citations, setCitations] = useState<any[]>([]);

    useEffect(() => {
        fetch(`${backendUrl}/api/geo/citation-tracking/recent/${auditId}`)
            .then((res) => res.json())
            .then((data) => setCitations(data))
            .catch(console.error);
    }, [auditId, backendUrl]);

    if (citations.length === 0) {
        return (
            <div className="text-center py-12 bg-white/5 rounded-2xl border border-dashed border-white/10">
                <p className="text-white/40">No citations found yet.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {citations.map((citation, idx) => (
                <div key={idx} className="bg-white/5 border border-white/10 p-6 rounded-2xl hover:bg-white/10 transition-colors">
                    <div className="font-semibold text-lg text-white mb-2">{citation.query}</div>
                    <div className="bg-black/20 p-4 rounded-xl border border-white/5 mb-3">
                        <p className="text-sm text-white/70 italic">&quot;{citation.citation_text}&quot;</p>
                    </div>
                    <div className="flex gap-3 text-xs">
                        <span className="bg-white/10 text-white/80 px-3 py-1 rounded-lg border border-white/10 font-medium">
                            {citation.llm_name}
                        </span>
                        <span
                            className={`px-3 py-1 rounded-lg border font-medium ${citation.sentiment === 'positive'
                                ? 'bg-green-500/20 text-green-300 border-green-500/30'
                                : citation.sentiment === 'negative'
                                    ? 'bg-red-500/20 text-red-300 border-red-500/30'
                                    : 'bg-white/10 text-white/60 border-white/10'
                                }`}
                        >
                            {citation.sentiment}
                        </span>
                    </div>
                </div>
            ))}
        </div>
    );
}

function SchemaGenerator({ backendUrl }: { backendUrl: string }) {
    const [url, setUrl] = useState('');
    const [html, setHtml] = useState('');
    const [result, setResult] = useState<any>(null);
    const [loading, setLoading] = useState(false);

    const generate = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${backendUrl}/api/geo/schema/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, html_content: html }),
            });
            const data = await res.json();
            setResult(data);
        } catch (e) {
            console.error(e);
            alert('Error generating schema');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6 max-w-4xl">
            <div className="grid grid-cols-1 gap-6">
                <div className="space-y-2">
                    <Label className="text-white/80">Page URL</Label>
                    <Input
                        placeholder="https://example.com/page"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        className="glass-input h-12"
                    />
                </div>
                <div className="space-y-2">
                    <Label className="text-white/80">HTML Content (Optional if URL provided)</Label>
                    <Textarea
                        placeholder="Paste HTML here..."
                        className="glass-input min-h-[150px] font-mono text-xs"
                        value={html}
                        onChange={(e) => setHtml(e.target.value)}
                    />
                </div>
                <Button onClick={generate} disabled={loading} className="glass-button-primary w-full md:w-auto px-8 py-6">
                    {loading ? 'Generating...' : 'Generate Schema'}
                </Button>
            </div>

            {result && (
                <div className="mt-8 bg-black/40 border border-white/10 rounded-2xl p-6 backdrop-blur-md">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="font-bold text-white text-lg">Generated Schema ({result.page_type})</h3>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigator.clipboard.writeText(result.implementation_code)}
                            className="glass-button border-white/20 hover:bg-white/10"
                        >
                            <Copy className="w-4 h-4 mr-2" />
                            Copy Code
                        </Button>
                    </div>
                    <pre className="bg-black/50 text-green-400 p-6 rounded-xl overflow-x-auto text-sm font-mono border border-white/5 shadow-inner">
                        {result.implementation_code}
                    </pre>
                </div>
            )}
        </div>
    );
}

function ContentTemplates({ backendUrl }: { backendUrl: string }) {
    const [templates, setTemplates] = useState<any[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
    const [topic, setTopic] = useState('');
    const [keywords, setKeywords] = useState('');
    const [result, setResult] = useState<any>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetch(`${backendUrl}/api/geo/content-templates/list`)
            .then((res) => res.json())
            .then((data) => setTemplates(data.templates || []))
            .catch(console.error);
    }, [backendUrl]);

    const generate = async () => {
        if (!selectedTemplate) return;
        setLoading(true);
        try {
            const res = await fetch(`${backendUrl}/api/geo/content-templates/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    template_type: selectedTemplate,
                    topic,
                    keywords: keywords.split(',').map((k) => k.trim()),
                }),
            });
            const data = await res.json();
            setResult(data);
        } catch (e) {
            console.error(e);
            alert('Error generating template');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {templates.map((template, idx) => (
                    <Dialog key={idx}>
                        <DialogTrigger asChild>
                            <div
                                className="glass-card p-6 cursor-pointer group hover:bg-white/10 border-white/10"
                                onClick={() => {
                                    setSelectedTemplate(template.type);
                                    setResult(null);
                                }}
                            >
                                <div className="flex items-start justify-between mb-4">
                                    <div className="p-3 bg-white/5 rounded-xl group-hover:bg-white/10 transition-colors">
                                        <Zap className="w-6 h-6 text-yellow-400" />
                                    </div>
                                    <Award className="w-5 h-5 text-white/20" />
                                </div>
                                <h4 className="font-bold text-xl text-white mb-2">{template.name}</h4>
                                <p className="text-sm text-white/60 mb-4 line-clamp-2">{template.description}</p>
                                <div className="pt-4 border-t border-white/5">
                                    <p className="text-xs text-white/40 uppercase tracking-wider mb-1">Best For</p>
                                    <p className="text-sm text-white/80">{template.best_for}</p>
                                </div>
                            </div>
                        </DialogTrigger>
                        <DialogContent className="bg-[#0a0a0a]/95 backdrop-blur-xl border-white/10 text-white max-w-4xl max-h-[85vh] overflow-y-auto sm:rounded-3xl shadow-2xl">
                            <DialogHeader>
                                <DialogTitle className="text-2xl font-bold">Generate {template.name}</DialogTitle>
                                <DialogDescription className="text-white/60">
                                    Enter your topic and keywords to generate a GEO-optimized template.
                                </DialogDescription>
                            </DialogHeader>

                            {!result ? (
                                <div className="space-y-6 py-6">
                                    <div className="space-y-2">
                                        <Label className="text-white/80">Topic</Label>
                                        <Input
                                            placeholder="e.g., Best CRM for Small Business"
                                            value={topic}
                                            onChange={(e) => setTopic(e.target.value)}
                                            className="glass-input h-12"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-white/80">Keywords (comma separated)</Label>
                                        <Input
                                            placeholder="e.g., crm, small business, sales software"
                                            value={keywords}
                                            onChange={(e) => setKeywords(e.target.value)}
                                            className="glass-input h-12"
                                        />
                                    </div>
                                    <Button onClick={generate} disabled={loading} className="glass-button-primary w-full py-6 text-lg">
                                        {loading ? 'Generating Template...' : 'Generate Content'}
                                    </Button>
                                </div>
                            ) : (
                                <div className="space-y-8 py-6">
                                    <div className="bg-green-500/10 border border-green-500/20 p-6 rounded-2xl">
                                        <h3 className="font-bold text-green-400 mb-3 flex items-center text-lg">
                                            <Check className="w-5 h-5 mr-2" /> Template Generated Successfully
                                        </h3>
                                        <div className="text-sm text-green-300/80">
                                            <strong className="text-green-300 block mb-2">Optimization Tips:</strong>
                                            <ul className="list-disc list-inside space-y-1">
                                                {result.optimization_tips.map((tip: string, i: number) => (
                                                    <li key={i}>{tip}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        <Label className="font-bold text-white text-lg">Structure & Example Content</Label>
                                        <div className="bg-black/40 p-6 rounded-2xl border border-white/10 font-mono text-sm whitespace-pre-wrap text-white/80 shadow-inner">
                                            {result.structure.join('\n')}
                                            {'\n\n--- EXAMPLE CONTENT ---\n\n'}
                                            {result.example_content}
                                        </div>
                                    </div>

                                    <div className="flex justify-end pt-4">
                                        <Button variant="outline" onClick={() => setResult(null)} className="glass-button border-white/20">Generate Another</Button>
                                    </div>
                                </div>
                            )}
                        </DialogContent>
                    </Dialog>
                ))}
            </div>
        </div>
    );
}
