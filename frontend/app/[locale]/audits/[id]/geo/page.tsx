"use client";

import { useEffect, useState, useRef } from "react";
import {
  useParams,
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  ArrowLeft,
  TrendingUp,
  Target,
  Award,
  FileText,
  Sparkles,
  BarChart3,
  Search,
  ShoppingBag,
  PenSquare,
} from "lucide-react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import {
  CitationsTableSkeleton,
  HistorySkeleton,
  QueryDiscoverySkeleton,
  CompetitorAnalysisSkeleton,
  SchemaGeneratorSkeleton,
  ContentTemplatesSkeleton,
  ContentAnalyzeSkeleton,
} from "./components/skeletons";

// Lazy load heavy tab components with optimized loading states
const RecentCitationsTable = dynamic(
  () => import("./components/RecentCitationsTable"),
  {
    ssr: false,
    loading: () => <CitationsTableSkeleton />,
  },
);
const CitationHistory = dynamic(() => import("./components/CitationHistory"), {
  ssr: false,
  loading: () => <HistorySkeleton />,
});
const QueryDiscovery = dynamic(() => import("./components/QueryDiscovery"), {
  ssr: false,
  loading: () => <QueryDiscoverySkeleton />,
});
const CompetitorAnalysis = dynamic(
  () => import("./components/CompetitorAnalysis"),
  {
    ssr: false,
    loading: () => <CompetitorAnalysisSkeleton />,
  },
);
const SchemaGenerator = dynamic(() => import("./components/SchemaGenerator"), {
  ssr: false,
  loading: () => <SchemaGeneratorSkeleton />,
});
const SchemaMultipleGenerator = dynamic(
  () => import("./components/SchemaMultipleGenerator"),
  {
    ssr: false,
    loading: () => <SchemaGeneratorSkeleton />,
  },
);
const ContentTemplates = dynamic(
  () => import("./components/ContentTemplates"),
  {
    ssr: false,
    loading: () => <ContentTemplatesSkeleton />,
  },
);
const ContentAnalyze = dynamic(() => import("./components/ContentAnalyze"), {
  ssr: false,
  loading: () => <ContentAnalyzeSkeleton />,
});
const CommerceCampaign = dynamic(
  () => import("./components/CommerceCampaign"),
  {
    ssr: false,
    loading: () => <ContentTemplatesSkeleton />,
  },
);
const ArticleEngine = dynamic(() => import("./components/ArticleEngine"), {
  ssr: false,
  loading: () => <ContentTemplatesSkeleton />,
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
const DEFAULT_TAB = "opportunities";

const TAB_OPTIONS = [
  { value: "opportunities", label: "Top Opportunities", group: "Visibility" },
  { value: "citations", label: "Recent Citations", group: "Visibility" },
  { value: "history", label: "Citation History", group: "Visibility" },
  { value: "query", label: "Query Discovery", group: "Intelligence" },
  { value: "competitors", label: "Competitors", group: "Intelligence" },
  { value: "commerce", label: "Ecommerce Query Analyzer", group: "Growth" },
  { value: "article-engine", label: "Article Engine", group: "Growth" },
  { value: "schema", label: "Schema Generator", group: "Structured Data" },
  {
    value: "schema-multiple",
    label: "Schema Multiple",
    group: "Structured Data",
  },
  { value: "templates", label: "Content Templates", group: "Content" },
  { value: "content-analyze", label: "Analyze Content", group: "Content" },
] as const;

const TAB_SET: ReadonlySet<string> = new Set(
  TAB_OPTIONS.map((option) => option.value),
);
const getSafeTab = (tab: string | null) =>
  tab && TAB_SET.has(tab) ? tab : DEFAULT_TAB;

export default function GEODashboardPage() {
  const params = useParams();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const auditId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<GEODashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(() =>
    getSafeTab(searchParams.get("tab")),
  );
  const hasPreloaded = useRef(false);
  const requestIdRef = useRef(0);

  const backendUrl = API_URL;

  // A) Sync active tab with URL param.
  useEffect(() => {
    const nextTab = getSafeTab(searchParams.get("tab"));
    setActiveTab((prev) => (prev === nextTab ? prev : nextTab));
  }, [searchParams]);

  // Pre-load components after initial render for instant tab switching
  useEffect(() => {
    if (hasPreloaded.current) return;

    // Wait for main content to render, then preload in background
    const preloadTimer = setTimeout(() => {
      hasPreloaded.current = true;
      const preload = () => {
        import("./components/RecentCitationsTable");
        import("./components/CitationHistory");
        import("./components/QueryDiscovery");
        import("./components/CompetitorAnalysis");
        import("./components/SchemaGenerator");
        import("./components/SchemaMultipleGenerator");
        import("./components/ContentTemplates");
        import("./components/ContentAnalyze");
        import("./components/CommerceCampaign");
        import("./components/ArticleEngine");
      };

      if (typeof window !== "undefined" && "requestIdleCallback" in window) {
        (
          window as Window & { requestIdleCallback?: (cb: () => void) => void }
        ).requestIdleCallback?.(preload);
      } else {
        setTimeout(preload, 100);
      }
    }, 1500);

    return () => clearTimeout(preloadTimer);
  }, []);

  // B) Hydrate from local cache once per audit.
  useEffect(() => {
    if (!auditId || typeof window === "undefined") return;

    setError(null);
    setLoading(true);

    const cacheKey = getCacheKey(auditId);
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        setData(parsed);
        setLoading(false);
      } catch {
        // Ignore invalid cache and continue with remote fetch.
      }
    }
  }, [auditId]);

  // C) Fetch dashboard once per audit/backend with cancellation + stale response guard.
  useEffect(() => {
    if (!auditId) return;

    const cacheKey = getCacheKey(auditId);
    const requestId = ++requestIdRef.current;
    const controller = new AbortController();

    const fetchData = async () => {
      try {
        const res = await fetchWithBackendAuth(
          `${backendUrl}/api/geo/dashboard/${auditId}`,
          {
            signal: controller.signal,
          },
        );
        if (!res.ok) throw new Error("Failed to fetch GEO data");
        const geoData = await res.json();
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return;
        }
        setData(geoData);
        setError(null);
        if (typeof window !== "undefined") {
          localStorage.setItem(cacheKey, JSON.stringify(geoData));
        }
      } catch (err: any) {
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return;
        }
        const hasCachedData =
          typeof window !== "undefined" &&
          Boolean(localStorage.getItem(cacheKey));
        if (!hasCachedData) {
          setError(err?.message || "Failed to fetch GEO data");
        }
      } finally {
        if (!controller.signal.aborted && requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => controller.abort();
  }, [auditId, backendUrl]);

  const handleTabChange = (nextTab: string) => {
    const safeTab = TAB_SET.has(nextTab) ? nextTab : DEFAULT_TAB;
    setActiveTab(safeTab);

    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", safeTab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const startCitationTracking = async () => {
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/geo/citation-tracking/start`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audit_id: Number(auditId),
            industry: "general",
            keywords: [],
            llm_name: "kimi",
          }),
        },
      );
      if (res.ok) {
        alert("Citation tracking started! Refresh in a few minutes.");
      }
    } catch (err) {
      console.error(err);
    }
  };

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
            <Button
              variant="ghost"
              className="text-muted-foreground hover:text-foreground hover:bg-muted/40 mb-6 pl-0"
            >
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

            <Button
              onClick={startCitationTracking}
              className="glass-button-primary px-8 py-6 text-lg"
            >
              <Sparkles className="w-5 h-5 mr-3" />
              Start Tracking
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-700 dark:text-amber-300">
            Dashboard summary is still loading. You can use all GEO tools while
            we retry.
          </div>
        )}

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
          <div className="glass-card p-6 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <Target className="w-24 h-24 text-brand" />
            </div>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">
              Citation Rate
            </h3>
            <div className="text-4xl font-bold text-foreground mb-1">
              {citationRate.toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              of queries mention you
            </p>
          </div>

          <div className="glass-card p-6 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <TrendingUp className="w-24 h-24 text-emerald-600" />
            </div>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">
              Total Mentions
            </h3>
            <div className="text-4xl font-bold text-emerald-600 mb-1">
              {totalMentions}
            </div>
            <p className="text-xs text-muted-foreground">in last 30 days</p>
          </div>

          <div className="glass-card p-6 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <Search className="w-24 h-24 text-sky-600" />
            </div>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">
              Opportunities
            </h3>
            <div className="text-4xl font-bold text-sky-600 mb-1">
              {opportunities.length}
            </div>
            <p className="text-xs text-muted-foreground">
              high potential queries
            </p>
          </div>

          <div className="glass-card p-6 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <BarChart3 className="w-24 h-24 text-brand" />
            </div>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">
              Sentiment
            </h3>
            <div className="flex gap-4 items-end h-10">
              <div className="flex flex-col items-center">
                <div className="h-1 w-8 bg-green-500/20 rounded-full overflow-hidden mb-1">
                  <div
                    className="h-full bg-green-500"
                    style={{ width: "100%" }}
                  ></div>
                </div>
                <span className="text-lg font-bold text-emerald-600">
                  {sentiment.positive || 0}
                </span>
              </div>
              <div className="flex flex-col items-center">
                <div className="h-1 w-8 bg-muted/40 rounded-full overflow-hidden mb-1">
                  <div
                    className="h-full bg-muted-foreground/60"
                    style={{ width: "100%" }}
                  ></div>
                </div>
                <span className="text-lg font-bold text-muted-foreground">
                  {sentiment.neutral || 0}
                </span>
              </div>
              <div className="flex flex-col items-center">
                <div className="h-1 w-8 bg-red-500/20 rounded-full overflow-hidden mb-1">
                  <div
                    className="h-full bg-red-500"
                    style={{ width: "100%" }}
                  ></div>
                </div>
                <span className="text-lg font-bold text-red-600">
                  {sentiment.negative || 0}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Tabs */}
        <Tabs
          value={activeTab}
          onValueChange={handleTabChange}
          className="space-y-8"
        >
          <div className="w-full md:max-w-md">
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
              Tool menu
            </p>
            <Select value={activeTab} onValueChange={handleTabChange}>
              <SelectTrigger className="w-full bg-muted/40 border-border rounded-xl">
                <SelectValue placeholder="Select a GEO tool" />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border/70">
                {[
                  "Visibility",
                  "Intelligence",
                  "Growth",
                  "Structured Data",
                  "Content",
                ].map((group) => (
                  <SelectGroup key={group}>
                    <SelectLabel>{group}</SelectLabel>
                    {TAB_OPTIONS.filter((option) => option.group === group).map(
                      (option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ),
                    )}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          </div>

          <TabsContent
            value="opportunities"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-blue-500/20 rounded-xl">
                  <Target className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Query Opportunities
                  </h2>
                  <p className="text-muted-foreground">
                    Queries that don&apos;t mention you yet but have high
                    potential
                  </p>
                </div>
              </div>

              {loading && !data ? (
                <div className="text-center py-12 bg-muted/30 rounded-2xl border border-dashed border-border">
                  <p className="text-muted-foreground">
                    Loading opportunities...
                  </p>
                </div>
              ) : opportunities.length === 0 ? (
                <div className="text-center py-12 bg-muted/30 rounded-2xl border border-dashed border-border">
                  <p className="text-muted-foreground">
                    No opportunities discovered yet. Run Query Discovery to find
                    them.
                  </p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {opportunities.map((opp, idx) => (
                    <div
                      key={idx}
                      className="group bg-muted/30 hover:bg-muted/50 border border-border rounded-2xl p-6 transition-all duration-300"
                    >
                      <div className="flex justify-between items-start mb-3">
                        <h4 className="font-semibold text-xl text-foreground group-hover:text-brand transition-colors">
                          {opp.query}
                        </h4>
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

          <TabsContent
            value="citations"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-green-500/20 rounded-xl">
                  <TrendingUp className="w-6 h-6 text-green-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Recent Citations
                  </h2>
                  <p className="text-muted-foreground">
                    Where your brand was mentioned in LLM responses
                  </p>
                </div>
              </div>
              <RecentCitationsTable
                auditId={Number(auditId)}
                backendUrl={backendUrl}
              />
            </div>
          </TabsContent>

          <TabsContent
            value="history"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-green-500/20 rounded-xl">
                  <TrendingUp className="w-6 h-6 text-green-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Citation History
                  </h2>
                  <p className="text-muted-foreground">
                    Aggregated history for monthly tracking
                  </p>
                </div>
              </div>
              <CitationHistory
                auditId={Number(auditId)}
                backendUrl={backendUrl}
              />
            </div>
          </TabsContent>

          <TabsContent
            value="query"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-blue-500/20 rounded-xl">
                  <Search className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Query Discovery
                  </h2>
                  <p className="text-muted-foreground">
                    Discover queries and opportunities for LLM citations
                  </p>
                </div>
              </div>
              <QueryDiscovery
                auditId={Number(auditId)}
                backendUrl={backendUrl}
              />
            </div>
          </TabsContent>

          <TabsContent
            value="competitors"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-brand/10 rounded-xl">
                  <BarChart3 className="w-6 h-6 text-brand" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Competitor Analysis
                  </h2>
                  <p className="text-muted-foreground">
                    Run analysis and benchmark against competitors
                  </p>
                </div>
              </div>
              <CompetitorAnalysis
                auditId={Number(auditId)}
                backendUrl={backendUrl}
              />
            </div>
          </TabsContent>

          <TabsContent
            value="commerce"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-emerald-500/20 rounded-xl">
                  <ShoppingBag className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Ecommerce Query Analyzer
                  </h2>
                  <p className="text-muted-foreground">
                    Analyze one query at a time and learn how to beat the
                    current #1 result.
                  </p>
                </div>
              </div>
              <CommerceCampaign
                auditId={Number(auditId)}
                backendUrl={backendUrl}
              />
            </div>
          </TabsContent>

          <TabsContent
            value="article-engine"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-indigo-500/20 rounded-xl">
                  <PenSquare className="w-6 h-6 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Article Engine
                  </h2>
                  <p className="text-muted-foreground">
                    Generate X GEO/SEO articles grounded in your audit and
                    competitor gaps.
                  </p>
                </div>
              </div>
              <ArticleEngine
                auditId={Number(auditId)}
                backendUrl={backendUrl}
              />
            </div>
          </TabsContent>

          <TabsContent
            value="schema"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-brand/10 rounded-xl">
                  <FileText className="w-6 h-6 text-brand" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Schema.org Generator
                  </h2>
                  <p className="text-muted-foreground">
                    Generate optimized Schema.org for better LLM understanding
                  </p>
                </div>
              </div>
              <SchemaGenerator backendUrl={backendUrl} />
            </div>
          </TabsContent>

          <TabsContent
            value="schema-multiple"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-brand/10 rounded-xl">
                  <FileText className="w-6 h-6 text-brand" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Multiple Schemas
                  </h2>
                  <p className="text-muted-foreground">
                    Generate multiple suggested schemas for a page
                  </p>
                </div>
              </div>
              <SchemaMultipleGenerator backendUrl={backendUrl} />
            </div>
          </TabsContent>

          <TabsContent
            value="templates"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-pink-500/20 rounded-xl">
                  <Award className="w-6 h-6 text-pink-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Content Templates
                  </h2>
                  <p className="text-muted-foreground">
                    GEO-optimized content templates for maximum visibility
                  </p>
                </div>
              </div>
              <ContentTemplates backendUrl={backendUrl} />
            </div>
          </TabsContent>

          <TabsContent
            value="content-analyze"
            className="transition-all duration-300 ease-out data-[state=inactive]:opacity-0 data-[state=active]:opacity-100"
          >
            <div className="glass-card p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-pink-500/20 rounded-xl">
                  <Award className="w-6 h-6 text-pink-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Analyze Content for GEO
                  </h2>
                  <p className="text-muted-foreground">
                    Analyze freeform content to identify GEO gaps.
                  </p>
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
