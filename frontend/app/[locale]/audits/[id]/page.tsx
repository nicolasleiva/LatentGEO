"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import logger from "@/lib/logger";
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
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuditSSE } from "@/hooks/useAuditSSE";
import { API_URL } from "@/lib/api";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

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

const safeHostname = (value?: string): string => {
  if (!value) return "";
  try {
    return new URL(value).hostname.replace("www.", "");
  } catch {
    const cleaned = value.replace(/^https?:\/\//, "").replace(/^www\./, "");
    return cleaned.split("/")[0] || cleaned;
  }
};

const formatDate = (value?: string) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString();
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
type GeoWarmTab = "commerce" | "article-engine";

export default function AuditDetailPage() {
  const params = useParams();
  const router = useRouter();
  const auditId = params.id as string;
  const locale = typeof params.locale === "string" ? params.locale : "en";
  const localePrefix = `/${locale}`;

  const [audit, setAudit] = useState<any>(null);
  const [pages, setPages] = useState<any[]>([]);
  const [competitors, setCompetitors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageSpeedData, setPageSpeedData] = useState<any>(null);
  const [keywordGapData, setKeywordGapData] = useState<any>(null);
  const [pageSpeedLoading, setPageSpeedLoading] = useState(false);
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [hasChatCompleted, setHasChatCompleted] = useState(false);

  const backendUrl = API_URL;
  const [activeTab, setActiveTab] = useState<
    "overview" | "report" | "fix-plan"
  >("overview");
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportMessage, setReportMessage] = useState<string | null>(null);
  const [fixPlan, setFixPlan] = useState<any[] | null>(null);
  const [fixPlanLoading, setFixPlanLoading] = useState(false);
  const [fixPlanMessage, setFixPlanMessage] = useState<string | null>(null);
  const categoryDisplay = useMemo(
    () =>
      normalizeCategory(
        audit?.external_intelligence?.category || audit?.category,
      ),
    [audit],
  );
  const languageDisplay = audit?.language || "en";
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
      geoArticleEngine: `${toolsBase}/geo?tab=article-engine`,
      githubAutoFix: `${toolsBase}/github-auto-fix`,
    };
  }, [auditId, localePrefix]);
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
        `${backendUrl}/api/geo/dashboard/${auditId}`,
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
        `${backendUrl}/api/reports/markdown/${auditId}`,
      );
      if (res.ok) {
        const data = await res.json();
        setReportMarkdown(data?.markdown || "");
        setReportMessage(null);
        return;
      }
      if (res.status === 404) {
        setReportMarkdown("");
        setReportMessage(
          "Report not generated. Click Generate PDF to build it.",
        );
        return;
      }

      const fallbackRes = await fetchWithBackendAuth(
        `${backendUrl}/api/audits/${auditId}/report`,
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
        setReportMessage(
          "Report not generated. Click Generate PDF to build it.",
        );
        return;
      }

      setReportMarkdown("");
      setReportMessage("Report not generated. Click Generate PDF to build it.");
    } catch (err) {
      console.error(err);
      setReportMarkdown("");
      setReportMessage("Report not generated. Click Generate PDF to build it.");
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
        `${backendUrl}/api/audits/${auditId}/fix_plan`,
      );
      if (!res.ok) {
        setFixPlan([]);
        setFixPlanMessage(
          "Fix plan will be created when you generate the PDF report.",
        );
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
        setFixPlanMessage(
          "Fix plan will be created when you generate the PDF report.",
        );
      } else {
        setFixPlanMessage(null);
      }
    } catch (err) {
      console.error(err);
      setFixPlan([]);
      setFixPlanMessage(
        "Fix plan will be created when you generate the PDF report.",
      );
    } finally {
      setFixPlanLoading(false);
    }
  }, [auditId, backendUrl, fixPlanLoading, fixPlan]);

  const MAX_RETRIES = 4;

  const fetchData = useCallback(
    async (attempt = 0) => {
      try {
        // Fetch audit first
        const auditRes = await fetchWithBackendAuth(
          `${backendUrl}/api/audits/${auditId}`,
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

        // Stop loading immediately so Chat appears ASAP
        setLoading(false);

        // Fetch pages and competitors in parallel (non-blocking for initial render)
        const [pagesRes, compRes] = await Promise.all([
          fetchWithBackendAuth(`${backendUrl}/api/audits/${auditId}/pages`),
          auditData.status === "completed"
            ? fetchWithBackendAuth(
                `${backendUrl}/api/audits/${auditId}/competitors`,
              ).catch(() => null)
            : Promise.resolve(null),
        ]);

        if (pagesRes.ok) {
          const pagesData = await pagesRes.json();
          setPages(pagesData);
        }

        if (compRes?.ok) {
          const compData = await compRes.json();
          if (Array.isArray(compData) && compData.length > 0) {
            setCompetitors(compData);
          } else if (Array.isArray(auditData?.competitor_audits)) {
            setCompetitors(auditData.competitor_audits);
          }
        } else if (Array.isArray(auditData?.competitor_audits)) {
          setCompetitors(auditData.competitor_audits);
        }

        // Initialize PageSpeed data if available in audit
        if (auditData.pagespeed_data) {
          setPageSpeedData(auditData.pagespeed_data);
        }
      } catch (err) {
        console.error(err);
        setLoading(false);
      }
    },
    [auditId, backendUrl, MAX_RETRIES],
  );

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const routes = [
      geoRoutes.geoDashboard,
      geoRoutes.keywords,
      geoRoutes.backlinks,
      geoRoutes.rankTracking,
      geoRoutes.contentEditor,
      geoRoutes.aiContent,
      geoRoutes.geoCommerce,
      geoRoutes.geoArticleEngine,
      geoRoutes.githubAutoFix,
    ];
    routes.forEach((route) => warmGeoNavigation(route));
  }, [geoRoutes, warmGeoNavigation]);

  useEffect(() => {
    geoWarmupStateRef.current = { auditId: null, inFlight: false };
    geoWarmedTabsRef.current.clear();
  }, [auditId]);

  useEffect(() => {
    if (audit?.status !== "completed") return;
    void warmGeoDashboardCache();

    const preloadTimer = setTimeout(() => {
      warmGeoTabModule("commerce");
      warmGeoTabModule("article-engine");
    }, 1200);

    return () => clearTimeout(preloadTimer);
  }, [audit?.status, warmGeoDashboardCache, warmGeoTabModule]);

  // Limpiar PageSpeed cuando status cambia a 'running'
  useEffect(() => {
    if (audit?.status === "running") {
      setPageSpeedData(null);
    }
  }, [audit?.status]);

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
      ...competitors.slice(0, 5).map((comp: any) => ({
        name: comp.domain || safeHostname(comp.url) || "Competitor",
        score: typeof comp.geo_score === "number" ? comp.geo_score : 0,
        color: "hsl(var(--muted-foreground))",
      })),
    ];
    return sites;
  }, [audit, competitors]);

  const statusLabel =
    audit?.status === "running" ? "processing" : (audit?.status ?? "unknown");
  const progressValue = Math.round(audit?.progress ?? 0);
  const pagesCount =
    audit?.total_pages && audit.total_pages > 0
      ? audit.total_pages
      : pages.length;
  const coverageBadges = [
    { label: "PageSpeed", ok: Boolean(pageSpeedData || audit?.pagespeed_data) },
    { label: "Competitors", ok: competitors.length > 0 },
    { label: "Fix Plan", ok: (audit?.fix_plan?.length ?? 0) > 0 },
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
    setPageSpeedLoading(true);
    try {
      logger.log("Analyzing PageSpeed...");
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/audits/${auditId}/pagespeed`,
        {
          method: "POST",
        },
      );
      logger.log("PageSpeed response:", res.status);
      if (res.ok) {
        const data = await res.json();
        logger.log("PageSpeed data:", data);
        // Use data.data if it exists (new backend response structure)
        setPageSpeedData(data.data || data);
        alert("✅ PageSpeed analysis completed!");
      } else {
        const error = await res
          .json()
          .catch(() => ({ detail: "Unknown error" }));
        console.error("PageSpeed error:", error);
        alert(`❌ Error: ${error.detail || "Failed to analyze PageSpeed"}`);
      }
    } catch (err) {
      console.error("PageSpeed exception:", err);
      alert(
        `❌ Error: ${err instanceof Error ? err.message : "Failed to analyze PageSpeed"}`,
      );
    } finally {
      setPageSpeedLoading(false);
    }
  };

  const generatePDF = async () => {
    if (pdfGenerating) return;
    setPdfGenerating(true);
    try {
      const generateRes = await fetchWithBackendAuth(
        `${backendUrl}/api/audits/${auditId}/generate-pdf`,
        {
          method: "POST",
        },
      );

      if (generateRes.status === 409) {
        const payload = await generateRes.json().catch(() => ({}));
        const retryAfter = Number(payload?.retry_after_seconds || 10);
        alert(`PDF generation already in progress. Retry in ~${retryAfter}s.`);
        return;
      }

      if (!generateRes.ok) {
        const error = await generateRes.json().catch(() => ({}));
        throw new Error(error?.detail || "Unknown error");
      }

      await new Promise((resolve) => setTimeout(resolve, 500));
      const downloadRes = await fetchWithBackendAuth(
        `${backendUrl}/api/audits/${auditId}/download-pdf`,
      );
      if (!downloadRes.ok) {
        const errorPayload = await downloadRes
          .json()
          .catch(() => ({ detail: "Download failed" }));
        throw new Error(errorPayload.detail || "Download failed");
      }
      const pdfBlob = await downloadRes.blob();
      const objectUrl = URL.createObjectURL(pdfBlob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `audit_${auditId}_report.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error(err);
      alert(
        `Error generating PDF: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setPdfGenerating(false);
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
          Back to Audits
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
                  Created {formatDate(audit?.created_at)}
                </span>
                {audit?.started_at && (
                  <span className="px-3 py-1 rounded-full border border-border bg-muted/40">
                    Started {formatDate(audit?.started_at)}
                  </span>
                )}
                {audit?.completed_at && (
                  <span className="px-3 py-1 rounded-full border border-border bg-muted/40">
                    Completed {formatDate(audit?.completed_at)}
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
                    className="h-full bg-brand rounded-full transition-all"
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
                  This audit failed before completion. Check backend logs for
                  the detailed error.
                </div>
              )}
            </div>

            {audit?.status === "completed" && (
              <div className="flex flex-wrap gap-3">
                {audit.source === "hubspot" && (
                  <Button
                    onClick={() =>
                      router.push(`/audits/${auditId}/hubspot-apply`)
                    }
                    className="bg-[#ff7a59] hover:bg-[#ff7a59]/90 text-white px-6"
                  >
                    <Sparkles className="h-4 w-4 mr-2" />
                    Apply to HubSpot
                  </Button>
                )}
                <Button
                  onClick={analyzePageSpeed}
                  disabled={pageSpeedLoading}
                  className="glass-button px-6"
                >
                  {pageSpeedLoading ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Clock className="h-4 w-4 mr-2" />
                  )}
                  Analyze PageSpeed
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
                  {pdfGenerating ? "Generating PDF..." : "PDF Report"}
                </Button>
                <Button
                  data-testid="open-geo-dashboard-button"
                  onMouseEnter={() => warmGeoNavigation(geoRoutes.geoDashboard)}
                  onFocus={() => warmGeoNavigation(geoRoutes.geoDashboard)}
                  onClick={() => {
                    warmGeoNavigation(geoRoutes.geoDashboard);
                    router.push(geoRoutes.geoDashboard);
                  }}
                  className="glass-button-primary px-6"
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open GEO Dashboard
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Audit signals */}
        {audit && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="glass-panel p-5 rounded-2xl">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
                Market Context
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
                Data Coverage
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
                Signals
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
                    {competitors.length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Fix plan items</span>
                  <span className="text-foreground font-semibold">
                    {audit?.fix_plan?.length ?? 0}
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
            setActiveTab(nextTab);
            if (nextTab === "report") loadReport();
            if (nextTab === "fix-plan") loadFixPlan();
          }}
        >
          <TabsList className="mb-8">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="report">Report</TabsTrigger>
            <TabsTrigger value="fix-plan">Fix Plan</TabsTrigger>
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

                  {/* Opportunities */}
                  {psData.opportunities &&
                    Object.keys(psData.opportunities).length > 0 && (
                      <div className="mb-6">
                        <h3 className="text-lg font-semibold text-foreground mb-4">
                          Optimization Opportunities
                        </h3>
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                          {Object.entries(psData.opportunities).map(
                            ([key, data]: [string, any]) =>
                              data &&
                              data.score !== null &&
                              data.score < 0.9 && (
                                <div
                                  key={key}
                                  className="bg-muted/50 p-3 rounded-xl border border-border flex items-start gap-3"
                                >
                                  <AlertTriangle
                                    className={`w-4 h-4 mt-1 flex-shrink-0 ${data.score < 0.5 ? "text-red-500" : "text-amber-500"}`}
                                  />
                                  <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium text-foreground">
                                      {data.title || key.replace(/-/g, " ")}
                                    </div>
                                    {data.displayValue && (
                                      <div className="text-xs text-muted-foreground mt-1">
                                        {data.displayValue}
                                      </div>
                                    )}
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    Score: {Math.round((data.score || 0) * 100)}
                                  </div>
                                </div>
                              ),
                          )}
                        </div>
                      </div>
                    )}

                  {/* Diagnostics */}
                  {psData.diagnostics &&
                    Object.keys(psData.diagnostics).length > 0 && (
                      <div className="mb-6">
                        <h3 className="text-lg font-semibold text-foreground mb-4">
                          Diagnostics
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto">
                          {Object.entries(psData.diagnostics).map(
                            ([key, metric]: [string, any]) =>
                              metric &&
                              metric.displayValue && (
                                <div
                                  key={key}
                                  className="bg-muted/50 p-3 rounded-xl border border-border"
                                >
                                  <div className="text-xs text-muted-foreground">
                                    {metric.title || key.replace(/_/g, " ")}
                                  </div>
                                  <div className="text-sm text-foreground font-medium">
                                    {metric.displayValue}
                                  </div>
                                  {metric.description && (
                                    <div className="text-xs text-muted-foreground mt-1">
                                      {metric.description}
                                    </div>
                                  )}
                                </div>
                              ),
                          )}
                        </div>
                      </div>
                    )}

                  {/* Metadata */}
                  {psData.metadata && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">
                        Audit Information
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {psData.metadata.fetch_time && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">
                              Fetch Time
                            </div>
                            <div className="text-sm text-foreground">
                              {new Date(
                                psData.metadata.fetch_time,
                              ).toLocaleString()}
                            </div>
                          </div>
                        )}
                        {psData.metadata.user_agent && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">
                              User Agent
                            </div>
                            <div className="text-xs text-foreground truncate">
                              {psData.metadata.user_agent}
                            </div>
                          </div>
                        )}
                        {psData.metadata.benchmark_index && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">
                              Benchmark Index
                            </div>
                            <div className="text-sm text-foreground">
                              {psData.metadata.benchmark_index}
                            </div>
                          </div>
                        )}
                        {psData.metadata.network_throttling && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">
                              Network Setting
                            </div>
                            <div className="text-xs text-foreground truncate">
                              {psData.metadata.network_throttling}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Metrics Detail */}
                  {psData.metrics && Object.keys(psData.metrics).length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">
                        Detailed Metrics
                      </h3>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-96 overflow-y-auto">
                        {Object.entries(psData.metrics).map(
                          ([key, value]: [string, any]) => {
                            if (value === null || value === undefined)
                              return null;
                            return (
                              <div
                                key={key}
                                className="bg-muted/50 p-3 rounded-xl border border-border"
                              >
                                <div className="text-xs text-muted-foreground capitalize">
                                  {key.replace(/_/g, " ")}
                                </div>
                                <div className="text-sm font-medium text-foreground">
                                  {typeof value === "number"
                                    ? key.includes("time") ||
                                      key.includes("duration") ||
                                      key.includes("ms")
                                      ? `${Math.round(value)}ms`
                                      : key.includes("score")
                                        ? value.toFixed(1)
                                        : value.toLocaleString()
                                    : String(value)}
                                </div>
                              </div>
                            );
                          },
                        )}
                      </div>
                    </div>
                  )}

                  {/* Screenshots */}
                  {psData.screenshots &&
                    Array.isArray(psData.screenshots) &&
                    psData.screenshots.length > 0 && (
                      <div className="mb-6">
                        <h3 className="text-lg font-semibold text-foreground mb-4">
                          Page Screenshots
                        </h3>
                        <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                          {psData.screenshots.map(
                            (screenshot: any, idx: number) => (
                              <div
                                key={idx}
                                className="rounded-lg border border-border overflow-hidden bg-muted/50"
                              >
                                <div className="text-[10px] text-muted-foreground p-1 text-center">
                                  {(screenshot.timestamp / 1000).toFixed(1)}s
                                </div>
                                {screenshot.data && (
                                  <div className="relative w-full h-24">
                                    <Image
                                      src={screenshot.data}
                                      alt={`Screenshot at ${screenshot.timestamp}ms`}
                                      fill
                                      className="object-cover object-top"
                                    />
                                  </div>
                                )}
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}

                  {/* Audits/Recommendations */}
                  {psData.audits && Object.keys(psData.audits).length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">
                        Improvement Recommendations
                      </h3>
                      <div className="space-y-3 max-h-[500px] overflow-y-auto">
                        {Object.entries(psData.audits).map(
                          ([key, audit]: [string, any]) => {
                            if (!audit || !audit.title) return null;

                            const isPass = audit.scoreDisplayMode === "pass";
                            const score =
                              audit.score !== null && audit.score !== undefined
                                ? audit.score
                                : null;

                            return (
                              <div
                                key={key}
                                className={`p-4 rounded-xl border ${
                                  isPass
                                    ? "bg-green-500/5 border-green-500/20"
                                    : "bg-yellow-500/5 border-yellow-500/20"
                                }`}
                              >
                                <div className="flex items-start gap-3">
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-start justify-between gap-2 mb-2">
                                      <h4 className="font-medium text-foreground">
                                        {audit.title}
                                      </h4>
                                      {score !== null && (
                                        <div
                                          className={`text-xs font-bold px-2 py-1 rounded ${
                                            isPass
                                              ? "bg-green-500/20 text-green-300"
                                              : score >= 0.75
                                                ? "bg-yellow-500/20 text-yellow-300"
                                                : "bg-red-500/20 text-red-300"
                                          }`}
                                        >
                                          {Math.round(score * 100)}
                                        </div>
                                      )}
                                    </div>
                                    {audit.description && (
                                      <p className="text-sm text-muted-foreground mb-2">
                                        {audit.description}
                                      </p>
                                    )}
                                    {audit.explanation && (
                                      <div className="text-xs text-muted-foreground bg-black/20 p-2 rounded mb-2">
                                        {audit.explanation}
                                      </div>
                                    )}
                                    {audit.details &&
                                      audit.details.type === "opportunity" && (
                                        <div className="text-xs text-muted-foreground">
                                          <div className="font-medium mb-1">
                                            Savings:{" "}
                                            {audit.details.headings?.[0]
                                              ?.valueType === "timespanMs"
                                              ? "Time"
                                              : "Bytes"}
                                          </div>
                                          {audit.details.items && (
                                            <div className="space-y-1">
                                              {audit.details.items
                                                .slice(0, 3)
                                                .map(
                                                  (item: any, idx: number) => (
                                                    <div
                                                      key={idx}
                                                      className="text-xs"
                                                    >
                                                      •{" "}
                                                      {item.url ||
                                                        item.source ||
                                                        JSON.stringify(
                                                          item,
                                                        ).substring(0, 100)}
                                                    </div>
                                                  ),
                                                )}
                                              {audit.details.items.length >
                                                3 && (
                                                <div className="text-xs">
                                                  ... and{" "}
                                                  {audit.details.items.length -
                                                    3}{" "}
                                                  more
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      )}
                                  </div>
                                </div>
                              </div>
                            );
                          },
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Tools Section - COMPLETE */}
            {audit?.status === "completed" && (
              <div className="glass-card p-8 mb-8">
                <h2 className="text-2xl font-bold text-foreground mb-6">
                  SEO & GEO Tools
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* GEO Dashboard */}
                  <Link
                    href={geoRoutes.geoDashboard}
                    {...getGeoWarmLinkProps(geoRoutes.geoDashboard)}
                    data-testid="geo-tool-card-dashboard"
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
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
                      Citation tracking, query discovery, and LLM optimization
                    </p>
                  </Link>

                  {/* Keywords Research */}
                  <Link
                    href={geoRoutes.keywords}
                    {...getGeoWarmLinkProps(geoRoutes.keywords)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-brand/10 rounded-xl">
                        <Search className="w-6 h-6 text-brand" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Keywords Research
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Discover and track relevant keywords for your niche
                    </p>
                  </Link>

                  {/* Backlinks Analysis */}
                  <Link
                    href={geoRoutes.backlinks}
                    {...getGeoWarmLinkProps(geoRoutes.backlinks)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-green-500/20 rounded-xl">
                        <LinkIcon className="w-6 h-6 text-emerald-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Backlinks
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Analyze your backlink profile and opportunities
                    </p>
                  </Link>

                  {/* Rank Tracking */}
                  <Link
                    href={geoRoutes.rankTracking}
                    {...getGeoWarmLinkProps(geoRoutes.rankTracking)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
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
                      Monitor your rankings across search engines
                    </p>
                  </Link>

                  {/* Content Editor */}
                  <Link
                    href={`${geoRoutes.contentEditor}?url=${encodeURIComponent(audit?.url || "")}`}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
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
                      AI-powered content optimization for better visibility
                    </p>
                  </Link>

                  {/* AI Content Suggestions */}
                  <Link
                    href={geoRoutes.aiContent}
                    {...getGeoWarmLinkProps(geoRoutes.aiContent)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-cyan-500/20 rounded-xl">
                        <Sparkles className="w-6 h-6 text-sky-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      AI Content Ideas
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Generate content suggestions based on your audit
                    </p>
                  </Link>

                  {/* Commerce LLM */}
                  <Link
                    href={geoRoutes.geoCommerce}
                    {...getGeoWarmLinkProps(geoRoutes.geoCommerce, "commerce")}
                    data-testid="geo-tool-card-commerce"
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-indigo-500/20 rounded-xl">
                        <ShoppingBag className="w-6 h-6 text-indigo-600" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      Ecommerce LLM
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Optimize product pages to win AI citations, qualified
                      clicks, and sales
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
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
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
                      Generate audit-driven GEO/SEO articles to outrank
                      competitors in AI answers
                    </p>
                  </Link>

                  {/* GitHub Auto-Fix */}
                  <Link
                    href={geoRoutes.githubAutoFix}
                    {...getGeoWarmLinkProps(geoRoutes.githubAutoFix)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1 block"
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
                      Create Pull Requests with AI-powered SEO/GEO fixes
                    </p>
                  </Link>

                  {/* HubSpot Auto-Apply */}
                  <Dialog>
                    <DialogTrigger asChild>
                      <button className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1">
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
                          Apply SEO/GEO recommendations directly to HubSpot CMS
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

            {/* Pages analysis */}
            <div className="glass-card p-8 mb-8">
              <h2 className="text-2xl font-bold text-foreground mb-6">
                Analyzed Pages
              </h2>
              <div className="space-y-4">
                {pages.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
                    No pages analyzed yet. Once the crawl completes, page-level
                    insights will appear here.
                  </div>
                ) : (
                  pages.map((page: any) => {
                    const issues = [] as any[];
                    if (
                      page.audit_data?.structure?.h1_check?.status !== "pass"
                    ) {
                      issues.push({
                        severity: "critical",
                        msg: "Missing or multiple H1",
                      });
                    }
                    if (
                      !page.audit_data?.schema?.schema_presence?.status ||
                      page.audit_data?.schema?.schema_presence?.status !==
                        "present"
                    ) {
                      issues.push({
                        severity: "high",
                        msg: "Missing Schema markup",
                      });
                    }
                    if (
                      page.audit_data?.eeat?.author_presence?.status !== "pass"
                    ) {
                      issues.push({
                        severity: "high",
                        msg: "Author not identified",
                      });
                    }
                    if (
                      page.audit_data?.structure?.semantic_html?.score_percent <
                      50
                    ) {
                      issues.push({
                        severity: "medium",
                        msg: "Low semantic HTML score",
                      });
                    }

                    return (
                      <div
                        key={page.id}
                        className="glass-panel p-6 rounded-2xl transition-colors"
                      >
                        <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-4">
                          <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-lg text-foreground truncate">
                              {page.url}
                            </h3>
                            <p className="text-sm text-muted-foreground truncate">
                              {page.path}
                            </p>
                          </div>
                          <div className="text-right flex-shrink-0">
                            <div className="text-3xl font-bold text-foreground">
                              {page.overall_score?.toFixed(1) || 0}
                            </div>
                            <div className="text-xs text-muted-foreground uppercase tracking-wider">
                              Score
                            </div>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground mb-1">
                              H1
                            </div>
                            <div className="font-semibold text-foreground">
                              {page.h1_score?.toFixed(0) || 0}
                            </div>
                          </div>
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground mb-1">
                              Structure
                            </div>
                            <div className="font-semibold text-foreground">
                              {page.structure_score?.toFixed(0) || 0}
                            </div>
                          </div>
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground mb-1">
                              Content
                            </div>
                            <div className="font-semibold text-foreground">
                              {page.content_score?.toFixed(0) || 0}
                            </div>
                          </div>
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground mb-1">
                              E-E-A-T
                            </div>
                            <div className="font-semibold text-foreground">
                              {page.eeat_score?.toFixed(0) || 0}
                            </div>
                          </div>
                        </div>

                        {issues.length > 0 && (
                          <div className="space-y-2">
                            {issues.map((issue, idx) => (
                              <div
                                key={idx}
                                className={`text-sm p-3 rounded-xl border flex items-center gap-2 ${
                                  issue.severity === "critical"
                                    ? "bg-red-500/10 text-red-600 border-red-500/20"
                                    : issue.severity === "high"
                                      ? "bg-orange-500/10 text-orange-600 border-orange-500/20"
                                      : "bg-amber-500/10 text-amber-600 border-amber-500/20"
                                }`}
                              >
                                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                                {issue.msg}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Competitive analysis */}
            <div className="glass-card p-8 mb-8">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-foreground">
                    Competitive Analysis
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Benchmark GEO performance against peer domains.
                  </p>
                </div>
                <span className="text-xs uppercase tracking-wide text-muted-foreground border border-border px-3 py-1 rounded-full">
                  {competitors.length} competitors
                </span>
              </div>

              {competitors.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground space-y-2">
                  <div>No competitors identified yet.</div>
                  <div>
                    We’ll surface competitors as soon as discovery queries
                    return results.
                  </div>
                  <div className="text-xs">
                    Category:{" "}
                    {audit?.external_intelligence?.category ||
                      audit?.category ||
                      "Unclassified"}
                  </div>
                </div>
              ) : (
                <>
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-foreground/80 mb-4">
                      Score Comparison
                    </h3>
                    <div className="space-y-3">
                      {comparisonSites.map((site) => (
                        <div
                          key={site.name}
                          className="flex items-center gap-4"
                        >
                          <div className="w-40 text-sm text-muted-foreground truncate">
                            {site.name}
                          </div>
                          <div className="flex-1 h-2 bg-muted/40 rounded-full overflow-hidden">
                            <div
                              className="h-2 rounded-full"
                              style={{
                                width: `${Math.min(site.score, 100)}%`,
                                backgroundColor: site.color,
                              }}
                            />
                          </div>
                          <div className="w-14 text-sm font-semibold text-foreground text-right">
                            {site.score.toFixed(1)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <h3 className="text-lg font-semibold text-foreground/80 mb-4">
                      Detailed Benchmark
                    </h3>
                    <table className="w-full text-sm text-left">
                      <thead>
                        <tr className="border-b border-border text-muted-foreground">
                          <th className="p-4 font-medium">Website</th>
                          <th className="text-center p-4 font-medium">
                            GEO Score (%)
                          </th>
                          <th className="text-center p-4 font-medium">
                            Schema
                          </th>
                          <th className="text-center p-4 font-medium">
                            Semantic HTML
                          </th>
                          <th className="text-center p-4 font-medium">
                            E-E-A-T
                          </th>
                          <th className="text-center p-4 font-medium">H1</th>
                          <th className="text-center p-4 font-medium">Tone</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        <tr className="bg-muted/30">
                          <td className="p-4 font-semibold text-foreground">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 bg-brand rounded-full" />
                              Your Site
                            </div>
                          </td>
                          <td className="text-center p-4 font-bold text-brand">
                            {audit.geo_score !== undefined &&
                            audit.geo_score !== null
                              ? `${audit.geo_score.toFixed(1)}%`
                              : `${comparisonSites[0]?.score?.toFixed(1) ?? "0.0"}%`}
                          </td>
                          <td className="text-center p-4 text-foreground/70">
                            {audit.target_audit?.schema?.schema_presence
                              ?.status === "present"
                              ? "✓"
                              : "✗"}
                          </td>
                          <td className="text-center p-4 text-foreground/70">
                            {typeof audit.target_audit?.structure?.semantic_html
                              ?.score_percent === "number"
                              ? `${audit.target_audit?.structure?.semantic_html?.score_percent.toFixed(0)}%`
                              : "N/A"}
                          </td>
                          <td className="text-center p-4 text-foreground/70">
                            {audit.target_audit?.eeat?.author_presence
                              ?.status === "pass"
                              ? "✓"
                              : "✗"}
                          </td>
                          <td className="text-center p-4 text-foreground/70">
                            {audit.target_audit?.structure?.h1_check?.status ===
                            "pass"
                              ? "✓"
                              : "✗"}
                          </td>
                          <td className="text-center p-4 text-foreground/70">
                            {typeof audit.target_audit?.content
                              ?.conversational_tone?.score === "number"
                              ? audit.target_audit?.content?.conversational_tone?.score.toFixed(
                                  1,
                                )
                              : "0.0"}
                            /10
                          </td>
                        </tr>
                        {competitors.map((comp: any, idx: number) => {
                          const domain =
                            safeHostname(comp.url) ||
                            comp.domain ||
                            "Competitor";
                          const toneScore =
                            typeof comp.tone_score === "number"
                              ? comp.tone_score
                              : 0;
                          return (
                            <tr
                              key={idx}
                              className="hover:bg-muted/20 transition-colors"
                            >
                              <td className="p-4 text-muted-foreground">
                                <div className="flex items-center gap-2">
                                  <span className="w-2 h-2 bg-slate-400 rounded-full" />
                                  <a
                                    href={comp.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="hover:text-foreground hover:underline"
                                  >
                                    {domain}
                                  </a>
                                </div>
                              </td>
                              <td className="text-center p-4 font-bold text-foreground/90">
                                {comp.geo_score !== undefined &&
                                comp.geo_score !== null
                                  ? `${comp.geo_score.toFixed(1)}%`
                                  : "0.0%"}
                              </td>
                              <td className="text-center p-4 text-muted-foreground">
                                {comp.schema_present ? "✓" : "✗"}
                              </td>
                              <td className="text-center p-4 text-muted-foreground">
                                {typeof comp.structure_score === "number"
                                  ? `${comp.structure_score.toFixed(0)}%`
                                  : "N/A"}
                              </td>
                              <td className="text-center p-4 text-muted-foreground">
                                {typeof comp.eeat_score === "number"
                                  ? comp.eeat_score.toFixed(0)
                                  : "N/A"}
                              </td>
                              <td className="text-center p-4 text-muted-foreground">
                                {comp.h1_present ? "✓" : "✗"}
                              </td>
                              <td className="text-center p-4 text-muted-foreground">
                                {toneScore.toFixed(1)}/10
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </TabsContent>

          <TabsContent value="report">
            <div className="glass-card p-8">
              <div className="flex items-center justify-between gap-4 mb-6">
                <h2 className="text-2xl font-bold text-foreground flex items-center gap-3">
                  <FileText className="w-6 h-6 text-brand" />
                  Report (Markdown)
                </h2>
                <Button
                  variant="outline"
                  onClick={() => {
                    setReportMarkdown(null);
                    loadReport();
                  }}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Reload
                </Button>
              </div>

              {reportLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Loading report...
                </div>
              ) : reportMarkdown ? (
                <pre className="whitespace-pre-wrap break-words text-sm bg-muted/40 border border-border rounded-xl p-4 overflow-auto max-h-[70vh]">
                  {reportMarkdown}
                </pre>
              ) : (
                <div className="text-muted-foreground">
                  {reportMessage ||
                    "Report not generated. Click Generate PDF to build it."}
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="fix-plan">
            <div className="glass-card p-8">
              <div className="flex items-center justify-between gap-4 mb-6">
                <h2 className="text-2xl font-bold text-foreground flex items-center gap-3">
                  <Target className="w-6 h-6 text-brand" />
                  Fix Plan
                </h2>
                <Button
                  variant="outline"
                  onClick={() => {
                    setFixPlan(null);
                    loadFixPlan();
                  }}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Reload
                </Button>
              </div>

              {fixPlanLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Loading fix plan...
                </div>
              ) : fixPlan && fixPlan.length > 0 ? (
                <div className="space-y-3">
                  {fixPlan.map((item: any, idx: number) => (
                    <div
                      key={idx}
                      className="bg-muted/40 border border-border rounded-xl p-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-foreground">
                            {item?.title || item?.issue || `Fix #${idx + 1}`}
                          </div>
                          {item?.description && (
                            <div className="text-sm text-muted-foreground mt-1 whitespace-pre-wrap break-words">
                              {item.description}
                            </div>
                          )}
                        </div>
                        {item?.priority && (
                          <span className="text-xs px-2 py-1 rounded-full border border-border text-muted-foreground capitalize">
                            {item.priority}
                          </span>
                        )}
                      </div>
                      {(item?.files ||
                        item?.recommendations ||
                        item?.steps) && (
                        <pre className="mt-3 text-xs bg-muted/30 border border-border rounded-lg p-3 overflow-auto">
                          {JSON.stringify(
                            {
                              files: item.files,
                              recommendations: item.recommendations,
                              steps: item.steps,
                            },
                            null,
                            2,
                          )}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-muted-foreground">
                  {fixPlanMessage ||
                    "Fix plan will be created when you generate the PDF report."}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
