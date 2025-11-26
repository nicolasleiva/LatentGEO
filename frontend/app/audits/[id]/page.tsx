'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Header } from '@/components/header';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CoreWebVitalsChart } from '@/components/core-web-vitals-chart';
import { KeywordGapChart } from '@/components/keyword-gap-chart';
import { IssuesHeatmap } from '@/components/issues-heatmap';
import { ArrowLeft, Download, RefreshCw, ExternalLink, Globe, AlertTriangle, CheckCircle, Clock, FileText, Target, Search, Link as LinkIcon, TrendingUp, Edit, Sparkles } from 'lucide-react';

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

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  const fetchData = useCallback(async () => {
    try {
      const [auditRes, pagesRes] = await Promise.all([
        fetch(`${backendUrl}/api/audits/${auditId}`),
        fetch(`${backendUrl}/api/audits/${auditId}/pages`),
      ]);
      const auditData = await auditRes.json();
      const pagesData = await pagesRes.json();

      setAudit(auditData);
      setPages(pagesData);

      // PageSpeed data (if any)
      if (auditData.pagespeed_data && Object.keys(auditData.pagespeed_data).length > 0) {
        setPageSpeedData(auditData.pagespeed_data);
      }

      // Competitors (only when audit is finished)
      if (auditData.status === 'completed') {
        try {
          const compRes = await fetch(`${backendUrl}/api/audits/${auditId}/competitors`);
          if (compRes.ok) {
            const compData = await compRes.json();
            setCompetitors(compData);
          }
        } catch {
          console.log('No competitors data');
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [auditId, backendUrl]);

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll while audit is running
  useEffect(() => {
    if (audit?.status === 'completed') return;
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [audit?.status, fetchData]);

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <RefreshCw className="h-8 w-8 animate-spin text-white" />
        </main>
      </div>
    );
  }

  const analyzePageSpeed = async () => {
    setPageSpeedLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/audits/${auditId}/pagespeed`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setPageSpeedData(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setPageSpeedLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/20 text-green-300 border-green-500/30';
      case 'failed':
        return 'bg-red-500/20 text-red-300 border-red-500/30';
      default:
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="flex min-h-screen flex-col pb-20">
      <Header />

      <main className="flex-1 container mx-auto px-6 py-8">
        {/* Back button */}
        <Button variant="ghost" onClick={() => router.push('/audits')} className="mb-8 text-white/50 hover:text-white hover:bg-white/10 pl-0">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Audits
        </Button>

        {/* Header card */}
        <div className="glass-card p-8 mb-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Globe className="w-64 h-64 text-white" />
          </div>

          <div className="flex flex-col md:flex-row justify-between items-start relative z-10 gap-6">
            <div>
              <div className="flex items-center gap-4 mb-2">
                <h1 className="text-4xl font-bold text-white">
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
              <p className="text-lg text-white/60 mb-6 flex items-center gap-2">
                <Globe className="w-4 h-4" />
                {audit?.url ?? ''}
              </p>
            </div>

            {audit?.status === 'completed' && (
              <div className="flex gap-3">
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
                  onClick={() => window.open(`${backendUrl}/api/audits/${auditId}/download-pdf`)}
                  className="glass-button px-6"
                >
                  <Download className="h-4 w-4 mr-2" />
                  PDF Report
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

          {/* Progress bar (if not completed) */}
          {audit?.status !== 'completed' && (
            <div className="mt-8">
              <div className="flex justify-between mb-2 text-sm text-white/70">
                <span className="font-medium">Audit Progress</span>
                <span>{audit?.progress ?? 0}%</span>
              </div>
              <div className="w-full bg-white/10 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 to-purple-500 h-full rounded-full transition-all duration-500"
                  style={{ width: `${audit?.progress ?? 0}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Stats cards */}
        {audit?.status === 'completed' && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="glass-card p-6">
              <div className="flex items-center gap-3 mb-2 text-white/50">
                <FileText className="w-4 h-4" />
                <span className="text-sm font-medium uppercase tracking-wider">Pages</span>
              </div>
              <div className="text-3xl font-bold text-white">{audit.total_pages}</div>
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

        {/* PageSpeed COMPLETE Section */}
        {pageSpeedData && (
          <div className="glass-card p-8 mb-8">
            <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
              <Clock className="w-6 h-6 text-blue-400" />
              PageSpeed Insights
            </h2>

            {(() => {
              // Helper to get data whether it's flat or nested (mobile/desktop)
              const psData = pageSpeedData.mobile || (pageSpeedData.performance_score !== undefined ? pageSpeedData : null);

              if (!psData) return <div className="text-white/50">No detailed PageSpeed data available.</div>;

              return (
                <>
                  {/* Category Scores */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-black/20 p-4 rounded-xl border border-white/5 text-center">
                      <div className="text-xs text-white/40 mb-2">Performance</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.performance_score || 0)}`}>
                        {Math.round(psData.performance_score || 0)}
                      </div>
                    </div>
                    <div className="bg-black/20 p-4 rounded-xl border border-white/5 text-center">
                      <div className="text-xs text-white/40 mb-2">Accessibility</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.accessibility_score || 0)}`}>
                        {Math.round(psData.accessibility_score || 0)}
                      </div>
                    </div>
                    <div className="bg-black/20 p-4 rounded-xl border border-white/5 text-center">
                      <div className="text-xs text-white/40 mb-2">Best Practices</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.best_practices_score || 0)}`}>
                        {Math.round(psData.best_practices_score || 0)}
                      </div>
                    </div>
                    <div className="bg-black/20 p-4 rounded-xl border border-white/5 text-center">
                      <div className="text-xs text-white/40 mb-2">SEO</div>
                      <div className={`text-3xl font-bold ${getScoreColor(psData.seo_score || 0)}`}>
                        {Math.round(psData.seo_score || 0)}
                      </div>
                    </div>
                  </div>

                  {/* Core Web Vitals */}
                  {psData.core_web_vitals && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-white mb-4">Core Web Vitals</h3>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="bg-black/20 p-4 rounded-xl border border-white/5">
                          <div className="text-xs text-white/40 mb-1">LCP</div>
                          <div className="text-xl font-bold text-white">
                            {(psData.core_web_vitals.lcp / 1000).toFixed(2)}s
                          </div>
                        </div>
                        <div className="bg-black/20 p-4 rounded-xl border border-white/5">
                          <div className="text-xs text-white/40 mb-1">FID</div>
                          <div className="text-xl font-bold text-white">
                            {Math.round(psData.core_web_vitals.fid)}ms
                          </div>
                        </div>
                        <div className="bg-black/20 p-4 rounded-xl border border-white/5">
                          <div className="text-xs text-white/40 mb-1">CLS</div>
                          <div className="text-xl font-bold text-white">
                            {psData.core_web_vitals.cls.toFixed(3)}
                          </div>
                        </div>
                        <div className="bg-black/20 p-4 rounded-xl border border-white/5">
                          <div className="text-xs text-white/40 mb-1">FCP</div>
                          <div className="text-xl font-bold text-white">
                            {(psData.core_web_vitals.fcp / 1000).toFixed(2)}s
                          </div>
                        </div>
                        <div className="bg-black/20 p-4 rounded-xl border border-white/5">
                          <div className="text-xs text-white/40 mb-1">TTFB</div>
                          <div className="text-xl font-bold text-white">
                            {Math.round(psData.core_web_vitals.ttfb)}ms
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Metrics Chart */}
                  <div className="bg-black/20 rounded-2xl p-4 border border-white/5 mb-6">
                    <CoreWebVitalsChart data={pageSpeedData} />
                  </div>

                  {/* Opportunities */}
                  {psData.opportunities && Object.keys(psData.opportunities).length > 0 && (
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-white mb-4">Optimization Opportunities</h3>
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {Object.entries(psData.opportunities).map(([key, data]: [string, any]) => (
                          data && data.score !== null && data.score < 0.9 && (
                            <div key={key} className="bg-black/20 p-3 rounded-xl border border-white/5 flex items-start gap-3">
                              <AlertTriangle className={`w-4 h-4 mt-1 flex-shrink-0 ${data.score < 0.5 ? 'text-red-400' : 'text-yellow-400'}`} />
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-white">{data.title || key.replace(/-/g, ' ')}</div>
                                {data.displayValue && (
                                  <div className="text-xs text-white/50 mt-1">{data.displayValue}</div>
                                )}
                              </div>
                              <div className="text-xs text-white/30">
                                Score: {Math.round((data.score || 0) * 100)}
                              </div>
                            </div>
                          )
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Diagnostics */}
                  {psData.diagnostics && (
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-4">Diagnostics</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {psData.diagnostics.total_byte_weight && (
                          <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                            <div className="text-xs text-white/40">Total Byte Weight</div>
                            <div className="text-sm text-white">{psData.diagnostics.total_byte_weight.displayValue || 'N/A'}</div>
                          </div>
                        )}
                        {psData.diagnostics.dom_size && (
                          <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                            <div className="text-xs text-white/40">DOM Size</div>
                            <div className="text-sm text-white">{psData.diagnostics.dom_size.displayValue || 'N/A'}</div>
                          </div>
                        )}
                        {psData.diagnostics.bootup_time && (
                          <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                            <div className="text-xs text-white/40">JavaScript Bootup Time</div>
                            <div className="text-sm text-white">{psData.diagnostics.bootup_time.displayValue || 'N/A'}</div>
                          </div>
                        )}
                        {psData.diagnostics.mainthread_work_breakdown && (
                          <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                            <div className="text-xs text-white/40">Main Thread Work</div>
                            <div className="text-sm text-white">{psData.diagnostics.mainthread_work_breakdown.displayValue || 'N/A'}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        )}

        {/* Tools Section - COMPLETE */}
        {audit?.status === 'completed' && (
          <div className="glass-card p-8 mb-8">
            <h2 className="text-2xl font-bold text-white mb-6">SEO & GEO Tools</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* GEO Dashboard */}
              <button
                onClick={() => router.push(`/audits/${auditId}/geo`)}
                className="group bg-white/5 hover:bg-white/10 p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all text-left"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-3 bg-purple-500/20 rounded-xl">
                    <Target className="w-6 h-6 text-purple-400" />
                  </div>
                  <ExternalLink className="w-5 h-5 text-white/30 group-hover:text-white/60 transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">GEO Dashboard</h3>
                <p className="text-sm text-white/50">
                  Citation tracking, query discovery, and LLM optimization
                </p>
              </button>

              {/* Keywords Research */}
              <button
                onClick={() => router.push(`/audits/${auditId}/keywords`)}
                className="group bg-white/5 hover:bg-white/10 p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all text-left"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-3 bg-blue-500/20 rounded-xl">
                    <Search className="w-6 h-6 text-blue-400" />
                  </div>
                  <ExternalLink className="w-5 h-5 text-white/30 group-hover:text-white/60 transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Keywords Research</h3>
                <p className="text-sm text-white/50">
                  Discover and track relevant keywords for your niche
                </p>
              </button>

              {/* Backlinks Analysis */}
              <button
                onClick={() => router.push(`/audits/${auditId}/backlinks`)}
                className="group bg-white/5 hover:bg-white/10 p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all text-left"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-3 bg-green-500/20 rounded-xl">
                    <LinkIcon className="w-6 h-6 text-green-400" />
                  </div>
                  <ExternalLink className="w-5 h-5 text-white/30 group-hover:text-white/60 transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Backlinks</h3>
                <p className="text-sm text-white/50">
                  Analyze your backlink profile and opportunities
                </p>
              </button>

              {/* Rank Tracking */}
              <button
                onClick={() => router.push(`/audits/${auditId}/rank-tracking`)}
                className="group bg-white/5 hover:bg-white/10 p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all text-left"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-3 bg-orange-500/20 rounded-xl">
                    <TrendingUp className="w-6 h-6 text-orange-400" />
                  </div>
                  <ExternalLink className="w-5 h-5 text-white/30 group-hover:text-white/60 transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Rank Tracking</h3>
                <p className="text-sm text-white/50">
                  Monitor your rankings across search engines
                </p>
              </button>

              {/* Content Editor */}
              <button
                onClick={() => router.push(`/tools/content-editor?url=${encodeURIComponent(audit?.url || '')}`)}
                className="group bg-white/5 hover:bg-white/10 p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all text-left"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-3 bg-pink-500/20 rounded-xl">
                    <Edit className="w-6 h-6 text-pink-400" />
                  </div>
                  <ExternalLink className="w-5 h-5 text-white/30 group-hover:text-white/60 transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Content Editor</h3>
                <p className="text-sm text-white/50">
                  AI-powered content optimization for better visibility
                </p>
              </button>

              {/* AI Content Suggestions */}
              <button
                onClick={() => router.push(`/audits/${auditId}/ai-content`)}
                className="group bg-white/5 hover:bg-white/10 p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all text-left"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-3 bg-cyan-500/20 rounded-xl">
                    <Sparkles className="w-6 h-6 text-cyan-400" />
                  </div>
                  <ExternalLink className="w-5 h-5 text-white/30 group-hover:text-white/60 transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">AI Content Ideas</h3>
                <p className="text-sm text-white/50">
                  Generate content suggestions based on your audit
                </p>
              </button>
            </div>
          </div>
        )}

        {/* Pages analysis */}
        <div className="glass-card p-8 mb-8">
          <h2 className="text-2xl font-bold text-white mb-6">Analyzed Pages</h2>
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
                <div key={page.id} className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-colors">
                  <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-lg text-white truncate">{page.url}</h3>
                      <p className="text-sm text-white/50 truncate">{page.path}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-3xl font-bold text-white">{page.overall_score?.toFixed(1) || 0}</div>
                      <div className="text-xs text-white/40 uppercase tracking-wider">Score</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                      <div className="text-xs text-white/40 mb-1">H1</div>
                      <div className="font-semibold text-white">{page.h1_score?.toFixed(0) || 0}</div>
                    </div>
                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                      <div className="text-xs text-white/40 mb-1">Structure</div>
                      <div className="font-semibold text-white">{page.structure_score?.toFixed(0) || 0}</div>
                    </div>
                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                      <div className="text-xs text-white/40 mb-1">Content</div>
                      <div className="font-semibold text-white">{page.content_score?.toFixed(0) || 0}</div>
                    </div>
                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                      <div className="text-xs text-white/40 mb-1">E-E-A-T</div>
                      <div className="font-semibold text-white">{page.eeat_score?.toFixed(0) || 0}</div>
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
            <h2 className="text-2xl font-bold text-white mb-6">Competitive Analysis</h2>
            {/* Comparison chart (same SVG as before but styled for dark mode) */}
            <div className="mb-8 overflow-x-auto">
              <h3 className="text-lg font-semibold text-white/80 mb-4">GEO/SEO Score Comparison</h3>
              <div className="relative h-80 bg-black/20 border border-white/10 rounded-2xl p-6 min-w-[600px]">
                <svg className="w-full h-full" viewBox="0 0 800 300">
                  {[0, 2, 4, 6, 8, 10].map((val) => (
                    <g key={val}>
                      <line x1="60" y1={280 - val * 25} x2="780" y2={280 - val * 25} stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                      <text x="40" y={285 - val * 25} fontSize="12" fill="rgba(255,255,255,0.4)">
                        {val}
                      </text>
                    </g>
                  ))}
                  {(() => {
                    const allSites = [
                      {
                        name: 'Your Site',
                        score:
                          audit.total_pages > 0
                            ? 10 - (audit.critical_issues * 2 + audit.high_issues) / Math.max(1, audit.total_pages)
                            : 5,
                        color: '#a855f7', // Purple
                      },
                      ...competitors.slice(0, 5).map((comp: any) => {
                        const domain = comp.domain || new URL(comp.url).hostname.replace('www.', '');
                        const geoScore = comp.geo_score || 5;
                        return { name: domain, score: geoScore, color: '#94a3b8' }; // Slate 400
                      }),
                    ];
                    const spacing = 720 / (allSites.length - 1);
                    return (
                      <>
                        {allSites.map((site, idx) => {
                          if (idx === allSites.length - 1) return null;
                          const x1 = 60 + idx * spacing;
                          const y1 = 280 - site.score * 25;
                          const x2 = 60 + (idx + 1) * spacing;
                          const y2 = 280 - allSites[idx + 1].score * 25;
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
                          const y = 280 - site.score * 25;
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
              <h3 className="text-lg font-semibold text-white/80 mb-4">Detailed Benchmark</h3>
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="border-b border-white/10 text-white/50">
                    <th className="p-4 font-medium">Website</th>
                    <th className="text-center p-4 font-medium">GEO Score</th>
                    <th className="text-center p-4 font-medium">Schema</th>
                    <th className="text-center p-4 font-medium">Semantic HTML</th>
                    <th className="text-center p-4 font-medium">E-E-A-T</th>
                    <th className="text-center p-4 font-medium">H1</th>
                    <th className="text-center p-4 font-medium">Tone</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {/* Your site row */}
                  <tr className="bg-white/5">
                    <td className="p-4 font-semibold text-white">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 bg-purple-500 rounded-full shadow-[0_0_10px_rgba(168,85,247,0.5)]" />
                        Your Site
                      </div>
                    </td>
                    <td className="text-center p-4 font-bold text-purple-400">
                      {(() => {
                        const comp = audit.comparative_analysis;
                        if (comp?.scores?.[0]) {
                          return comp.scores[0].scores.total.toFixed(1);
                        }
                        return (10 - (audit.critical_issues * 2 + audit.high_issues) / Math.max(1, audit.total_pages)).toFixed(1);
                      })()}
                    </td>
                    <td className="text-center p-4 text-white/70">{audit.target_audit?.schema?.schema_presence?.status === 'present' ? '✓' : '✗'}</td>
                    <td className="text-center p-4 text-white/70">{audit.target_audit?.structure?.semantic_html?.score_percent?.toFixed(0) || 'N/A'}%</td>
                    <td className="text-center p-4 text-white/70">{audit.target_audit?.eeat?.author_presence?.status === 'pass' ? '✓' : '✗'}</td>
                    <td className="text-center p-4 text-white/70">{audit.target_audit?.structure?.h1_check?.status === 'pass' ? '✓' : '✗'}</td>
                    <td className="text-center p-4 text-white/70">{audit.target_audit?.content?.conversational_tone?.score || 0}/10</td>
                  </tr>
                  {/* Competitor rows */}
                  {competitors.map((comp: any, idx: number) => {
                    const domain = new URL(comp.url).hostname.replace('www.', '');
                    return (
                      <tr key={idx} className="hover:bg-white/5 transition-colors">
                        <td className="p-4 text-white/70">
                          <div className="flex items-center gap-2">
                            <span className="w-2 h-2 bg-slate-500 rounded-full" />
                            <a href={comp.url} target="_blank" rel="noopener noreferrer" className="hover:text-white hover:underline">
                              {domain}
                            </a>
                          </div>
                        </td>
                        <td className="text-center p-4 font-bold text-white/90">{comp.geo_score?.toFixed(1) || '5.0'}</td>
                        <td className="text-center p-4 text-white/50">{comp.schema_present ? '✓' : '✗'}</td>
                        <td className="text-center p-4 text-white/50">{comp.structure_score?.toFixed(0) || 'N/A'}%</td>
                        <td className="text-center p-4 text-white/50">{comp.eeat_score?.toFixed(0) || 'N/A'}</td>
                        <td className="text-center p-4 text-white/50">{comp.h1_present ? '✓' : '✗'}</td>
                        <td className="text-center p-4 text-white/50">{comp.tone_score?.toFixed(0) || '0'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
