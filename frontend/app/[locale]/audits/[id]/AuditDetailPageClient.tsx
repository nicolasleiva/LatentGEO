"use client";

import {
  startTransition,
  useDeferredValue,
  useEffect,
  useState,
  useCallback,
  useMemo,
  useRef,
} from "react";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import logger from "@/lib/logger";
import AuditPipelineDiagnostics from "@/components/audit-pipeline-diagnostics";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  ExternalLink,
  Globe,
  AlertTriangle,
  CheckCircle,
  Clock,
  FileText,
  Target,
  Search,
  Link as LinkIcon,
  TrendingUp,
  Edit,
  Sparkles,
  Github,
  GitPullRequest,
  ShoppingBag,
  PenSquare,
  Gauge,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuditSSE } from "@/hooks/useAuditSSE";
import { usePdfGeneration } from "@/hooks/usePdfGeneration";
import { usePageSpeedGeneration } from "@/hooks/usePageSpeedGeneration";
import { API_URL } from "@/lib/api-client";
import { fetchWithBackendAuth } from "@/lib/backend-auth";
import { formatStableDate } from "@/lib/dates";
import { getExternalIntelligenceBanner } from "@/lib/external-intelligence-status";
import { downloadAuditPdf } from "@/lib/pdf-download";

// Dynamic imports for heavy components
const CoreWebVitalsChart = dynamic(
  () =>
    import("@/components/core-web-vitals-chart").then(
      (mod) => mod.CoreWebVitalsChart,
    ),
  { ssr: false },
);
const KeywordGapChart = dynamic(
  () =>
    import("@/components/keyword-gap-chart").then((mod) => mod.KeywordGapChart),
  { ssr: false },
);
const IssuesHeatmap = dynamic(
  () => import("@/components/issues-heatmap").then((mod) => mod.IssuesHeatmap),
  { ssr: false },
);
const HubSpotIntegration = dynamic(
  () =>
    import("@/components/hubspot-integration").then(
      (mod) => mod.HubSpotIntegration,
    ),
  { ssr: false },
);
const AuditChatFlow = dynamic(
  () => import("@/components/audit-chat-flow").then((mod) => mod.AuditChatFlow),
  { ssr: false },
);
const AIProcessingScreen = dynamic(
  () =>
    import("@/components/ai-processing-screen").then(
      (mod) => mod.AIProcessingScreen,
    ),
  { ssr: false },
);
const AuditPageSpeedDiagnostics = dynamic(
  () => import("./AuditPageSpeedDiagnostics"),
  {
    ssr: false,
    loading: () => <DeferredSectionCard title="Loading raw diagnostics..." />,
  },
);
const AuditPageFindingsSection = dynamic(
  () => import("./AuditPageFindingsSection"),
  {
    ssr: false,
    loading: () => <DeferredSectionCard title="Loading page findings..." />,
  },
);
const AuditCompetitiveBenchmarkSection = dynamic(
  () => import("./AuditCompetitiveBenchmarkSection"),
  {
    ssr: false,
    loading: () => (
      <DeferredSectionCard title="Loading competitive benchmark..." />
    ),
  },
);
const AuditNarrativeTab = dynamic(() => import("./AuditNarrativeTab"), {
  ssr: false,
  loading: () => <DeferredSectionCard title="Loading narrative report..." />,
});
const AuditFixPlanTab = dynamic(() => import("./AuditFixPlanTab"), {
  ssr: false,
  loading: () => <DeferredSectionCard title="Loading execution plan..." />,
});

