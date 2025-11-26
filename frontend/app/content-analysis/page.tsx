"use client"

import { useState } from "react"
import { useRouter } from 'next/navigation'
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { KeywordGapChart } from "@/components/keyword-gap-chart"
import { IssuesHeatmap } from "@/components/issues-heatmap"
import { Loader2, ArrowLeft, BarChart2, Layers, Copy } from "lucide-react"

export default function ContentAnalysisPage() {
  const router = useRouter()
  const [yourUrl, setYourUrl] = useState("")
  const [compUrl, setCompUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [keywordData, setKeywordData] = useState<any>(null)

  const analyzeKeywords = async () => {
    if (!yourUrl || !compUrl) return
    setLoading(true)
    try {
      const data = await api.compareKeywords(yourUrl, compUrl)
      setKeywordData(data)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // Mock data para heatmap
  const heatmapData = [
    { url: "/page1", critical: 5, high: 12, medium: 8, low: 3 },
    { url: "/page2", critical: 2, high: 7, medium: 15, low: 5 },
    { url: "/page3", critical: 8, high: 10, medium: 6, low: 2 },
    { url: "/page4", critical: 1, high: 4, medium: 20, low: 10 },
    { url: "/page5", critical: 3, high: 9, medium: 12, low: 7 },
  ]

  return (
    <div className="min-h-screen text-white p-8">
      <nav className="flex items-center gap-4 mb-12 max-w-7xl mx-auto">
        <Button variant="ghost" onClick={() => router.push('/')} className="text-white/60 hover:text-white hover:bg-white/10 rounded-full px-4">
          <ArrowLeft className="h-4 w-4 mr-2" /> Back
        </Button>
        <div className="h-6 w-px bg-white/10"></div>
        <span className="text-white/40 text-sm">Content Intelligence</span>
      </nav>

      <main className="max-w-7xl mx-auto">
        <div className="glass-card p-8 md:p-10">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Content Analysis</h1>
            <p className="text-white/50">Deep dive into keyword gaps, content issues, and duplication.</p>
          </div>

          <Tabs defaultValue="keywords" className="space-y-8">
            <TabsList className="bg-white/5 border border-white/10 p-1 rounded-full backdrop-blur-md inline-flex">
              <TabsTrigger value="keywords" className="rounded-full px-6 data-[state=active]:bg-white data-[state=active]:text-black transition-all flex items-center gap-2">
                <BarChart2 className="w-4 h-4" /> Keyword Gap
              </TabsTrigger>
              <TabsTrigger value="heatmap" className="rounded-full px-6 data-[state=active]:bg-white data-[state=active]:text-black transition-all flex items-center gap-2">
                <Layers className="w-4 h-4" /> Issues Heatmap
              </TabsTrigger>
              <TabsTrigger value="duplicates" className="rounded-full px-6 data-[state=active]:bg-white data-[state=active]:text-black transition-all flex items-center gap-2">
                <Copy className="w-4 h-4" /> Duplicates
              </TabsTrigger>
            </TabsList>

            <TabsContent value="keywords" className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="glass p-6 rounded-2xl space-y-4 border border-white/10">
                <h3 className="text-lg font-medium">Compare Keywords</h3>
                <div className="flex flex-col md:flex-row gap-4">
                  <input
                    placeholder="Your URL (e.g. https://mysite.com)"
                    className="glass-input flex-1 px-4 py-3 rounded-xl outline-none"
                    value={yourUrl}
                    onChange={(e) => setYourUrl(e.target.value)}
                  />
                  <input
                    placeholder="Competitor URL (e.g. https://competitor.com)"
                    className="glass-input flex-1 px-4 py-3 rounded-xl outline-none"
                    value={compUrl}
                    onChange={(e) => setCompUrl(e.target.value)}
                  />
                  <Button onClick={analyzeKeywords} disabled={loading} className="glass-button-primary h-auto px-8">
                    {loading ? <Loader2 className="animate-spin" /> : "Analyze Gap"}
                  </Button>
                </div>
              </div>

              {keywordData && (
                <div className="glass p-6 rounded-2xl border border-white/10">
                  <KeywordGapChart data={keywordData} />
                </div>
              )}
            </TabsContent>

            <TabsContent value="heatmap" className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="glass p-6 rounded-2xl border border-white/10">
                <IssuesHeatmap data={heatmapData} />
              </div>
            </TabsContent>

            <TabsContent value="duplicates" className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="glass p-8 rounded-2xl border border-white/10 text-center py-20">
                <Copy className="w-12 h-12 mx-auto mb-4 text-white/20" />
                <h3 className="text-xl font-medium mb-2">Duplicate Content Detection</h3>
                <p className="text-white/50 max-w-md mx-auto">
                  Advanced TF-IDF and fuzzy matching analysis to detect internal and external content duplication.
                </p>
                <Button className="mt-6 glass-button" disabled>Coming Soon</Button>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  )
}
