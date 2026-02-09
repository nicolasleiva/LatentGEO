'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';

import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import logger from '@/lib/logger';
import { Header } from '@/components/header';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, Download, RefreshCw, ExternalLink, Globe, AlertTriangle, CheckCircle, Clock, FileText, Target, Search, Link as LinkIcon, TrendingUp, Edit, Sparkles, Github, GitPullRequest } from 'lucide-react';
import { Dialog, DialogContent, DialogTrigger, DialogTitle } from '@/components/ui/dialog';
import { useAuditSSE } from '@/hooks/useAuditSSE';
import { API_URL } from '@/lib/api';

// Dynamic imports for heavy components
const CoreWebVitalsChart = dynamic(() => import('@/components/core-web-vitals-chart').then(mod => mod.CoreWebVitalsChart), { ssr: false });
const KeywordGapChart = dynamic(() => import('@/components/keyword-gap-chart').then(mod => mod.KeywordGapChart), { ssr: false });
const IssuesHeatmap = dynamic(() => import('@/components/issues-heatmap').then(mod => mod.IssuesHeatmap), { ssr: false });
const GitHubIntegration = dynamic(() => import('@/components/github-integration').then(mod => mod.GitHubIntegration), { ssr: false });
const HubSpotIntegration = dynamic(() => import('@/components/hubspot-integration').then(mod => mod.HubSpotIntegration), { ssr: false });
const AuditChatFlow = dynamic(() => import('@/components/audit-chat-flow').then(mod => mod.AuditChatFlow), { ssr: false });
const AIProcessingScreen = dynamic(() => import('@/components/ai-processing-screen').then(mod => mod.AIProcessingScreen), { ssr: false });


