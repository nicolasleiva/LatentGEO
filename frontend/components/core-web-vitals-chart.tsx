"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"

interface CoreWebVitalsProps {
  data: {
    mobile?: {
      performance_score: number
      accessibility_score: number
      best_practices_score: number
      seo_score: number
      core_web_vitals: { lcp: number; fid: number; cls: number; fcp: number; ttfb: number }
      metadata?: { fetch_time: string; user_agent: string; lighthouse_version: string }
      metrics?: { fcp: number; lcp: number; tbt: number; cls: number; si: number }
      opportunities?: any
      diagnostics?: any
      screenshots?: Array<{data: string, timestamp: number}>
    }
    desktop?: {
      performance_score: number
      accessibility_score: number
      best_practices_score: number
      seo_score: number
      core_web_vitals: { lcp: number; fid: number; cls: number; fcp: number; ttfb: number }
      metadata?: { fetch_time: string; user_agent: string; lighthouse_version: string }
      metrics?: { fcp: number; lcp: number; tbt: number; cls: number; si: number }
      opportunities?: any
      diagnostics?: any
      screenshots?: Array<{data: string, timestamp: number}>
    }
  }
}

export function CoreWebVitalsChart({ data }: CoreWebVitalsProps) {
  const scoresData = [
    { metric: "Performance", Mobile: data.mobile?.performance_score || 0, Desktop: data.desktop?.performance_score || 0 },
    { metric: "Accessibility", Mobile: data.mobile?.accessibility_score || 0, Desktop: data.desktop?.accessibility_score || 0 },
    { metric: "Best Practices", Mobile: data.mobile?.best_practices_score || 0, Desktop: data.desktop?.best_practices_score || 0 },
    { metric: "SEO", Mobile: data.mobile?.seo_score || 0, Desktop: data.desktop?.seo_score || 0 },
  ]

  const vitalsData = [
    { metric: "LCP (s)", Mobile: ((data.mobile?.core_web_vitals?.lcp || 0) / 1000).toFixed(2), Desktop: ((data.desktop?.core_web_vitals?.lcp || 0) / 1000).toFixed(2) },
    { metric: "FID (ms)", Mobile: (data.mobile?.core_web_vitals?.fid || 0).toFixed(0), Desktop: (data.desktop?.core_web_vitals?.fid || 0).toFixed(0) },
    { metric: "CLS (x100)", Mobile: ((data.mobile?.core_web_vitals?.cls || 0) * 100).toFixed(2), Desktop: ((data.desktop?.core_web_vitals?.cls || 0) * 100).toFixed(2) },
    { metric: "FCP (s)", Mobile: ((data.mobile?.core_web_vitals?.fcp || 0) / 1000).toFixed(2), Desktop: ((data.desktop?.core_web_vitals?.fcp || 0) / 1000).toFixed(2) },
  ]

  const formatDate = (isoString: string) => {
    if (!isoString) return 'N/A'
    return new Date(isoString).toLocaleString('es-AR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })
  }

  return (
    <div className="space-y-4">
      {data.mobile?.metadata && (
        <Card>
          <CardHeader><CardTitle>Test Information</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="font-semibold mb-2">Mobile</div>
                <div className="space-y-1 text-gray-600">
                  <div>Captured at {formatDate(data.mobile.metadata.fetch_time)}</div>
                  <div>Moto G Power emulado</div>
                  <div>Lighthouse {data.mobile.metadata.lighthouse_version}</div>
                  <div>Network: 4G throttling</div>
                </div>
              </div>
              {data.desktop?.metadata && (
                <div>
                  <div className="font-semibold mb-2">Desktop</div>
                  <div className="space-y-1 text-gray-600">
                    <div>Captured at {formatDate(data.desktop.metadata.fetch_time)}</div>
                    <div>Desktop Browser</div>
                    <div>Lighthouse {data.desktop.metadata.lighthouse_version}</div>
                    <div>Network: Simulated</div>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {data.mobile?.metrics && (
        <Card>
          <CardHeader><CardTitle>Detailed Metrics</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">FCP</div><div className="text-xl font-bold">{(data.mobile.metrics.fcp / 1000).toFixed(1)}s</div><div className="text-xs text-gray-500 mt-1">Mobile</div></div>
              <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">LCP</div><div className="text-xl font-bold">{(data.mobile.metrics.lcp / 1000).toFixed(1)}s</div><div className="text-xs text-gray-500 mt-1">Mobile</div></div>
              <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">TBT</div><div className="text-xl font-bold">{data.mobile.metrics.tbt.toFixed(0)}ms</div><div className="text-xs text-gray-500 mt-1">Mobile</div></div>
              <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">CLS</div><div className="text-xl font-bold">{data.mobile.metrics.cls.toFixed(3)}</div><div className="text-xs text-gray-500 mt-1">Mobile</div></div>
              <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">SI</div><div className="text-xl font-bold">{(data.mobile.metrics.si / 1000).toFixed(1)}s</div><div className="text-xs text-gray-500 mt-1">Mobile</div></div>
            </div>
            {data.desktop?.metrics && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4">
                <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">FCP</div><div className="text-xl font-bold">{(data.desktop.metrics.fcp / 1000).toFixed(1)}s</div><div className="text-xs text-gray-500 mt-1">Desktop</div></div>
                <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">LCP</div><div className="text-xl font-bold">{(data.desktop.metrics.lcp / 1000).toFixed(1)}s</div><div className="text-xs text-gray-500 mt-1">Desktop</div></div>
                <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">TBT</div><div className="text-xl font-bold">{data.desktop.metrics.tbt.toFixed(0)}ms</div><div className="text-xs text-gray-500 mt-1">Desktop</div></div>
                <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">CLS</div><div className="text-xl font-bold">{data.desktop.metrics.cls.toFixed(3)}</div><div className="text-xs text-gray-500 mt-1">Desktop</div></div>
                <div className="text-center p-3 border rounded"><div className="text-xs text-gray-500 mb-1">SI</div><div className="text-xl font-bold">{(data.desktop.metrics.si / 1000).toFixed(1)}s</div><div className="text-xs text-gray-500 mt-1">Desktop</div></div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {data.mobile?.screenshots && data.mobile.screenshots.length > 0 && (
          <Card>
            <CardHeader><CardTitle>Loading Screenshots (Mobile)</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-2">
                {data.mobile.screenshots.map((s, i) => (
                  <div key={i} className="border rounded overflow-hidden">
                    <img src={s.data} alt={`Screenshot ${i + 1}`} className="w-full" />
                    <div className="text-xs text-center p-1 bg-gray-100">{(s.timestamp / 1000).toFixed(1)}s</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
        {data.desktop?.screenshots && data.desktop.screenshots.length > 0 && (
          <Card>
            <CardHeader><CardTitle>Loading Screenshots (Desktop)</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-2">
                {data.desktop.screenshots.map((s, i) => (
                  <div key={i} className="border rounded overflow-hidden">
                    <img src={s.data} alt={`Screenshot ${i + 1}`} className="w-full" />
                    <div className="text-xs text-center p-1 bg-gray-100">{(s.timestamp / 1000).toFixed(1)}s</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Lighthouse Scores</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={scoresData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="metric" stroke="#000" />
                <YAxis domain={[0, 100]} stroke="#000" />
                <Tooltip contentStyle={{ backgroundColor: '#fff', border: '1px solid #000' }} />
                <Legend />
                <Bar dataKey="Mobile" fill="#000" />
                <Bar dataKey="Desktop" fill="#666" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Core Web Vitals</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-4">
              {vitalsData.map((item, idx) => (
                <div key={idx} className="border-b pb-3">
                  <div className="flex justify-between items-center mb-2"><span className="font-semibold text-sm">{item.metric}</span></div>
                  <div className="grid grid-cols-2 gap-4">
                    <div><div className="text-xs text-gray-500 mb-1">Mobile</div><div className="text-2xl font-bold">{item.Mobile}</div></div>
                    <div><div className="text-xs text-gray-500 mb-1">Desktop</div><div className="text-2xl font-bold">{item.Desktop}</div></div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {data.mobile?.opportunities && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Opportunities (Mobile)</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {Object.entries(data.mobile.opportunities).map(([key, audit]: [string, any]) => 
                  audit?.title && (
                    <div key={key} className="flex justify-between border-b pb-2">
                      <span>{audit.title}</span>
                      <span className="font-semibold">{audit.displayValue || (audit.score === 1 ? '[OK]' : '[X]')}</span>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
          {data.desktop?.opportunities && (
            <Card>
              <CardHeader><CardTitle>Opportunities (Desktop)</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  {Object.entries(data.desktop.opportunities).map(([key, audit]: [string, any]) => 
                    audit?.title && (
                      <div key={key} className="flex justify-between border-b pb-2">
                        <span>{audit.title}</span>
                        <span className="font-semibold">{audit.displayValue || (audit.score === 1 ? '[OK]' : '[X]')}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}


      {data.mobile?.diagnostics && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Diagnostics (Mobile)</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {Object.entries(data.mobile.diagnostics).map(([key, audit]: [string, any]) => 
                  audit?.displayValue && (
                    <div key={key} className="flex justify-between border-b pb-2">
                      <span>{audit.title || key.replace(/_/g, ' ')}</span>
                      <span className="font-semibold">{audit.displayValue}</span>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
          {data.desktop?.diagnostics && (
            <Card>
              <CardHeader><CardTitle>Diagnostics (Desktop)</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  {Object.entries(data.desktop.diagnostics).map(([key, audit]: [string, any]) => 
                    audit?.displayValue && (
                      <div key={key} className="flex justify-between border-b pb-2">
                        <span>{audit.title || key.replace(/_/g, ' ')}</span>
                        <span className="font-semibold">{audit.displayValue}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {data.mobile?.accessibility && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Accessibility (Mobile: {data.mobile.accessibility.score})</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {Object.entries(data.mobile.accessibility).filter(([k]) => k !== 'score').map(([key, audit]: [string, any]) => 
                  audit?.title && (
                    <div key={key} className="flex justify-between border-b pb-2">
                      <span>{audit.title}</span>
                      <span className="font-semibold">{audit.displayValue || (audit.score === 1 ? '[OK]' : '[X]')}</span>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
          {data.desktop?.accessibility && (
            <Card>
              <CardHeader><CardTitle>Accessibility (Desktop: {data.desktop.accessibility.score})</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  {Object.entries(data.desktop.accessibility).filter(([k]) => k !== 'score').map(([key, audit]: [string, any]) => 
                    audit?.title && (
                      <div key={key} className="flex justify-between border-b pb-2">
                        <span>{audit.title}</span>
                        <span className="font-semibold">{audit.displayValue || (audit.score === 1 ? '[OK]' : '[X]')}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {data.mobile?.seo && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>SEO (Mobile: {data.mobile.seo.score})</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {Object.entries(data.mobile.seo).filter(([k]) => k !== 'score').map(([key, audit]: [string, any]) => 
                  audit?.title && (
                    <div key={key} className="flex justify-between border-b pb-2">
                      <span>{audit.title}</span>
                      <span className="font-semibold">{audit.displayValue || (audit.score === 1 ? '[OK]' : '[X]')}</span>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
          {data.desktop?.seo && (
            <Card>
              <CardHeader><CardTitle>SEO (Desktop: {data.desktop.seo.score})</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  {Object.entries(data.desktop.seo).filter(([k]) => k !== 'score').map(([key, audit]: [string, any]) => 
                    audit?.title && (
                      <div key={key} className="flex justify-between border-b pb-2">
                        <span>{audit.title}</span>
                        <span className="font-semibold">{audit.displayValue || (audit.score === 1 ? '[OK]' : '[X]')}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