const safeHostname = (value?: string): string => {
  if (!value) return "";
  try {
    return new URL(value).hostname.replace("www.", "");
  } catch {
    const cleaned = value.replace(/^https?:\/\//, "").replace(/^www\./, "");
    return cleaned.split("/")[0] || cleaned;
  }
};

const normalizeCategory = (value?: string) => {
  if (!value) return "Unclassified";
  const lowered = value.toLowerCase();
  if (
    lowered.includes("unknown category") ||
    lowered.includes("unknown") ||
    lowered.includes("desconocida")
  ) {
    return "Unclassified";
  }
  const removable = new Set([
    "nuestro",
    "nuestra",
    "nuestros",
    "nuestras",
    "our",
    "my",
    "your",
  ]);
  const tokens = value.match(/[A-Za-zÀ-ÿ0-9&+\-]+/g) || [];
  const cleaned = tokens
    .filter((t) => !removable.has(t.toLowerCase()))
    .join(" ")
    .trim();
  return cleaned || "Unclassified";
};

const GEO_DASHBOARD_CACHE_PREFIX = "geo-dashboard-";
const REPORT_NOT_READY_MESSAGE =
  "Narrative report not ready yet. Generate the PDF once to materialize it.";
const FIX_PLAN_NOT_READY_MESSAGE =
  "Execution plan will be available after the PDF generation step completes.";
const INITIAL_PAGE_FINDINGS_COUNT = 6;
const INITIAL_COMPETITOR_TABLE_COUNT = 5;
type GeoWarmTab = "commerce" | "article-engine";

type AuditDetailPageClientProps = {
  auditId?: string;
  locale?: string;
  initialAudit?: any | null;
  initialPages?: any[];
  initialCompetitors?: any[];
  initialAuditIsOverview?: boolean;
};

const resolveInitialCompetitors = (audit: any, competitors?: any[]): any[] => {
  if (Array.isArray(competitors) && competitors.length > 0) {
    return competitors;
  }
  if (Array.isArray(audit?.competitor_audits)) {
    return audit.competitor_audits;
  }
  return [];
};

function DeferredSectionCard({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div
      className="mb-8 rounded-3xl border border-border/70 bg-card p-8 shadow-sm"
      style={{ contentVisibility: "auto", containIntrinsicSize: "1px 420px" }}
    >
      <div className="h-5 w-48 animate-pulse rounded bg-muted/60" />
      {description ? (
        <div className="mt-3 h-4 w-72 animate-pulse rounded bg-muted/40" />
      ) : null}
      <div className="mt-6 space-y-3">
        <div className="h-24 animate-pulse rounded-2xl bg-muted/40" />
        <div className="h-24 animate-pulse rounded-2xl bg-muted/40" />
      </div>
      <div className="mt-4 text-xs text-muted-foreground">{title}</div>
    </div>
  );
}

export default function AuditDetailPageClient({
  auditId: auditIdProp,
  locale: localeProp,
  initialAudit = null,
  initialPages = [],
  initialCompetitors,
  initialAuditIsOverview = false,
}: AuditDetailPageClientProps) {
  const params = useParams<{ locale?: string; id?: string }>();
  const router = useRouter();
  const auditId =
    typeof auditIdProp === "string" && auditIdProp
      ? auditIdProp
      : (params.id ?? "");
  const locale =
    typeof localeProp === "string" && localeProp
      ? localeProp
      : typeof params.locale === "string"
        ? params.locale
        : "en";
  const localePrefix = `/${locale}`;

  const [audit, setAudit] = useState<any>(initialAudit);
  const [pages, setPages] = useState<any[]>(initialPages);
  const [competitors, setCompetitors] = useState<any[]>(
    resolveInitialCompetitors(initialAudit, initialCompetitors),
  );
  const pagesRef = useRef(pages);
  const competitorsRef = useRef(competitors);
  const [loading, setLoading] = useState(!initialAudit);
  const [pageSpeedData, setPageSpeedData] = useState<any>(
    initialAudit?.pagespeed_data ?? null,
  );
  const [keywordGapData, setKeywordGapData] = useState<any>(null);
  const [hasChatCompleted, setHasChatCompleted] = useState(false);

  const backendUrl = API_URL;
  const {
    state: pdfState,
    generate: generatePdfJob,
    isBusy: pdfGenerating,
  } = usePdfGeneration({
    auditId,
    autoDownload: true,
  });
  const {
    state: pageSpeedState,
    generate: generatePageSpeedJob,
    isBusy: pageSpeedGenerating,
  } = usePageSpeedGeneration({
    auditId,
  });
  const [activeTab, setActiveTab] = useState<
    "overview" | "report" | "fix-plan"
  >("overview");
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportMessage, setReportMessage] = useState<string | null>(null);
  const [fixPlan, setFixPlan] = useState<any[] | null>(null);
  const [fixPlanLoading, setFixPlanLoading] = useState(false);
  const [fixPlanMessage, setFixPlanMessage] = useState<string | null>(null);
  const [showPageSpeedDetails, setShowPageSpeedDetails] = useState(false);
  const [showAllPageFindings, setShowAllPageFindings] = useState(false);
  const [showFullBenchmark, setShowFullBenchmark] = useState(false);
  const deferredPages = useDeferredValue(pages);

  useEffect(() => {
    pagesRef.current = pages;
  }, [pages]);

  useEffect(() => {
    competitorsRef.current = competitors;
  }, [competitors]);
  const deferredCompetitors = useDeferredValue(competitors);
  const categoryDisplay = useMemo(
    () =>
      normalizeCategory(
        audit?.external_intelligence?.category || audit?.category,
      ),
    [audit],
  );
  const languageDisplay = audit?.language || "en";
  const runtimeDiagnostics = useMemo(
    () => audit?.runtime_diagnostics || audit?.diagnostics_summary || [],
    [audit?.diagnostics_summary, audit?.runtime_diagnostics],
  );
  const pdfStatusNotice = useMemo(() => {
    if (pdfState.status === "queued") {
      return "PDF generation queued. You can keep working while it finishes.";
    }
    if (pdfState.status === "waiting" && pdfState.waiting_on === "pagespeed") {
      return "PDF queued and waiting for the active PageSpeed pipeline to finish.";
    }
    if (pdfState.status === "running") {
      return "PDF generation in progress.";
    }
    if (pdfState.status === "completed" && pdfState.download_ready) {
      return "PDF ready to download.";
    }
    if (pdfState.status === "failed") {
      return pdfState.error?.message || "PDF generation failed.";
    }
    return null;
  }, [pdfState]);
  const pageSpeedStatusNotice = useMemo(() => {
    if (pageSpeedState.status === "queued") {
      return "PageSpeed queued. It continues in the background while you navigate the audit.";
    }
    if (pageSpeedState.status === "running") {
      return "PageSpeed analysis in progress.";
    }
    if (
      pageSpeedState.status === "completed" &&
      (pageSpeedState.pagespeed_available ||
        pageSpeedData ||
        audit?.pagespeed_data)
    ) {
      return "PageSpeed ready.";
    }
    if (pageSpeedState.status === "failed") {
      return (
        pageSpeedState.error?.message ||
        pageSpeedState.warnings[0] ||
        "PageSpeed analysis failed."
      );
    }
    return null;
  }, [audit?.pagespeed_data, pageSpeedData, pageSpeedState]);
  const externalIntelBanner = useMemo(
    () => getExternalIntelligenceBanner(audit?.external_intelligence),
    [audit?.external_intelligence],
  );
  const geoRoutes = useMemo(() => {
    const toolsBase = `${localePrefix}/audits/${auditId}`;
    return {
      geoDashboard: `${toolsBase}/geo`,
      keywords: `${toolsBase}/keywords`,
      backlinks: `${toolsBase}/backlinks`,
      rankTracking: `${toolsBase}/rank-tracking`,
      contentEditor: `${localePrefix}/tools/content-editor`,
      aiContent: `${toolsBase}/ai-content`,
      geoCommerce: `${toolsBase}/geo?tab=commerce`,
      geoArticleEngine: audit?.intake_profile?.add_articles
        ? `${toolsBase}/geo?tab=article-engine&articleCount=${Math.max(1, Math.min(12, Number(audit?.intake_profile?.article_count) || 3))}`
        : `${toolsBase}/geo?tab=article-engine`,
      githubAutoFix: `${toolsBase}/github-auto-fix`,
      odooDelivery: `${toolsBase}/odoo-delivery`,
    };
  }, [audit?.intake_profile, auditId, localePrefix]);
  const geoWarmupStateRef = useRef<{
    auditId: string | null;
    inFlight: boolean;
  }>({
    auditId: null,
    inFlight: false,
  });
  const geoWarmedTabsRef = useRef<Set<GeoWarmTab>>(new Set());

  const warmGeoTabModule = useCallback((tab: GeoWarmTab) => {
    if (geoWarmedTabsRef.current.has(tab)) return;
    geoWarmedTabsRef.current.add(tab);
    if (tab === "commerce") {
      void import("./geo/components/CommerceCampaign");
      return;
    }
    void import("./geo/components/ArticleEngine");
  }, []);

  const warmGeoDashboardCache = useCallback(async () => {
    if (!auditId || typeof window === "undefined") return;

    const cacheKey = `${GEO_DASHBOARD_CACHE_PREFIX}${auditId}`;
    if (localStorage.getItem(cacheKey)) return;

    const warmState = geoWarmupStateRef.current;
    if (warmState.inFlight && warmState.auditId === auditId) return;

    warmState.auditId = auditId;
    warmState.inFlight = true;
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/geo/dashboard/${auditId}`,
      );
      if (!res.ok) return;
      const geoData = await res.json();
      localStorage.setItem(cacheKey, JSON.stringify(geoData));
    } catch {
      // Best-effort warm-up only; GEO page still fetches live data on entry.
    } finally {
      if (geoWarmupStateRef.current.auditId === auditId) {
        geoWarmupStateRef.current.inFlight = false;
      }
    }
  }, [auditId, backendUrl]);

  const warmGeoNavigation = useCallback(
    (route: string, tab?: GeoWarmTab) => {
      const prefetch = router.prefetch;
      if (typeof prefetch === "function") {
        try {
          prefetch(route);
        } catch {
          // no-op in environments where prefetch is unavailable
        }
      }
      void warmGeoDashboardCache();
      if (tab) {
        warmGeoTabModule(tab);
      }
    },
    [router, warmGeoDashboardCache, warmGeoTabModule],
  );

  const getGeoWarmLinkProps = useCallback(
    (route: string, tab?: GeoWarmTab) => ({
      onMouseEnter: () => warmGeoNavigation(route, tab),
      onFocus: () => warmGeoNavigation(route, tab),
      onTouchStart: () => warmGeoNavigation(route, tab),
    }),
    [warmGeoNavigation],
  );

  const loadReport = useCallback(async () => {
    if (reportLoading || reportMarkdown) return;
    setReportLoading(true);
    setReportMessage(null);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/reports/markdown/${auditId}`,
      );
      if (res.ok) {
        const data = await res.json();
        setReportMarkdown(data?.markdown || "");
        setReportMessage(null);
        return;
      }
      if (res.status === 404) {
        setReportMarkdown("");
        setReportMessage(REPORT_NOT_READY_MESSAGE);
        return;
      }

      const fallbackRes = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/audits/${auditId}/report`,
      );
      if (fallbackRes.ok) {
        const data = await fallbackRes.json();
        setReportMarkdown(
          data?.report || data?.markdown || data?.report_markdown || "",
        );
        setReportMessage(null);
        return;
      }
      if (fallbackRes.status === 404) {
        setReportMarkdown("");
        setReportMessage(REPORT_NOT_READY_MESSAGE);
        return;
      }

      setReportMarkdown("");
      setReportMessage(REPORT_NOT_READY_MESSAGE);
    } catch (err) {
      console.error(err);
      setReportMarkdown("");
      setReportMessage(REPORT_NOT_READY_MESSAGE);
    } finally {
      setReportLoading(false);
    }
  }, [auditId, backendUrl, reportLoading, reportMarkdown]);

  const loadFixPlan = useCallback(async () => {
    if (fixPlanLoading || fixPlan) return;
    setFixPlanLoading(true);
    setFixPlanMessage(null);
    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/audits/${auditId}/fix_plan`,
      );
      if (!res.ok) {
        setFixPlan([]);
        setFixPlanMessage(FIX_PLAN_NOT_READY_MESSAGE);
        return;
      }
      const data = await res.json();
      setFixPlan(
        Array.isArray(data?.fix_plan)
          ? data.fix_plan
          : Array.isArray(data)
            ? data
            : [],
      );
      if (data?.message) {
        setFixPlanMessage(data.message);
      } else if (!Array.isArray(data?.fix_plan) || data.fix_plan.length === 0) {
        setFixPlanMessage(FIX_PLAN_NOT_READY_MESSAGE);
      } else {
        setFixPlanMessage(null);
      }
    } catch (err) {
      console.error(err);
      setFixPlan([]);
      setFixPlanMessage(FIX_PLAN_NOT_READY_MESSAGE);
    } finally {
      setFixPlanLoading(false);
    }
  }, [auditId, backendUrl, fixPlanLoading, fixPlan]);

  const loadSupplementalData = useCallback(
    async (auditData: any) => {
      if (!auditId) return;

      try {
        const currentPages = pagesRef.current;
        const currentCompetitors = competitorsRef.current;
        const shouldLoadCompetitors =
          auditData?.status === "completed" && currentCompetitors.length === 0;

        const [pagesRes, compRes] = await Promise.all([
          currentPages.length === 0
            ? fetchWithBackendAuth(
                `${backendUrl}/api/v1/audits/${auditId}/pages`,
              )
            : Promise.resolve(null),
          shouldLoadCompetitors
            ? fetchWithBackendAuth(
                `${backendUrl}/api/v1/audits/${auditId}/competitors`,
              ).catch(() => null)
            : Promise.resolve(null),
        ]);

        if (pagesRes?.ok) {
          const pagesData = await pagesRes.json();
          startTransition(() => {
            setPages(Array.isArray(pagesData) ? pagesData : []);
          });
        }

        if (compRes?.ok) {
          const compData = await compRes.json();
          if (Array.isArray(compData) && compData.length > 0) {
            startTransition(() => {
              setCompetitors(compData);
            });
          }
        }
      } catch (err) {
        console.error(err);
      }
    },
    [auditId, backendUrl],
  );

  const scheduleSupplementalLoad = useCallback(
    (auditData: any) => {
      if (!auditData || typeof window === "undefined") return undefined;

      if ("requestIdleCallback" in window) {
        const handle = window.requestIdleCallback(
          () => {
            void loadSupplementalData(auditData);
          },
          { timeout: 5000 },
        );
        return () => window.cancelIdleCallback(handle);
      }

      const timer = globalThis.setTimeout(() => {
        void loadSupplementalData(auditData);
      }, 2500);
      return () => globalThis.clearTimeout(timer);
    },
    [loadSupplementalData],
  );

  const MAX_RETRIES = 4;

  const fetchData = useCallback(
    async (attempt = 0) => {
      try {
        const auditRes = await fetchWithBackendAuth(
          `${backendUrl}/api/v1/audits/${auditId}`,
        );
        if (!auditRes.ok) {
          if (auditRes.status === 429) {
            if (attempt >= MAX_RETRIES) {
              throw new Error(`Rate limited after ${MAX_RETRIES + 1} attempts`);
            }
            const backoffMs = Math.min(2000 * (attempt + 1), 10000);
            logger.log(
              `Rate limited, retrying in ${backoffMs}ms... (attempt ${attempt + 1}/${MAX_RETRIES + 1})`,
            );
            await new Promise((resolve) => setTimeout(resolve, backoffMs));
            return fetchData(attempt + 1);
          }
          throw new Error(`Failed to fetch audit: ${auditRes.status}`);
        }
        const auditData = await auditRes.json();
        setAudit(auditData);
        if (
          Array.isArray(auditData?.competitor_audits) &&
          auditData.competitor_audits.length > 0
        ) {
          setCompetitors(auditData.competitor_audits);
        }
        if (
          Array.isArray(auditData?.fix_plan) &&
          auditData.fix_plan.length > 0
        ) {
          setFixPlan(auditData.fix_plan);
          setFixPlanMessage(null);
        }
        if (typeof auditData?.report_markdown === "string") {
          setReportMarkdown(auditData.report_markdown);
          setReportMessage(
            auditData.report_markdown.trim() ? null : REPORT_NOT_READY_MESSAGE,
          );
        }

        setLoading(false);

        if (auditData.pagespeed_data) {
          setPageSpeedData(auditData.pagespeed_data);
        }

        if (typeof window !== "undefined") {
          globalThis.setTimeout(() => {
            void loadSupplementalData(auditData);
          }, 2500);
        }
      } catch (err) {
        console.error(err);
        setLoading(false);
      }
    },
    [auditId, backendUrl, MAX_RETRIES, loadSupplementalData],
  );

  useEffect(() => {
    if (initialAuditIsOverview) {
      void fetchData();
      return undefined;
    }
    if (initialAudit) {
      return scheduleSupplementalLoad(initialAudit);
    }
    fetchData();
    return undefined;
  }, [
    fetchData,
    initialAudit,
    initialAuditIsOverview,
    scheduleSupplementalLoad,
  ]);

  useEffect(() => {
    geoWarmupStateRef.current = { auditId: null, inFlight: false };
    geoWarmedTabsRef.current.clear();
    setShowPageSpeedDetails(false);
    setShowAllPageFindings(false);
    setShowFullBenchmark(false);
  }, [auditId]);

  // Limpiar PageSpeed cuando status cambia a 'running'
  useEffect(() => {
    if (audit?.status === "running") {
      setPageSpeedData(null);
    }
  }, [audit?.status]);

  useEffect(() => {
    if (
      pageSpeedState.status === "completed" ||
      pageSpeedState.status === "failed"
    ) {
      void fetchData();
    }
  }, [fetchData, pageSpeedState.status]);

  // SSE for real-time status updates (replaces polling)
  const shouldSubscribeSSE =
    Boolean(audit) && audit.status !== "completed" && audit.status !== "failed";

  useAuditSSE(auditId, {
    onMessage: (statusData) => {
      setAudit((prev: any) => ({
        ...prev,
        ...statusData,
      }));
    },
    onComplete: (statusData) => {
      fetchData();
    },
    onError: (error) => {
      console.error("SSE error:", error);
    },
    enabled: shouldSubscribeSSE,
  });

  // Memoized helper functions - MUST be before any conditional returns
  const getStatusColor = useMemo(
    () => (status: string) => {
      switch (status) {
        case "completed":
          return "bg-emerald-500/10 text-emerald-600 border-emerald-500/30";
        case "failed":
          return "bg-red-500/10 text-red-600 border-red-500/30";
        default:
          return "bg-amber-500/10 text-amber-600 border-amber-500/30";
      }
    },
    [],
  );

  const getScoreColor = useMemo(
    () => (score: number) => {
      if (score >= 90) return "text-emerald-600";
      if (score >= 50) return "text-amber-500";
      return "text-red-500";
    },
    [],
  );

  const comparisonSites = useMemo(() => {
    if (!audit) return [];
    const baseScore = typeof audit.geo_score === "number" ? audit.geo_score : 0;
    const sites = [
      {
        name: "Your Site",
        score: baseScore,
        color: "hsl(var(--brand))",
      },
      ...deferredCompetitors.slice(0, 5).map((comp: any) => ({
        name: comp.domain || safeHostname(comp.url) || "Competitor",
        score: typeof comp.geo_score === "number" ? comp.geo_score : 0,
        color: "hsl(var(--muted-foreground))",
      })),
    ];
    return sites;
  }, [audit, deferredCompetitors]);

  const statusLabel =
    audit?.status === "running" ? "processing" : (audit?.status ?? "unknown");
  const progressValue = Math.round(audit?.progress ?? 0);
  const visiblePages = showAllPageFindings
    ? deferredPages
    : deferredPages.slice(0, INITIAL_PAGE_FINDINGS_COUNT);
  const visibleBenchmarkCompetitors = showFullBenchmark
    ? deferredCompetitors
    : deferredCompetitors.slice(0, INITIAL_COMPETITOR_TABLE_COUNT);
  const competitorCount =
    deferredCompetitors.length || Number(audit?.competitor_count) || 0;
  const fixPlanCount =
    (Array.isArray(fixPlan) ? fixPlan.length : undefined) ??
    (Array.isArray(audit?.fix_plan) ? audit.fix_plan.length : undefined) ??
    (Number.isFinite(Number(audit?.fix_plan_count))
      ? Number(audit?.fix_plan_count)
      : 0);
  const pagesCount =
    audit?.total_pages && audit.total_pages > 0
      ? audit.total_pages
      : pages.length;
  const coverageBadges = [
    { label: "PageSpeed", ok: Boolean(pageSpeedData || audit?.pagespeed_data) },
    { label: "Competitors", ok: competitorCount > 0 },
    { label: "Fix Plan", ok: fixPlanCount > 0 },
    { label: "Report", ok: Boolean(audit?.report_markdown) },
  ];

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <RefreshCw className="h-8 w-8 animate-spin text-foreground" />
        </main>
      </div>
    );
  }

  const analyzePageSpeed = async () => {
    try {
      await generatePageSpeedJob();
    } catch (err) {
      console.error("PageSpeed exception:", err);
      alert(
        `❌ Error: ${err instanceof Error ? err.message : "Failed to analyze PageSpeed"}`,
      );
    }
  };

  const generatePDF = async () => {
    try {
      if (pdfState.status === "completed" && pdfState.download_ready) {
        await downloadAuditPdf(auditId);
        return;
      }
      await generatePdfJob();
    } catch (err) {
      console.error(err);
      alert(
        `Error with PDF: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    }
  };

  const shouldShowProcessing =
    audit?.status === "running" ||
    audit?.status === "processing" ||
    (audit?.status === "pending" &&
      (hasChatCompleted || (audit?.progress ?? 0) > 0));

  const shouldShowChatOnly =
    audit?.status === "pending" &&
    (audit?.progress ?? 0) === 0 &&
    !hasChatCompleted;

  // Show AI Processing Screen when audit is running
  if (shouldShowProcessing) {
    return <AIProcessingScreen isProcessing={true} />;
  }

  if (shouldShowChatOnly) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 container mx-auto px-4 sm:px-6 py-8 sm:py-10">
          <div className="max-w-6xl mx-auto">
            <AuditChatFlow
              auditId={parseInt(auditId)}
              onComplete={() => {
                setHasChatCompleted(true);
                setAudit((prev: any) => ({
                  ...prev,
                  status: "running",
                  progress: 1,
                }));
                fetchData();
              }}
            />
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col pb-20">
      <Header />

      <main className="flex-1 container mx-auto px-6 py-8">
        {/* Back button */}
        <Button
          variant="ghost"
          onClick={() => router.push(`${localePrefix}/audits`)}
          className="mb-8 text-muted-foreground hover:text-foreground pl-0"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Queue
        </Button>

        {/* Header card */}
        <div className="glass-card p-8 mb-8 relative overflow-hidden">
          <div className="absolute -top-24 -right-24 w-72 h-72 rounded-full bg-brand/10 blur-3xl" />
          <div className="absolute bottom-0 right-0 p-8 opacity-10">
            <Globe className="w-40 h-40 text-foreground" />
          </div>

          <div className="flex flex-col lg:flex-row justify-between items-start relative z-10 gap-8">
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-wide text-muted-foreground">
                <span
                  className={`px-3 py-1 rounded-full border ${getStatusColor(audit?.status ?? "pending")}`}
                >
                  {statusLabel}
                </span>
                <span className="px-3 py-1 rounded-full border border-border bg-muted/40">
                  Progress {progressValue}%
                </span>
                <span className="px-3 py-1 rounded-full border border-border bg-muted/40">
                  Created {formatStableDate(audit?.created_at)}
                </span>
                {audit?.started_at && (
                  <span className="px-3 py-1 rounded-full border border-border bg-muted/40">
                    Started {formatStableDate(audit?.started_at)}
                  </span>
                )}
                {audit?.completed_at && (
                  <span className="px-3 py-1 rounded-full border border-border bg-muted/40">
                    Completed {formatStableDate(audit?.completed_at)}
                  </span>
                )}
              </div>

              <div>
                <h1 className="text-3xl md:text-4xl font-semibold text-foreground break-all">
                  {audit?.domain || safeHostname(audit?.url) || "—"}
                </h1>
                <p className="text-base text-muted-foreground mt-2 flex items-center gap-2 break-all">
                  <Globe className="w-4 h-4" />
                  {audit?.url ?? "—"}
                </p>
              </div>

              <div className="space-y-2">
                <div className="h-2 w-full bg-muted/50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand rounded-full transition-[width]"
                    style={{ width: `${progressValue}%` }}
                  />
                </div>
                <div className="text-xs text-muted-foreground">
                  Pipeline progress
                </div>
              </div>

              {audit?.error_message && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-600">
                  {audit.error_message}
                </div>
              )}
              {audit?.status === "failed" && !audit?.error_message && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700">
                  This run stopped before completion. Review backend logs for
                  diagnostic details.
                </div>
              )}
              {externalIntelBanner && (
                <div
                  className={`rounded-xl px-4 py-3 text-sm flex items-start gap-2 ${
                    externalIntelBanner.severity === "error"
                      ? "border border-amber-500/30 bg-amber-500/10 text-amber-700"
                      : "border border-blue-500/30 bg-blue-500/10 text-blue-700"
                  }`}
                >
                  <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{externalIntelBanner.message}</span>
                </div>
              )}

              <AuditPipelineDiagnostics
                diagnostics={runtimeDiagnostics}
                errorMessage={audit?.error_message}
              />
            </div>

            {audit?.status === "completed" && (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-3">
                  {audit.source === "hubspot" && (
                    <Button
                      onClick={() =>
                        router.push(
                          `${localePrefix}/audits/${auditId}/hubspot-apply`,
                        )
                      }
                      className="bg-[#ff7a59] hover:bg-[#ff7a59]/90 text-white px-6"
                    >
                      <Sparkles className="h-4 w-4 mr-2" />
                      Apply to HubSpot
                    </Button>
                  )}
                  <Button
                    onClick={analyzePageSpeed}
                    disabled={pageSpeedGenerating}
                    className="glass-button px-6"
                  >
                    {pageSpeedGenerating ? (
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Clock className="h-4 w-4 mr-2" />
                    )}
                    {pageSpeedState.status === "queued"
                      ? "Queued PageSpeed"
                      : pageSpeedGenerating ||
                          pageSpeedState.status === "running"
                        ? "Running PageSpeed"
                        : pageSpeedState.pagespeed_available ||
                            Boolean(pageSpeedData || audit?.pagespeed_data)
                          ? "Refresh PageSpeed"
                          : "Run PageSpeed"}
                  </Button>
                  <Button
                    onClick={generatePDF}
                    disabled={pdfGenerating}
                    className="glass-button px-6"
                  >
                    {pdfGenerating ? (
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Download className="h-4 w-4 mr-2" />
                    )}
                    {pdfState.status === "queued"
                      ? "Queued for PDF"
                      : pdfState.status === "waiting"
                        ? "Waiting on PageSpeed"
                        : pdfGenerating || pdfState.status === "running"
                          ? "Building PDF..."
                          : pdfState.status === "completed"
                            ? "Download PDF"
                            : pdfState.status === "failed"
                              ? "Retry PDF"
                              : "Export PDF"}
                  </Button>
                  <Button
                    data-testid="open-geo-dashboard-button"
                    onMouseEnter={() =>
                      warmGeoNavigation(geoRoutes.geoDashboard)
                    }
                    onFocus={() => warmGeoNavigation(geoRoutes.geoDashboard)}
                    onClick={() => {
                      warmGeoNavigation(geoRoutes.geoDashboard);
                      router.push(geoRoutes.geoDashboard);
                    }}
                    className="glass-button-primary px-6"
                  >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open GEO Command Center
                  </Button>
                </div>

                {pdfStatusNotice ? (
                  <p
                    className={`text-sm ${
                      pdfState.status === "failed"
                        ? "text-destructive"
                        : "text-muted-foreground"
                    }`}
                  >
                    {pdfStatusNotice}
                  </p>
                ) : null}

                {pdfState.warnings[0] ? (
                  <p className="text-sm text-amber-600">
                    {pdfState.warnings[0]}
                  </p>
                ) : null}

                {pageSpeedStatusNotice ? (
                  <p
                    className={`text-sm ${
                      pageSpeedState.status === "failed"
                        ? "text-destructive"
                        : pageSpeedState.warnings[0]
                          ? "text-amber-600"
                          : "text-muted-foreground"
                    }`}
                  >
                    {pageSpeedState.warnings[0] || pageSpeedStatusNotice}
                  </p>
                ) : null}
              </div>
            )}
          </div>
        </div>

        {/* Audit signals */}
        {audit && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="glass-panel p-5 rounded-2xl">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
                Context
              </div>
              <div className="text-lg font-semibold text-foreground">
                {categoryDisplay}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                Market:{" "}
                {audit?.external_intelligence?.market || audit?.market || "—"} ·
                Language: {languageDisplay}
              </div>
            </div>
            <div className="glass-panel p-5 rounded-2xl">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
                Coverage
              </div>
              <div className="flex flex-wrap gap-2">
                {coverageBadges.map((badge) => (
                  <span
                    key={badge.label}
                    className={`px-3 py-1 rounded-full border text-xs ${
                      badge.ok
                        ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/30"
                        : "bg-muted/50 text-muted-foreground border-border"
                    }`}
                  >
                    {badge.label}
                  </span>
                ))}
              </div>
            </div>
            <div className="glass-panel p-5 rounded-2xl">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
                Execution Signals
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Pages audited</span>
                  <span className="text-foreground font-semibold">
                    {pagesCount}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">
                    Competitors found
                  </span>
                  <span className="text-foreground font-semibold">
                    {competitorCount}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Fix plan items</span>
                  <span className="text-foreground font-semibold">
                    {fixPlanCount}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Critical issues</span>
                  <span className="text-foreground font-semibold">
                    {audit?.critical_issues ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">High issues</span>
                  <span className="text-foreground font-semibold">
                    {audit?.high_issues ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Medium issues</span>
                  <span className="text-foreground font-semibold">
                    {audit?.medium_issues ?? 0}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        <Tabs
          defaultValue="overview"
          value={activeTab}
          onValueChange={(v) => {
            const nextTab = v as "overview" | "report" | "fix-plan";
            startTransition(() => {
              setActiveTab(nextTab);
            });
            if (nextTab === "report") void loadReport();
            if (nextTab === "fix-plan") void loadFixPlan();
          }}
        >
          <TabsList className="mb-8">
            <TabsTrigger value="overview">Summary</TabsTrigger>
            <TabsTrigger value="report">Narrative</TabsTrigger>
            <TabsTrigger value="fix-plan">Execution Plan</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            {/* Stats cards */}
            {audit && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-muted-foreground">
                    <FileText className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">
                      Pages
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-foreground">
                    {pagesCount}
                  </div>
                </div>
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-red-600/70">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">
                      Critical
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-red-600">
                    {audit.critical_issues ?? 0}
                  </div>
                </div>
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-amber-600/70">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">
                      High
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-amber-600">
                    {audit.high_issues ?? 0}
                  </div>
                </div>
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-amber-500/70">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">
                      Medium
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-amber-500">
                    {audit.medium_issues ?? 0}
                  </div>
                </div>
              </div>
            )}

            {(() => {
              const rawData = pageSpeedData?.data || pageSpeedData;
              const psData =
                rawData?.mobile ||
                (rawData?.performance_score !== undefined ? rawData : null);

              if (!psData) return null;

              return (
                <div className="glass-card p-8 mb-8">
                  <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
                    <Clock className="w-6 h-6 text-brand" />
                    PageSpeed Insights
                  </h2>

                  {/* Category Scores */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">
                        Performance
                      </div>
                      <div
                        className={`text-3xl font-bold ${getScoreColor(psData.performance_score || 0)}`}
                      >
                        {Math.round(psData.performance_score || 0)}
                      </div>
                    </div>
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">
                        Accessibility
                      </div>
                      <div
                        className={`text-3xl font-bold ${getScoreColor(psData.accessibility_score || 0)}`}
                      >
                        {Math.round(psData.accessibility_score || 0)}
                      </div>
                    </div>
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">
                        Best Practices
                      </div>
                      <div
                        className={`text-3xl font-bold ${getScoreColor(psData.best_practices_score || 0)}`}
                      >
                        {Math.round(psData.best_practices_score || 0)}
                      </div>
                    </div>
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">
                        SEO
                      </div>
                      <div
                        className={`text-3xl font-bold ${getScoreColor(psData.seo_score || 0)}`}
                      >
                        {Math.round(psData.seo_score || 0)}
                      </div>
                    </div>
                  </div>

                  {/* Core Web Vitals */}
                  {psData.core_web_vitals && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">
                        Core Web Vitals
                      </h3>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">
                            LCP
                          </div>
                          <div className="text-xl font-bold text-foreground">
                            {(psData.core_web_vitals.lcp / 1000).toFixed(2)}s
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">
                            FID
                          </div>
                          <div className="text-xl font-bold text-foreground">
                            {Math.round(psData.core_web_vitals.fid)}ms
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">
                            CLS
                          </div>
                          <div className="text-xl font-bold text-foreground">
                            {psData.core_web_vitals.cls.toFixed(3)}
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">
                            FCP
                          </div>
                          <div className="text-xl font-bold text-foreground">
                            {(psData.core_web_vitals.fcp / 1000).toFixed(2)}s
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">
                            TTFB
                          </div>
                          <div className="text-xl font-bold text-foreground">
                            {Math.round(psData.core_web_vitals.ttfb)}ms
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Metrics Chart */}
                  <div className="bg-muted/50 rounded-2xl p-4 border border-border mb-6">
                    <CoreWebVitalsChart data={pageSpeedData} />
                  </div>

                  <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-dashed border-border bg-muted/20 p-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">
                        Deep PageSpeed Diagnostics
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        Raw audit traces, screenshots, and low-level
                        recommendations load on demand to keep this summary
                        lighter.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() =>
                        setShowPageSpeedDetails((current) => !current)
                      }
                    >
                      {showPageSpeedDetails
                        ? "Hide Raw Diagnostics"
                        : "Load Raw Diagnostics"}
                    </Button>
                  </div>

                  {showPageSpeedDetails ? (
                    <AuditPageSpeedDiagnostics psData={psData} />
                  ) : null}
                </div>
              );
            })()}

            {/* Tools Section - COMPLETE */}
            {audit?.status === "completed" && (
              <div className="glass-card p-8 mb-8">
                <h2 className="text-2xl font-bold text-foreground mb-6">
                  Execution Tool Suite
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* GEO Dashboard */}
                  <Link
                    href={geoRoutes.geoDashboard}
                    {...getGeoWarmLinkProps(geoRoutes.geoDashboard)}
                    data-testid="geo-tool-card-dashboard"
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-brand/10 rounded-xl">
                        <Target className="w-6 h-6 text-brand" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      GEO Dashboard
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Monitor citations, discovery opportunities, and
                      assistant-facing visibility.
                    </p>
                  </Link>

                  {/* Keywords Research */}
                  <Link
                    href={geoRoutes.keywords}
                    {...getGeoWarmLinkProps(geoRoutes.keywords)}
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-brand/10 rounded-xl">
                        <Search className="w-6 h-6 text-brand" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Keyword Discovery
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Map prompts and queries aligned to demand capture.
                    </p>
                  </Link>

                  {/* Backlinks Analysis */}
                  <Link
                    href={geoRoutes.backlinks}
                    {...getGeoWarmLinkProps(geoRoutes.backlinks)}
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-green-500/20 rounded-xl">
                        <LinkIcon className="w-6 h-6 text-emerald-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Backlink Intelligence
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Evaluate authority signals and high-value linking
                      opportunities.
                    </p>
                  </Link>

                  {/* Rank Tracking */}
                  <Link
                    href={geoRoutes.rankTracking}
                    {...getGeoWarmLinkProps(geoRoutes.rankTracking)}
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-orange-500/20 rounded-xl">
                        <TrendingUp className="w-6 h-6 text-amber-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Rank Tracking
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Track ranking movement and visibility drift over time.
                    </p>
                  </Link>

                  {/* Content Editor */}
                  <Link
                    href={`${geoRoutes.contentEditor}?url=${encodeURIComponent(audit?.url || "")}`}
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-pink-500/20 rounded-xl">
                        <Edit className="w-6 h-6 text-rose-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Content Editor
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Refine page messaging for clarity, intent match, and
                      conversion context.
                    </p>
                  </Link>

                  {/* AI Content Suggestions */}
                  <Link
                    href={geoRoutes.aiContent}
                    {...getGeoWarmLinkProps(geoRoutes.aiContent)}
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-cyan-500/20 rounded-xl">
                        <Sparkles className="w-6 h-6 text-sky-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      AI Content Angles
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Generate editorial angles based on audit findings and
                      gaps.
                    </p>
                  </Link>

                  {/* Commerce LLM */}
                  <Link
                    href={geoRoutes.geoCommerce}
                    {...getGeoWarmLinkProps(geoRoutes.geoCommerce, "commerce")}
                    data-testid="geo-tool-card-commerce"
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-indigo-500/20 rounded-xl">
                        <ShoppingBag className="w-6 h-6 text-indigo-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Ecommerce Query Analyzer
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Analyze commerce prompts to improve citation share and
                      buying-intent traffic.
                    </p>
                  </Link>

                  {/* Article Engine */}
                  <Link
                    href={geoRoutes.geoArticleEngine}
                    {...getGeoWarmLinkProps(
                      geoRoutes.geoArticleEngine,
                      "article-engine",
                    )}
                    data-testid="geo-tool-card-article-engine"
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-violet-500/20 rounded-xl">
                        <PenSquare className="w-6 h-6 text-violet-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Article Engine
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Generate audit-grounded articles designed to close
                      citation and intent gaps.
                    </p>
                  </Link>

                  {/* GitHub Auto-Fix */}
                  <Link
                    href={geoRoutes.githubAutoFix}
                    {...getGeoWarmLinkProps(geoRoutes.githubAutoFix)}
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-brand/10 rounded-xl">
                        <GitPullRequest className="w-6 h-6 text-brand" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      GitHub Auto-Fix
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Create implementation-ready PRs with scoped SEO/GEO
                      changes.
                    </p>
                  </Link>

                  <Link
                    href={geoRoutes.odooDelivery}
                    {...getGeoWarmLinkProps(geoRoutes.odooDelivery)}
                    className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-emerald-500/15 rounded-xl">
                        <Gauge className="w-6 h-6 text-emerald-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Odoo Delivery Pack
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Generate an Odoo-ready delivery pack with validated audit
                      fixes, article deliverables, and ecommerce actions.
                    </p>
                  </Link>

                  {/* HubSpot Auto-Apply */}
                  <Dialog>
                    <DialogTrigger asChild>
                      <button className="group glass-panel p-6 rounded-2xl transition-transform text-left hover:-translate-y-1">
                        <div className="flex items-start justify-between mb-3">
                          <div className="p-3 bg-orange-500/20 rounded-xl">
                            <Sparkles className="w-6 h-6 text-amber-600" />
                          </div>
                          <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                        </div>
                        <h3 className="text-lg font-semibold text-foreground mb-2">
                          HubSpot Auto-Apply
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          Push selected recommendations directly into HubSpot
                          CMS pages.
                        </p>
                      </button>
                    </DialogTrigger>
                    <DialogContent className="glass-card border-border sm:max-w-2xl">
                      <DialogTitle className="text-xl font-bold text-foreground">
                        HubSpot Auto-Apply Integration
                      </DialogTitle>
                      <HubSpotIntegration
                        auditId={auditId}
                        auditUrl={audit?.url || ""}
                      />
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            )}

            <AuditPageFindingsSection
              pages={deferredPages}
              visiblePages={visiblePages}
              remainingCount={Math.max(
                deferredPages.length - visiblePages.length,
                0,
              )}
              onLoadAll={() => setShowAllPageFindings(true)}
            />

            <AuditCompetitiveBenchmarkSection
              audit={audit}
              competitors={deferredCompetitors}
              comparisonSites={comparisonSites}
              visibleCompetitors={visibleBenchmarkCompetitors}
              showFullBenchmark={showFullBenchmark}
              onToggleFullBenchmark={() =>
                setShowFullBenchmark((current) => !current)
              }
              initialCompetitorCount={INITIAL_COMPETITOR_TABLE_COUNT}
              expectedCompetitorCount={competitorCount}
            />
          </TabsContent>

          <TabsContent value="report">
            {activeTab === "report" ? (
              <AuditNarrativeTab
                reportLoading={reportLoading}
                reportMarkdown={reportMarkdown}
                reportMessage={reportMessage}
                fallbackMessage={REPORT_NOT_READY_MESSAGE}
                onRefresh={() => {
                  setReportMarkdown(null);
                  void loadReport();
                }}
              />
            ) : null}
          </TabsContent>

          <TabsContent value="fix-plan">
            {activeTab === "fix-plan" ? (
              <AuditFixPlanTab
                fixPlanLoading={fixPlanLoading}
                fixPlan={fixPlan}
                fixPlanMessage={fixPlanMessage}
                fallbackMessage={FIX_PLAN_NOT_READY_MESSAGE}
                onRefresh={() => {
                  setFixPlan(null);
                  void loadFixPlan();
                }}
              />
            ) : null}
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
