'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CoreWebVitalsChart } from '@/components/core-web-vitals-chart'
import { KeywordGapChart } from '@/components/keyword-gap-chart'
import { IssuesHeatmap } from '@/components/issues-heatmap'
import { ArrowLeft, Download, RefreshCw, ExternalLink } from 'lucide-react'

export default function AuditDetailPage() {
  const params = useParams()
  const router = useRouter()
  const auditId = params.id as string
  
  const [audit, setAudit] = useState<any>(null)
  const [pages, setPages] = useState<any[]>([])
  const [competitors, setCompetitors] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [pageSpeedData, setPageSpeedData] = useState<any>(null)
  const [keywordGapData, setKeywordGapData] = useState<any>(null)
  const [pageSpeedLoading, setPageSpeedLoading] = useState(false)

  const fetchData = async () => {
    try {
      const [auditRes, pagesRes] = await Promise.all([
        fetch(`http://localhost:8000/api/audits/${auditId}`),
        fetch(`http://localhost:8000/api/audits/${auditId}/pages`)
      ])
      
      const auditData = await auditRes.json()
      const pagesData = await pagesRes.json()
      
      setAudit(auditData)
      setPages(pagesData)
      
      // Cargar PageSpeed desde BD si existe
      if (auditData.pagespeed_data && Object.keys(auditData.pagespeed_data).length > 0) {
        console.log('PageSpeed data loaded from DB:', auditData.pagespeed_data)
        setPageSpeedData(auditData.pagespeed_data)
      } else {
        console.log('No PageSpeed data in DB')
      }
      
      if (auditData.status === 'completed') {
        try {
          const compRes = await fetch(`http://localhost:8000/api/audits/${auditId}/competitors`)
          if (compRes.ok) {
            const compData = await compRes.json()
            setCompetitors(compData)
          }
        } catch (e) {
          console.log('No competitors data')
        }
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [auditId])
  
  useEffect(() => {
    if (audit?.status === 'completed') return
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [audit?.status])

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <RefreshCw className="h-8 w-8 animate-spin" />
        </main>
      </div>
    )
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-black'
      case 'failed': return 'bg-gray-600'
      default: return 'bg-gray-400'
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      
      <main className="flex-1 container mx-auto px-4 py-8">
        <Button variant="ghost" onClick={() => router.push('/audits')} className="mb-6">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>

        <div className="space-y-6">
          {/* Header */}
          <div className="bg-white border-2 border-black rounded-lg p-6">
            <div className="flex justify-between items-start">
              <div>
                <h1 className="text-3xl font-bold mb-2">{audit.domain || new URL(audit.url).hostname.replace('www.', '')}</h1>
                <p className="text-lg text-muted-foreground mb-4">{audit.url}</p>
                <span className={`px-3 py-1 rounded-full text-white text-sm ${getStatusColor(audit.status)}`}>
                  {audit.status}
                </span>
              </div>
              {audit.status === 'completed' && (
                <Button onClick={() => window.open(`http://localhost:8000/api/audits/${auditId}/download-pdf`)}>
                  <Download className="h-4 w-4 mr-2" />
                  Descargar PDF
                </Button>
              )}
            </div>
          </div>

          {/* Progress */}
          {audit.status !== 'completed' && (
            <div className="bg-white border-2 border-black rounded-lg p-6">
              <div className="flex justify-between mb-2">
                <span className="font-semibold">Progreso</span>
                <span>{audit.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-4">
                <div className="bg-black h-4 rounded-full" style={{ width: `${audit.progress}%` }} />
              </div>
            </div>
          )}

          {/* Stats Cards */}
          {audit.status === 'completed' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white border-2 border-black rounded-lg p-6">
                  <div className="text-3xl font-bold mb-2">{audit.total_pages}</div>
                  <div className="text-sm text-muted-foreground">Páginas Analizadas</div>
                </div>
                <div className="bg-white border-2 border-black rounded-lg p-6">
                  <div className="text-3xl font-bold mb-2">{audit.critical_issues}</div>
                  <div className="text-sm text-muted-foreground">Issues Críticos</div>
                </div>
                <div className="bg-white border-2 border-black rounded-lg p-6">
                  <div className="text-3xl font-bold mb-2">{audit.high_issues}</div>
                  <div className="text-sm text-muted-foreground">Issues Altos</div>
                </div>
                <div className="bg-white border-2 border-black rounded-lg p-6">
                  <div className="text-3xl font-bold mb-2">{audit.medium_issues}</div>
                  <div className="text-sm text-muted-foreground">Issues Medios</div>
                </div>
              </div>

              {/* Pages Analysis */}
              <div className="bg-white border-2 border-black rounded-lg p-6">
                <h2 className="text-2xl font-bold mb-4">Páginas Analizadas</h2>
                <div className="space-y-4">
                  {pages.map((page: any) => {
                    const issues = []
                    if (page.audit_data?.structure?.h1_check?.status !== 'pass') {
                      issues.push({ severity: 'critical', msg: 'H1 faltante o múltiple' })
                    }
                    if (!page.audit_data?.schema?.schema_presence?.status || page.audit_data?.schema?.schema_presence?.status !== 'present') {
                      issues.push({ severity: 'high', msg: 'Schema markup faltante' })
                    }
                    if (page.audit_data?.eeat?.author_presence?.status !== 'pass') {
                      issues.push({ severity: 'high', msg: 'Autor no identificado' })
                    }
                    if (page.audit_data?.structure?.semantic_html?.score_percent < 50) {
                      issues.push({ severity: 'medium', msg: 'HTML semántico bajo' })
                    }
                    
                    return (
                      <div key={page.id} className="border-2 border-gray-200 rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <div className="flex-1">
                            <h3 className="font-semibold">{page.url}</h3>
                            <p className="text-sm text-muted-foreground">{page.path}</p>
                          </div>
                          <div className="text-right">
                            <div className="text-2xl font-bold">{page.overall_score?.toFixed(1) || 0}</div>
                            <div className="text-xs text-muted-foreground">Score</div>
                          </div>
                        </div>
                        <div className="grid grid-cols-4 gap-2 mt-4">
                          <div>
                            <div className="text-xs text-muted-foreground">H1</div>
                            <div className="font-semibold">{page.h1_score?.toFixed(0) || 0}</div>
                          </div>
                          <div>
                            <div className="text-xs text-muted-foreground">Estructura</div>
                            <div className="font-semibold">{page.structure_score?.toFixed(0) || 0}</div>
                          </div>
                          <div>
                            <div className="text-xs text-muted-foreground">Contenido</div>
                            <div className="font-semibold">{page.content_score?.toFixed(0) || 0}</div>
                          </div>
                          <div>
                            <div className="text-xs text-muted-foreground">E-E-A-T</div>
                            <div className="font-semibold">{page.eeat_score?.toFixed(0) || 0}</div>
                          </div>
                        </div>
                        <div className="flex gap-2 mt-2">
                          <span className="text-xs px-2 py-1 bg-gray-900 text-white rounded">
                            {page.critical_issues} críticos
                          </span>
                          <span className="text-xs px-2 py-1 bg-gray-600 text-white rounded">
                            {page.high_issues} altos
                          </span>
                          <span className="text-xs px-2 py-1 bg-gray-400 text-white rounded">
                            {page.medium_issues} medios
                          </span>
                        </div>
                        {issues.length > 0 && (
                          <div className="mt-4 space-y-2">
                            <div className="text-sm font-semibold">Issues Detectados:</div>
                            {issues.map((issue, idx) => (
                              <div key={idx} className={`text-sm p-2 rounded border ${
                                issue.severity === 'critical' ? 'bg-gray-900 text-white border-black' :
                                issue.severity === 'high' ? 'bg-gray-600 text-white border-gray-700' :
                                'bg-gray-300 text-black border-gray-400'
                              }`}>
                                • {issue.msg}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Competitive Analysis with Charts */}
              {competitors.length > 0 && (
                <>
                  {/* Comparison Chart */}
                  <div className="bg-white border-2 border-black rounded-lg p-6">
                    <h2 className="text-2xl font-bold mb-6">Análisis Comparativo de Competencia</h2>
                    
                    {/* Line Chart */}
                    <div className="mb-8">
                      <h3 className="text-lg font-semibold mb-4">Comparativa de Scores GEO/SEO</h3>
                      <div className="relative h-80 border-2 border-gray-200 rounded-lg p-4">
                        <svg className="w-full h-full" viewBox="0 0 800 300">
                          {/* Grid lines */}
                          {[0, 2, 4, 6, 8, 10].map((val) => (
                            <g key={val}>
                              <line
                                x1="60"
                                y1={280 - (val * 25)}
                                x2="780"
                                y2={280 - (val * 25)}
                                stroke="#e5e7eb"
                                strokeWidth="1"
                              />
                              <text x="40" y={285 - (val * 25)} fontSize="12" fill="#6b7280">
                                {val}
                              </text>
                            </g>
                          ))}
                          
                          {/* X-axis labels and data points */}
                          {(() => {
                            const allSites = [
                              { name: 'Tu Sitio', score: audit.total_pages > 0 ? (10 - (audit.critical_issues * 2 + audit.high_issues) / Math.max(1, audit.total_pages)) : 5, color: '#000000' },
                              ...competitors.slice(0, 5).map((comp: any) => {
                                const domain = comp.domain || new URL(comp.url).hostname.replace('www.', '')
                                const geoScore = comp.geo_score || 5
                                return { name: domain, score: geoScore, color: '#6b7280' }
                              })
                            ]
                            const spacing = 720 / (allSites.length - 1)
                            
                            return (
                              <>
                                {/* Lines connecting points */}
                                {allSites.map((site, idx) => {
                                  if (idx === allSites.length - 1) return null
                                  const x1 = 60 + (idx * spacing)
                                  const y1 = 280 - (site.score * 25)
                                  const x2 = 60 + ((idx + 1) * spacing)
                                  const y2 = 280 - (allSites[idx + 1].score * 25)
                                  return (
                                    <line
                                      key={`line-${idx}`}
                                      x1={x1}
                                      y1={y1}
                                      x2={x2}
                                      y2={y2}
                                      stroke={site.color}
                                      strokeWidth="3"
                                    />
                                  )
                                })}
                                
                                {/* Data points */}
                                {allSites.map((site, idx) => {
                                  const x = 60 + (idx * spacing)
                                  const y = 280 - (site.score * 25)
                                  return (
                                    <g key={`point-${idx}`}>
                                      <circle cx={x} cy={y} r="6" fill={site.color} />
                                      <circle cx={x} cy={y} r="3" fill="white" />
                                      <text
                                        x={x}
                                        y="295"
                                        fontSize="11"
                                        fill="#374151"
                                        textAnchor="middle"
                                        transform={`rotate(-45, ${x}, 295)`}
                                      >
                                        {site.name.length > 15 ? site.name.substring(0, 15) + '...' : site.name}
                                      </text>
                                      <text
                                        x={x}
                                        y={y - 12}
                                        fontSize="12"
                                        fontWeight="bold"
                                        fill={site.color}
                                        textAnchor="middle"
                                      >
                                        {site.score.toFixed(1)}
                                      </text>
                                    </g>
                                  )
                                })}
                              </>
                            )
                          })()}
                        </svg>
                      </div>
                    </div>

                    {/* Detailed Comparison Table */}
                    <div className="overflow-x-auto">
                      <h3 className="text-lg font-semibold mb-4">Tabla Comparativa Detallada</h3>
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b-2 border-gray-300">
                            <th className="text-left p-3 font-semibold">Sitio Web</th>
                            <th className="text-center p-3 font-semibold">GEO Score</th>
                            <th className="text-center p-3 font-semibold">Schema</th>
                            <th className="text-center p-3 font-semibold">HTML Semántico</th>
                            <th className="text-center p-3 font-semibold">E-E-A-T</th>
                            <th className="text-center p-3 font-semibold">H1</th>
                            <th className="text-center p-3 font-semibold">Tono Conv.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {/* Your site */}
                          <tr className="border-b border-gray-200 bg-gray-100">
                            <td className="p-3 font-semibold">
                              <div className="flex items-center gap-2">
                                <span className="w-3 h-3 bg-black rounded-full"></span>
                                Tu Sitio
                              </div>
                            </td>
                            <td className="text-center p-3 font-bold">
                              {(() => {
                                const comparativeAnalysis = audit.comparative_analysis
                                if (comparativeAnalysis?.scores?.[0]) {
                                  return comparativeAnalysis.scores[0].scores.total.toFixed(1)
                                }
                                return (10 - (audit.critical_issues * 2 + audit.high_issues) / Math.max(1, audit.total_pages)).toFixed(1)
                              })()}
                            </td>
                            <td className="text-center p-3">
                              {audit.target_audit?.schema?.schema_presence?.status === 'present' ? '✓' : '✗'}
                            </td>
                            <td className="text-center p-3">
                              {audit.target_audit?.structure?.semantic_html?.score_percent?.toFixed(0) || 'N/A'}%
                            </td>
                            <td className="text-center p-3">
                              {audit.target_audit?.eeat?.author_presence?.status === 'pass' ? '✓' : '✗'}
                            </td>
                            <td className="text-center p-3">
                              {audit.target_audit?.structure?.h1_check?.status === 'pass' ? '✓' : '✗'}
                            </td>
                            <td className="text-center p-3">
                              {audit.target_audit?.content?.conversational_tone?.score || 0}/10
                            </td>
                          </tr>
                          
                          {/* Competitors */}
                          {(() => {
                            // Usar datos del nuevo análisis comparativo si están disponibles
                            const comparativeAnalysis = audit.comparative_analysis
                            if (comparativeAnalysis?.scores) {
                              return comparativeAnalysis.scores.slice(1).map((item: any, idx: number) => {
                                const domain = new URL(item.url).hostname.replace('www.', '')
                                const scores = item.scores
                                return (
                                  <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                                    <td className="p-3">
                                      <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 bg-gray-600 rounded-full"></span>
                                        <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                                          {domain}
                                        </a>
                                      </div>
                                    </td>
                                    <td className="text-center p-3 font-bold">
                                      {scores.total.toFixed(1)}
                                    </td>
                                    <td className="text-center p-3">
                                      {scores.schema > 0 ? '✓' : '✗'}
                                    </td>
                                    <td className="text-center p-3">
                                      {scores.structure.toFixed(0)}%
                                    </td>
                                    <td className="text-center p-3">
                                      {scores.eeat > 0 ? '✓' : '✗'}
                                    </td>
                                    <td className="text-center p-3">
                                      {scores.structure >= 25 ? '✓' : '✗'}
                                    </td>
                                    <td className="text-center p-3">
                                      {scores.content.toFixed(0)}/100
                                    </td>
                                  </tr>
                                )
                              })
                            }
                            // Fallback a datos antiguos
                            return competitors.slice(0, 5).map((comp: any, idx: number) => {
                              const domain = comp.domain || new URL(comp.url).hostname.replace('www.', '')
                              const geoScore = comp.geo_score || 0
                              return (
                                <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                                  <td className="p-3">
                                    <div className="flex items-center gap-2">
                                      <span className="w-3 h-3 bg-gray-600 rounded-full"></span>
                                      <a href={`https://${domain}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                                        {domain}
                                      </a>
                                    </div>
                                  </td>
                                  <td className="text-center p-3 font-bold">
                                    {typeof geoScore === 'number' ? geoScore.toFixed(1) : geoScore}
                                  </td>
                                  <td className="text-center p-3">
                                    {comp.audit_data?.schema?.schema_presence?.status === 'present' ? '✓' : '✗'}
                                  </td>
                                  <td className="text-center p-3">
                                    {comp.audit_data?.structure?.semantic_html?.score_percent?.toFixed(0) || 'N/A'}%
                                  </td>
                                  <td className="text-center p-3">
                                    {comp.audit_data?.eeat?.author_presence?.status === 'pass' ? '✓' : '✗'}
                                  </td>
                                  <td className="text-center p-3">
                                    {comp.audit_data?.structure?.h1_check?.status === 'pass' ? '✓' : '✗'}
                                  </td>
                                  <td className="text-center p-3">
                                    {comp.audit_data?.content?.conversational_tone?.score || 0}/10
                                  </td>
                                </tr>
                              )
                            })
                          })()}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Competitive Insights */}
                  <div className="bg-white border-2 border-black rounded-lg p-6">
                    <h2 className="text-2xl font-bold mb-4">Insights Competitivos</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="border-2 border-gray-200 rounded-lg p-4">
                        <div className="text-sm text-muted-foreground mb-1">Tu Posición</div>
                        <div className="text-3xl font-bold">
                          #{(() => {
                            const yourScore = 10 - (audit.critical_issues * 2 + audit.high_issues) / Math.max(1, audit.total_pages)
                            const allScores = [yourScore, ...competitors.map((c: any) => c.geo_score || 0)]
                            return allScores.filter(s => s > yourScore).length + 1
                          })()}
                        </div>
                        <div className="text-xs text-muted-foreground">de {competitors.length + 1} sitios</div>
                      </div>
                      <div className="border-2 border-gray-200 rounded-lg p-4">
                        <div className="text-sm text-muted-foreground mb-1">Gap vs Líder</div>
                        <div className="text-3xl font-bold">
                          {(() => {
                            const yourScore = 10 - (audit.critical_issues * 2 + audit.high_issues) / Math.max(1, audit.total_pages)
                            const maxCompScore = Math.max(...competitors.map((c: any) => c.geo_score || 0))
                            return Math.max(0, maxCompScore - yourScore).toFixed(1)
                          })()}
                        </div>
                        <div className="text-xs text-muted-foreground">puntos de diferencia</div>
                      </div>
                      <div className="border-2 border-gray-200 rounded-lg p-4">
                        <div className="text-sm text-muted-foreground mb-1">Ventaja Potencial</div>
                        <div className="text-3xl font-bold">
                          {(() => {
                            const yourScore = 10 - (audit.critical_issues * 2 + audit.high_issues) / Math.max(1, audit.total_pages)
                            return Math.max(0, 10 - yourScore).toFixed(1)
                          })()}
                        </div>
                        <div className="text-xs text-muted-foreground">puntos de mejora</div>
                      </div>
                    </div>
                    
                    {/* Competitive Advantages */}
                    <div className="mt-6 space-y-4">
                      <h3 className="font-semibold">Ventajas Competitivas Detectadas:</h3>
                      {(() => {
                        const advantages = []
                        const hasSchema = audit.target_audit?.schema?.schema_presence?.status === 'present'
                        const compWithSchema = competitors.filter((c: any) => c.audit_data?.schema?.schema_presence?.status === 'present').length
                        
                        if (hasSchema && compWithSchema < competitors.length / 2) {
                          advantages.push('✓ Implementación de Schema.org superior a la mayoría de competidores')
                        } else if (!hasSchema && compWithSchema > competitors.length / 2) {
                          advantages.push('✗ Falta de Schema.org te coloca en desventaja frente a competidores')
                        }
                        
                        const yourSemantic = audit.target_audit?.structure?.semantic_html?.score_percent || 0
                        const avgCompSemantic = competitors.reduce((sum: number, c: any) => 
                          sum + (c.audit_data?.structure?.semantic_html?.score_percent || 0), 0) / competitors.length
                        
                        if (yourSemantic > avgCompSemantic) {
                          advantages.push(`✓ HTML Semántico ${(yourSemantic - avgCompSemantic).toFixed(0)}% superior al promedio`)
                        } else {
                          advantages.push(`✗ HTML Semántico ${(avgCompSemantic - yourSemantic).toFixed(0)}% inferior al promedio`)
                        }
                        
                        return advantages.map((adv, idx) => (
                          <div key={idx} className={`p-3 rounded border ${adv.startsWith('✓') ? 'bg-gray-100 border-black' : 'bg-gray-800 text-white border-gray-900'}`}>
                            {adv}
                          </div>
                        ))
                      })()}
                    </div>
                  </div>
                </>
              )}

              {/* New Features Tabs */}
              <div className="bg-white border-2 border-black rounded-lg p-6">
                <h2 className="text-2xl font-bold mb-4">Análisis Avanzado</h2>
                <Tabs defaultValue="pagespeed">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="pagespeed">Core Web Vitals</TabsTrigger>
                    <TabsTrigger value="keywords">Keyword Gap</TabsTrigger>
                    <TabsTrigger value="heatmap">Issues Heatmap</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="pagespeed" className="mt-4">
                    {pageSpeedData ? (
                      <CoreWebVitalsChart data={pageSpeedData} />
                    ) : (
                      <div className="text-center py-8">
                        <p className="text-sm text-muted-foreground">PageSpeed data no disponible para esta auditoría</p>
                      </div>
                    )}
                  </TabsContent>
                  
                  <TabsContent value="keywords" className="mt-4">
                    {!keywordGapData && competitors.length > 0 ? (
                      <div className="text-center py-8">
                        <Button onClick={async () => {
                          const compUrl = competitors[0]?.url
                          if (compUrl) {
                            const res = await fetch(`http://localhost:8000/api/content/keywords/compare?your_url=${encodeURIComponent(audit.url)}&competitor_url=${encodeURIComponent(compUrl)}`)
                            const data = await res.json()
                            setKeywordGapData(data)
                          }
                        }}>
                          Analizar Keywords vs {competitors[0]?.domain}
                        </Button>
                      </div>
                    ) : keywordGapData ? (
                      <KeywordGapChart data={keywordGapData} />
                    ) : (
                      <p className="text-center py-8 text-muted-foreground">No hay competidores para comparar</p>
                    )}
                  </TabsContent>
                  
                  <TabsContent value="heatmap" className="mt-4">
                    <IssuesHeatmap data={pages.map(p => ({
                      url: p.path,
                      critical: p.critical_issues || 0,
                      high: p.high_issues || 0,
                      medium: p.medium_issues || 0,
                      low: p.low_issues || 0
                    }))} />
                  </TabsContent>
                </Tabs>
              </div>

              {/* JSON Data */}
              <div className="bg-white border-2 border-black rounded-lg p-6">
                <h2 className="text-2xl font-bold mb-4">Datos Completos (JSON)</h2>
                <div className="space-y-4">
                  <details className="border-2 border-gray-200 rounded-lg p-4">
                    <summary className="font-semibold cursor-pointer">Target Audit</summary>
                    <pre className="mt-2 text-xs overflow-auto max-h-96 bg-gray-50 p-4 rounded">
                      {JSON.stringify(audit.target_audit, null, 2)}
                    </pre>
                  </details>
                  <details className="border-2 border-gray-200 rounded-lg p-4">
                    <summary className="font-semibold cursor-pointer">External Intelligence</summary>
                    <pre className="mt-2 text-xs overflow-auto max-h-96 bg-gray-50 p-4 rounded">
                      {JSON.stringify(audit.external_intelligence, null, 2)}
                    </pre>
                  </details>
                  <details className="border-2 border-gray-200 rounded-lg p-4">
                    <summary className="font-semibold cursor-pointer">Fix Plan</summary>
                    <pre className="mt-2 text-xs overflow-auto max-h-96 bg-gray-50 p-4 rounded">
                      {JSON.stringify(audit.fix_plan, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