export default function AuditDetailPage() {
  const params = useParams();
  const router = useRouter();
  const auditId = params.id as string;

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
  const [activeTab, setActiveTab] = useState<'overview' | 'report' | 'fix-plan'>('overview');
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [fixPlan, setFixPlan] = useState<any[] | null>(null);
  const [fixPlanLoading, setFixPlanLoading] = useState(false);

  const loadReport = useCallback(async () => {
    if (reportLoading || reportMarkdown) return;
    setReportLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/reports/markdown/${auditId}`);
      if (res.ok) {
        const data = await res.json();
        setReportMarkdown(data?.markdown || '');
        return;
      }

      const fallbackRes = await fetch(`${backendUrl}/api/audits/${auditId}/report`);
      if (fallbackRes.ok) {
        const data = await fallbackRes.json();
        setReportMarkdown(data?.report || data?.markdown || '');
        return;
      }

      setReportMarkdown('');
    } catch (err) {
      console.error(err);
      setReportMarkdown('');
    } finally {
      setReportLoading(false);
    }
  }, [auditId, backendUrl, reportLoading, reportMarkdown]);

  const loadFixPlan = useCallback(async () => {
    if (fixPlanLoading || fixPlan) return;
    setFixPlanLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/audits/${auditId}/fix_plan`);
      if (!res.ok) {
        setFixPlan([]);
        return;
      }
      const data = await res.json();
      setFixPlan(Array.isArray(data?.fix_plan) ? data.fix_plan : Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setFixPlan([]);
    } finally {
      setFixPlanLoading(false);
    }
  }, [auditId, backendUrl, fixPlanLoading, fixPlan]);

  const fetchData = useCallback(async () => {
    try {
      // Fetch audit first
      const auditRes = await fetch(`${backendUrl}/api/audits/${auditId}`);
      if (!auditRes.ok) {
        if (auditRes.status === 429) {
          logger.log('Rate limited, retrying in 2s...');
          await new Promise(resolve => setTimeout(resolve, 2000));
          return fetchData();
        }
        throw new Error(`Failed to fetch audit: ${auditRes.status}`);
      }
      const auditData = await auditRes.json();
      setAudit(auditData);

      // Stop loading immediately so Chat appears ASAP
      setLoading(false);

      // Fetch pages and competitors in parallel (non-blocking for initial render)
      const [pagesRes, compRes] = await Promise.all([
        fetch(`${backendUrl}/api/audits/${auditId}/pages`),
        auditData.status === 'completed'
          ? fetch(`${backendUrl}/api/audits/${auditId}/competitors`).catch(() => null)
          : Promise.resolve(null)
      ]);

      if (pagesRes.ok) {
        const pagesData = await pagesRes.json();
        setPages(pagesData);
      }

      if (compRes?.ok) {
        const compData = await compRes.json();
        setCompetitors(compData);
      }

      // Initialize PageSpeed data if available in audit
      if (auditData.pagespeed_data) {
        setPageSpeedData(auditData.pagespeed_data);
      }
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  }, [auditId, backendUrl]);

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Limpiar PageSpeed cuando status cambia a 'running'
  useEffect(() => {
    if (audit?.status === 'processing') {
      setPageSpeedData(null);
    }
  }, [audit?.status]);

  // SSE for real-time status updates (replaces polling)
  useAuditSSE(auditId, {
    onMessage: (statusData) => {
      setAudit((prev: any) => ({
        ...prev,
        ...statusData
      }));
    },
    onComplete: (statusData) => {
      fetchData();
    },
    onError: (error) => {
      console.error('SSE error:', error);
    }
  });

  // Memoized helper functions - MUST be before any conditional returns
  const getStatusColor = useMemo(() => (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/20 text-green-300 border-green-500/30';
      case 'failed':
        return 'bg-red-500/20 text-red-300 border-red-500/30';
      default:
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    }
  }, []);

  const getScoreColor = useMemo(() => (score: number) => {
    if (score >= 90) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  }, []);

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
      logger.log('Analyzing PageSpeed...');
      const res = await fetch(`${backendUrl}/api/audits/${auditId}/pagespeed`, {
        method: 'POST',
      });
      logger.log('PageSpeed response:', res.status);
      if (res.ok) {
        const data = await res.json();
        logger.log('PageSpeed data:', data);
        // Use data.data if it exists (new backend response structure)
        setPageSpeedData(data.data || data);
        alert('✅ PageSpeed analysis completed!');
      } else {
        const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('PageSpeed error:', error);
        alert(`❌ Error: ${error.detail || 'Failed to analyze PageSpeed'}`);
      }
    } catch (err) {
      console.error('PageSpeed exception:', err);
      alert(`❌ Error: ${err instanceof Error ? err.message : 'Failed to analyze PageSpeed'}`);
    } finally {
      setPageSpeedLoading(false);
    }
  };

  const generatePDF = async () => {
    setPdfGenerating(true);
    try {
      const generateRes = await fetch(`${backendUrl}/api/audits/${auditId}/generate-pdf`, {
        method: 'POST',
      });
      if (generateRes.ok) {
        await new Promise(resolve => setTimeout(resolve, 500));
        window.open(`${backendUrl}/api/audits/${auditId}/download-pdf`, '_blank');
      } else {
        const error = await generateRes.json();
        alert(`Error: ${error.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error(err);
      alert('Error generating PDF');
    } finally {
      setPdfGenerating(false);
    }
  };

  // Show AI Processing Screen when audit is processing
  if (audit?.status === 'processing') {
    return <AIProcessingScreen isProcessing={true} />;
  }

  return (
    <div className="flex min-h-screen flex-col pb-20">
      <Header />

      <main className="flex-1 container mx-auto px-6 py-8">
        {/* Back button */}
        <Button variant="ghost" onClick={() => router.push('/audits')} className="mb-8 text-muted-foreground hover:text-foreground pl-0">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Audits
        </Button>

        {/* Header card */}
        <div className="glass-card p-8 mb-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Globe className="w-64 h-64 text-foreground" />
          </div>

          <div className="flex flex-col md:flex-row justify-between items-start relative z-10 gap-6">
            <div>
              <div className="flex items-center gap-4 mb-2">
                <h1 className="text-4xl font-bold text-foreground">
                  {audit?.domain
                    ? audit.domain
                    : audit?.url
                      ? new URL(audit.url).hostname.replace('www.', '')
                      : '---'}
                </h1>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-medium border ${audit ? getStatusColor(audit.status) : ''
                    }`}
                >
                  {audit?.status ?? ''}
                </span>
              </div>
              <p className="text-lg text-muted-foreground mb-6 flex items-center gap-2">
                <Globe className="w-4 h-4" />
                {audit?.url ?? ''}
              </p>
            </div>

            {audit?.status === 'completed' && (
              <div className="flex gap-3">
                {audit.source === 'hubspot' && (
                  <Button
                    onClick={() => router.push(`/audits/${auditId}/hubspot-apply`)}
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
                  {pdfGenerating ? 'Generating PDF...' : 'PDF Report'}
                </Button>
                <Button
                  onClick={() => router.push(`/audits/${auditId}/geo`)}
                  className="glass-button-primary px-6"
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open GEO Dashboard
                </Button>
              </div>
            )}
          </div>

        </div>

        {/* Chat Flow for Configuration (if audit is pending) */}
        {audit?.status === 'pending' && audit?.progress === 0 && !hasChatCompleted && (
          <div className="mb-8">
            <AuditChatFlow
              auditId={parseInt(auditId)}
              onComplete={() => {
                setHasChatCompleted(true); // Prevent chat from reappearing
                // Optimistically update status to hide chat and show progress immediately
                setAudit((prev: any) => ({
                  ...prev,
                  status: 'processing',
                  progress: 1
                }));
                // Refresh audit data after configuration
                fetchData();
              }}
            />
          </div>
        )}

        <Tabs
          defaultValue="overview"
          value={activeTab}
          onValueChange={(v) => {
            const nextTab = (v as 'overview' | 'report' | 'fix-plan');
            setActiveTab(nextTab);
            if (nextTab === 'report') loadReport();
            if (nextTab === 'fix-plan') loadFixPlan();
          }}
        >
          <TabsList className="mb-8">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="report">Report</TabsTrigger>
            <TabsTrigger value="fix-plan">Fix Plan</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            {/* Stats cards */}
            {audit?.status === 'completed' && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-muted-foreground">
                    <FileText className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">Pages</span>
                  </div>
                  <div className="text-3xl font-bold text-foreground">{audit.total_pages}</div>
                </div>
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-red-400/70">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">Critical</span>
                  </div>
                  <div className="text-3xl font-bold text-red-400">{audit.critical_issues}</div>
                </div>
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-orange-400/70">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">High</span>
                  </div>
                  <div className="text-3xl font-bold text-orange-400">{audit.high_issues}</div>
                </div>
                <div className="glass-card p-6">
                  <div className="flex items-center gap-3 mb-2 text-yellow-400/70">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-medium uppercase tracking-wider">Medium</span>
                  </div>
                  <div className="text-3xl font-bold text-yellow-400">{audit.medium_issues}</div>
                </div>
              </div>
            )}

            {(() => {
              const rawData = pageSpeedData?.data || pageSpeedData;
              const psData = rawData?.mobile || (rawData?.performance_score !== undefined ? rawData : null);

              if (!psData) return null;

              return (
                <div className="glass-card p-8 mb-8">
                  <h2 className="text-2xl font-bold text-foreground mb-6 flex items-center gap-3">
                    <Clock className="w-6 h-6 text-blue-400" />
                    PageSpeed Insights
                  </h2>

                  {/* Category Scores */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">Performance</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.performance_score || 0)}`}>
                        {Math.round(psData.performance_score || 0)}
                      </div>
                    </div>
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">Accessibility</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.accessibility_score || 0)}`}>
                        {Math.round(psData.accessibility_score || 0)}
                      </div>
                    </div>
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">Best Practices</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.best_practices_score || 0)}`}>
                        {Math.round(psData.best_practices_score || 0)}
                      </div>
                    </div>
                    <div className="bg-muted/50 p-4 rounded-xl border border-border text-center">
                      <div className="text-xs text-muted-foreground mb-2">SEO</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.seo_score || 0)}`}>
                        {Math.round(psData.seo_score || 0)}
                      </div>
                    </div>
                  </div>

                  {/* Core Web Vitals */}
                  {psData.core_web_vitals && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">Core Web Vitals</h3>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">LCP</div>
                          <div className="text-xl font-bold text-foreground">
                            {(psData.core_web_vitals.lcp / 1000).toFixed(2)}s
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">FID</div>
                          <div className="text-xl font-bold text-foreground">
                            {Math.round(psData.core_web_vitals.fid)}ms
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">CLS</div>
                          <div className="text-xl font-bold text-foreground">
                            {psData.core_web_vitals.cls.toFixed(3)}
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">FCP</div>
                          <div className="text-xl font-bold text-foreground">
                            {(psData.core_web_vitals.fcp / 1000).toFixed(2)}s
                          </div>
                        </div>
                        <div className="bg-muted/50 p-4 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">TTFB</div>
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
                  {psData.opportunities && Object.keys(psData.opportunities).length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">Optimization Opportunities</h3>
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {Object.entries(psData.opportunities).map(([key, data]: [string, any]) => (
                          data && data.score !== null && data.score < 0.9 && (
                            <div key={key} className="bg-muted/50 p-3 rounded-xl border border-border flex items-start gap-3">
                              <AlertTriangle className={`w-4 h-4 mt-1 flex-shrink-0 ${data.score < 0.5 ? 'text-red-400' : 'text-yellow-400'}`} />
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-foreground">{data.title || key.replace(/-/g, ' ')}</div>
                                {data.displayValue && (
                                  <div className="text-xs text-muted-foreground mt-1">{data.displayValue}</div>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Score: {Math.round((data.score || 0) * 100)}
                              </div>
                            </div>
                          )
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Diagnostics */}
                  {psData.diagnostics && Object.keys(psData.diagnostics).length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">Diagnostics</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto">
                        {Object.entries(psData.diagnostics).map(([key, metric]: [string, any]) => (
                          metric && metric.displayValue && (
                            <div key={key} className="bg-muted/50 p-3 rounded-xl border border-border">
                              <div className="text-xs text-muted-foreground">{metric.title || key.replace(/_/g, ' ')}</div>
                              <div className="text-sm text-foreground font-medium">{metric.displayValue}</div>
                              {metric.description && (
                                <div className="text-xs text-muted-foreground mt-1">{metric.description}</div>
                              )}
                            </div>
                          )
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata */}
                  {psData.metadata && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">Audit Information</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {psData.metadata.fetch_time && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">Fetch Time</div>
                            <div className="text-sm text-foreground">{new Date(psData.metadata.fetch_time).toLocaleString()}</div>
                          </div>
                        )}
                        {psData.metadata.user_agent && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">User Agent</div>
                            <div className="text-xs text-foreground truncate">{psData.metadata.user_agent}</div>
                          </div>
                        )}
                        {psData.metadata.benchmark_index && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">Benchmark Index</div>
                            <div className="text-sm text-foreground">{psData.metadata.benchmark_index}</div>
                          </div>
                        )}
                        {psData.metadata.network_throttling && (
                          <div className="bg-muted/50 p-3 rounded-xl border border-border">
                            <div className="text-xs text-muted-foreground">Network Setting</div>
                            <div className="text-xs text-foreground truncate">{psData.metadata.network_throttling}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Metrics Detail */}
                  {psData.metrics && Object.keys(psData.metrics).length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">Detailed Metrics</h3>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-96 overflow-y-auto">
                        {Object.entries(psData.metrics).map(([key, value]: [string, any]) => {
                          if (value === null || value === undefined) return null;
                          return (
                            <div key={key} className="bg-muted/50 p-3 rounded-xl border border-border">
                              <div className="text-xs text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</div>
                              <div className="text-sm font-medium text-foreground">
                                {typeof value === 'number' ? (
                                  key.includes('time') || key.includes('duration') || key.includes('ms')
                                    ? `${Math.round(value)}ms`
                                    : key.includes('score')
                                      ? value.toFixed(1)
                                      : value.toLocaleString()
                                ) : (
                                  String(value)
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Screenshots */}
                  {psData.screenshots && Array.isArray(psData.screenshots) && psData.screenshots.length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">Page Screenshots</h3>
                      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                        {psData.screenshots.map((screenshot: any, idx: number) => (
                          <div key={idx} className="rounded-lg border border-border overflow-hidden bg-muted/50">
                            <div className="text-[10px] text-muted-foreground p-1 text-center">{(screenshot.timestamp / 1000).toFixed(1)}s</div>
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
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Audits/Recommendations */}
                  {psData.audits && Object.keys(psData.audits).length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-foreground mb-4">Improvement Recommendations</h3>
                      <div className="space-y-3 max-h-[500px] overflow-y-auto">
                        {Object.entries(psData.audits).map(([key, audit]: [string, any]) => {
                          if (!audit || !audit.title) return null;

                          const isPass = audit.scoreDisplayMode === 'pass';
                          const score = audit.score !== null && audit.score !== undefined ? audit.score : null;

                          return (
                            <div
                              key={key}
                              className={`p-4 rounded-xl border ${isPass
                                ? 'bg-green-500/5 border-green-500/20'
                                : 'bg-yellow-500/5 border-yellow-500/20'
                                }`}
                            >
                              <div className="flex items-start gap-3">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-start justify-between gap-2 mb-2">
                                    <h4 className="font-medium text-foreground">{audit.title}</h4>
                                    {score !== null && (
                                      <div className={`text-xs font-bold px-2 py-1 rounded ${isPass
                                        ? 'bg-green-500/20 text-green-300'
                                        : score >= 0.75 ? 'bg-yellow-500/20 text-yellow-300' : 'bg-red-500/20 text-red-300'
                                        }`}>
                                        {Math.round(score * 100)}
                                      </div>
                                    )}
                                  </div>
                                  {audit.description && (
                                    <p className="text-sm text-muted-foreground mb-2">{audit.description}</p>
                                  )}
                                  {audit.explanation && (
                                    <div className="text-xs text-muted-foreground bg-black/20 p-2 rounded mb-2">
                                      {audit.explanation}
                                    </div>
                                  )}
                                  {audit.details && audit.details.type === 'opportunity' && (
                                    <div className="text-xs text-muted-foreground">
                                      <div className="font-medium mb-1">Savings: {audit.details.headings?.[0]?.valueType === 'timespanMs' ? 'Time' : 'Bytes'}</div>
                                      {audit.details.items && (
                                        <div className="space-y-1">
                                          {audit.details.items.slice(0, 3).map((item: any, idx: number) => (
                                            <div key={idx} className="text-xs">
                                              • {item.url || item.source || JSON.stringify(item).substring(0, 100)}
                                            </div>
                                          ))}
                                          {audit.details.items.length > 3 && (
                                            <div className="text-xs">... and {audit.details.items.length - 3} more</div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Tools Section - COMPLETE */}
            {audit?.status === 'completed' && (
              <div className="glass-card p-8 mb-8">
                <h2 className="text-2xl font-bold text-foreground mb-6">SEO & GEO Tools</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* GEO Dashboard */}
                  <button
                    onClick={() => router.push(`/audits/${auditId}/geo`)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-purple-500/20 rounded-xl">
                        <Target className="w-6 h-6 text-purple-400" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">GEO Dashboard</h3>
                    <p className="text-sm text-muted-foreground">
                      Citation tracking, query discovery, and LLM optimization
                    </p>
                  </button>

                  {/* Keywords Research */}
                  <button
                    onClick={() => router.push(`/audits/${auditId}/keywords`)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-blue-500/20 rounded-xl">
                        <Search className="w-6 h-6 text-blue-400" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Keywords Research</h3>
                    <p className="text-sm text-muted-foreground">
                      Discover and track relevant keywords for your niche
                    </p>
                  </button>

                  {/* Backlinks Analysis */}
                  <button
                    onClick={() => router.push(`/audits/${auditId}/backlinks`)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-green-500/20 rounded-xl">
                        <LinkIcon className="w-6 h-6 text-green-400" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Backlinks</h3>
                    <p className="text-sm text-muted-foreground">
                      Analyze your backlink profile and opportunities
                    </p>
                  </button>

                  {/* Rank Tracking */}
                  <button
                    onClick={() => router.push(`/audits/${auditId}/rank-tracking`)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-orange-500/20 rounded-xl">
                        <TrendingUp className="w-6 h-6 text-orange-400" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Rank Tracking</h3>
                    <p className="text-sm text-muted-foreground">
                      Monitor your rankings across search engines
                    </p>
                  </button>

                  {/* Content Editor */}
                  <button
                    onClick={() => router.push(`/tools/content-editor?url=${encodeURIComponent(audit?.url || '')}`)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-pink-500/20 rounded-xl">
                        <Edit className="w-6 h-6 text-pink-400" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">Content Editor</h3>
                    <p className="text-sm text-muted-foreground">
                      AI-powered content optimization for better visibility
                    </p>
                  </button>

                  {/* AI Content Suggestions */}
                  <button
                    onClick={() => router.push(`/audits/${auditId}/ai-content`)}
                    className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 bg-cyan-500/20 rounded-xl">
                        <Sparkles className="w-6 h-6 text-cyan-400" />
                      </div>
                      <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">AI Content Ideas</h3>
                    <p className="text-sm text-muted-foreground">
                      Generate content suggestions based on your audit
                    </p>
                  </button>

                  {/* GitHub Auto-Fix */}
                  <Dialog>
                    <DialogTrigger asChild>
                      <button className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1">
                        <div className="flex items-start justify-between mb-3">
                          <div className="p-3 bg-purple-500/20 rounded-xl">
                            <GitPullRequest className="w-6 h-6 text-purple-400" />
                          </div>
                          <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                        </div>
                        <h3 className="text-lg font-semibold text-foreground mb-2">GitHub Auto-Fix</h3>
                        <p className="text-sm text-muted-foreground">
                          Create Pull Requests with AI-powered SEO/GEO fixes
                        </p>
                      </button>
                    </DialogTrigger>
                    <DialogContent className="glass-card border-border sm:max-w-2xl">
                      <DialogTitle className="text-xl font-bold text-foreground">GitHub Auto-Fix Integration</DialogTitle>
                      <GitHubIntegration auditId={auditId} auditUrl={audit?.url || ''} />
                    </DialogContent>
                  </Dialog>

                  {/* HubSpot Auto-Apply */}
                  <Dialog>
                    <DialogTrigger asChild>
                      <button className="group glass-panel p-6 rounded-2xl transition-all text-left hover:-translate-y-1">
                        <div className="flex items-start justify-between mb-3">
                          <div className="p-3 bg-orange-500/20 rounded-xl">
                            <Sparkles className="w-6 h-6 text-orange-400" />
                          </div>
                          <ExternalLink className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                        </div>
                        <h3 className="text-lg font-semibold text-foreground mb-2">HubSpot Auto-Apply</h3>
                        <p className="text-sm text-muted-foreground">
                          Apply SEO/GEO recommendations directly to HubSpot CMS
                        </p>
                      </button>
                    </DialogTrigger>
                    <DialogContent className="glass-card border-border sm:max-w-2xl">
                      <DialogTitle className="text-xl font-bold text-foreground">HubSpot Auto-Apply Integration</DialogTitle>
                      <HubSpotIntegration auditId={auditId} auditUrl={audit?.url || ''} />
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            )}

            {/* Pages analysis */}
            <div className="glass-card p-8 mb-8">
              <h2 className="text-2xl font-bold text-foreground mb-6">Analyzed Pages</h2>
              <div className="space-y-4">
                {pages.map((page: any) => {
                  const issues = [] as any[];
                  if (page.audit_data?.structure?.h1_check?.status !== 'pass') {
                    issues.push({ severity: 'critical', msg: 'Missing or multiple H1' });
                  }
                  if (!page.audit_data?.schema?.schema_presence?.status || page.audit_data?.schema?.schema_presence?.status !== 'present') {
                    issues.push({ severity: 'high', msg: 'Missing Schema markup' });
                  }
                  if (page.audit_data?.eeat?.author_presence?.status !== 'pass') {
                    issues.push({ severity: 'high', msg: 'Author not identified' });
                  }
                  if (page.audit_data?.structure?.semantic_html?.score_percent < 50) {
                    issues.push({ severity: 'medium', msg: 'Low semantic HTML score' });
                  }

                  return (
                    <div key={page.id} className="glass-panel p-6 rounded-2xl transition-colors">
                      <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-4">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-lg text-foreground truncate">{page.url}</h3>
                          <p className="text-sm text-muted-foreground truncate">{page.path}</p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <div className="text-3xl font-bold text-foreground">{page.overall_score?.toFixed(1) || 0}</div>
                          <div className="text-xs text-muted-foreground uppercase tracking-wider">Score</div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div className="bg-muted/50 p-3 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">H1</div>
                          <div className="font-semibold text-foreground">{page.h1_score?.toFixed(0) || 0}</div>
                        </div>
                        <div className="bg-muted/50 p-3 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">Structure</div>
                          <div className="font-semibold text-foreground">{page.structure_score?.toFixed(0) || 0}</div>
                        </div>
                        <div className="bg-muted/50 p-3 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">Content</div>
                          <div className="font-semibold text-foreground">{page.content_score?.toFixed(0) || 0}</div>
                        </div>
                        <div className="bg-muted/50 p-3 rounded-xl border border-border">
                          <div className="text-xs text-muted-foreground mb-1">E-E-A-T</div>
                          <div className="font-semibold text-foreground">{page.eeat_score?.toFixed(0) || 0}</div>
                        </div>
                      </div>

                      {issues.length > 0 && (
                        <div className="space-y-2">
                          {issues.map((issue, idx) => (
                            <div
                              key={idx}
                              className={`text-sm p-3 rounded-xl border flex items-center gap-2 ${issue.severity === 'critical'
                                ? 'bg-red-500/10 text-red-200 border-red-500/20'
                                : issue.severity === 'high'
                                  ? 'bg-orange-500/10 text-orange-200 border-orange-500/20'
                                  : 'bg-yellow-500/10 text-yellow-200 border-yellow-500/20'
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
                })}
              </div>
            </div>

            {/* Competitive analysis */}
            {competitors.length > 0 && (
              <div className="glass-card p-8 mb-8">
                <h2 className="text-2xl font-bold text-foreground mb-6">Competitive Analysis</h2>
                {/* Comparison chart (same SVG as before but styled for dark mode) */}
                <div className="mb-8 overflow-x-auto">
                  <h3 className="text-lg font-semibold text-foreground/80 mb-4">GEO/SEO Score Comparison</h3>
                  <div className="relative h-80 bg-muted/50 border border-border rounded-2xl p-6 min-w-[600px]">
                    <svg className="w-full h-full" viewBox="0 0 800 300">
                      {[0, 20, 40, 60, 80, 100].map((val) => (
                        <g key={val}>
                          <line x1="60" y1={280 - val * 2.5} x2="780" y2={280 - val * 2.5} stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                          <text x="40" y={285 - val * 2.5} fontSize="12" fill="rgba(255,255,255,0.4)">
                            {val}
                          </text>
                        </g>
                      ))}
                      {(() => {
                        const allSites = [
                          {
                            name: 'Your Site',
                            score:
                              audit.geo_score !== undefined && audit.geo_score !== null
                                ? audit.geo_score
                                : (audit.total_pages > 0
                                  ? 100 - (audit.critical_issues * 2 + audit.high_issues) * 10 / Math.max(1, audit.total_pages)
                                  : 50),
                            color: '#a855f7', // Purple
                          },
                          ...competitors.slice(0, 5).map((comp: any) => {
                            const domain = comp.domain || new URL(comp.url).hostname.replace('www.', '');
                            const geoScore = comp.geo_score || 50;
                            return { name: domain, score: geoScore, color: '#94a3b8' }; // Slate 400
                          }),
                        ];
                        const spacing = 720 / (allSites.length - 1);
                        return (
                          <>
                            {allSites.map((site, idx) => {
                              if (idx === allSites.length - 1) return null;
                              const x1 = 60 + idx * spacing;
                              const y1 = 280 - site.score * 2.5;
                              const x2 = 60 + (idx + 1) * spacing;
                              const y2 = 280 - allSites[idx + 1].score * 2.5;
                              return (
                                <line
                                  key={`line-${idx}`}
                                  x1={x1}
                                  y1={y1}
                                  x2={x2}
                                  y2={y2}
                                  stroke={site.color}
                                  strokeWidth="2"
                                  strokeOpacity="0.5"
                                />
                              );
                            })}
                            {allSites.map((site, idx) => {
                              const x = 60 + idx * spacing;
                              const y = 280 - site.score * 2.5;
                              return (
                                <g key={`point-${idx}`}>
                                  <circle cx={x} cy={y} r="6" fill={site.color} />
                                  <circle cx={x} cy={y} r="3" fill="#000" />
                                  <text
                                    x={x}
                                    y="295"
                                    fontSize="11"
                                    fill="rgba(255,255,255,0.7)"
                                    textAnchor="middle"
                                    transform={`rotate(-45, ${x}, 295)`}
                                  >
                                    {site.name.length > 15 ? site.name.substring(0, 15) + '...' : site.name}
                                  </text>
                                  <text x={x} y={y - 12} fontSize="12" fontWeight="bold" fill={site.color} textAnchor="middle">
                                    {site.score.toFixed(1)}
                                  </text>
                                </g>
                              );
                            })}
                          </>
                        );
                      })()}
                    </svg>
                  </div>
                </div>
                {/* Detailed comparison table */}
                <div className="overflow-x-auto">
                  <h3 className="text-lg font-semibold text-foreground/80 mb-4">Detailed Benchmark</h3>
                  <table className="w-full text-sm text-left">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th className="p-4 font-medium">Website</th>
                        <th className="text-center p-4 font-medium">GEO Score (%)</th>
                        <th className="text-center p-4 font-medium">Schema</th>
                        <th className="text-center p-4 font-medium">Semantic HTML</th>
                        <th className="text-center p-4 font-medium">E-E-A-T</th>
                        <th className="text-center p-4 font-medium">H1</th>
                        <th className="text-center p-4 font-medium">Tone</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {/* Your site row */}
                      <tr className="bg-muted/30">
                        <td className="p-4 font-semibold text-foreground">
                          <div className="flex items-center gap-2">
                            <span className="w-2 h-2 bg-purple-500 rounded-full shadow-[0_0_10px_rgba(168,85,247,0.5)]" />
                            Your Site
                          </div>
                        </td>
                        <td className="text-center p-4 font-bold text-purple-400">
                          {(() => {
                              if (audit.geo_score !== undefined && audit.geo_score !== null) {
                                return `${audit.geo_score.toFixed(1)}%`;
                              }
                              const comp = audit.comparative_analysis;
                              if (comp?.scores?.[0]) {
                                return `${comp.scores[0].scores.total.toFixed(1)}%`;
                              }
                              return `${(100 - (audit.critical_issues * 2 + audit.high_issues) * 10 / Math.max(1, audit.total_pages)).toFixed(1)}%`;
                            })()}
                          </td>
                        <td className="text-center p-4 text-foreground/70">{audit.target_audit?.schema?.schema_presence?.status === 'present' ? '✓' : '✗'}</td>
                        <td className="text-center p-4 text-foreground/70">{audit.target_audit?.structure?.semantic_html?.score_percent?.toFixed(0) || 'N/A'}%</td>
                        <td className="text-center p-4 text-foreground/70">{audit.target_audit?.eeat?.author_presence?.status === 'pass' ? '✓' : '✗'}</td>
                        <td className="text-center p-4 text-foreground/70">{audit.target_audit?.structure?.h1_check?.status === 'pass' ? '✓' : '✗'}</td>
                        <td className="text-center p-4 text-foreground/70">{audit.target_audit?.content?.conversational_tone?.score || 0}/10</td>
                      </tr>
                      {/* Competitor rows */}
                      {competitors.map((comp: any, idx: number) => {
                        const domain = new URL(comp.url).hostname.replace('www.', '');
                        return (
                          <tr key={idx} className="hover:bg-muted/20 transition-colors">
                            <td className="p-4 text-muted-foreground">
                              <div className="flex items-center gap-2">
                                <span className="w-2 h-2 bg-slate-500 rounded-full" />
                                <a href={comp.url} target="_blank" rel="noopener noreferrer" className="hover:text-foreground hover:underline">
                                  {domain}
                                </a>
                              </div>
                            </td>
                            <td className="text-center p-4 font-bold text-foreground/90">
                              {comp.geo_score !== undefined && comp.geo_score !== null
                                ? `${comp.geo_score.toFixed(1)}%`
                                : '0.0%'}
                            </td>
                            <td className="text-center p-4 text-muted-foreground">{comp.schema_present ? '✓' : '✗'}</td>
                            <td className="text-center p-4 text-muted-foreground">{comp.structure_score?.toFixed(0) || 'N/A'}%</td>
                            <td className="text-center p-4 text-muted-foreground">{comp.eeat_score?.toFixed(0) || 'N/A'}</td>
                            <td className="text-center p-4 text-muted-foreground">{comp.h1_present ? '✓' : '✗'}</td>
                            <td className="text-center p-4 text-muted-foreground">{comp.tone_score?.toFixed(0) || '0'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="report">
            <div className="glass-card p-8">
              <div className="flex items-center justify-between gap-4 mb-6">
                <h2 className="text-2xl font-bold text-foreground flex items-center gap-3">
                  <FileText className="w-6 h-6 text-blue-400" />
                  Report (Markdown)
                </h2>
                <Button variant="outline" onClick={() => { setReportMarkdown(null); loadReport(); }}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Reload
                </Button>
              </div>

              {reportLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Loading report...
                </div>
              ) : (
                <pre className="whitespace-pre-wrap break-words text-sm bg-muted/40 border border-border rounded-xl p-4 overflow-auto max-h-[70vh]">
                  {reportMarkdown || 'No report available.'}
                </pre>
              )}
            </div>
          </TabsContent>

          <TabsContent value="fix-plan">
            <div className="glass-card p-8">
              <div className="flex items-center justify-between gap-4 mb-6">
                <h2 className="text-2xl font-bold text-foreground flex items-center gap-3">
                  <Target className="w-6 h-6 text-purple-400" />
                  Fix Plan
                </h2>
                <Button variant="outline" onClick={() => { setFixPlan(null); loadFixPlan(); }}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Reload
                </Button>
              </div>

              {fixPlanLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Loading fix plan...
                </div>
              ) : (fixPlan && fixPlan.length > 0) ? (
                <div className="space-y-3">
                  {fixPlan.map((item: any, idx: number) => (
                    <div key={idx} className="bg-muted/40 border border-border rounded-xl p-4">
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
                      {(item?.files || item?.recommendations || item?.steps) && (
                        <pre className="mt-3 text-xs bg-muted/30 border border-border rounded-lg p-3 overflow-auto">
                          {JSON.stringify({ files: item.files, recommendations: item.recommendations, steps: item.steps }, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-muted-foreground">No fix plan available.</div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div >
  );
}
