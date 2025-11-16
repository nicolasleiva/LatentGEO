"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { KeywordGapChart } from "@/components/keyword-gap-chart"
import { IssuesHeatmap } from "@/components/issues-heatmap"
import { Loader2 } from "lucide-react"

export default function ContentAnalysisPage() {
  const [yourUrl, setYourUrl] = useState("")
  const [compUrl, setCompUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [keywordData, setKeywordData] = useState<any>(null)

  const analyzeKeywords = async () => {
    if (!yourUrl || !compUrl) return
    setLoading(true)
    try {
      const res = await fetch(
        `http://localhost:8000/api/content/keywords/compare?your_url=${encodeURIComponent(yourUrl)}&competitor_url=${encodeURIComponent(compUrl)}`
      )
      const data = await res.json()
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
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-3xl font-bold">Content Analysis</h1>

      <Tabs defaultValue="keywords">
        <TabsList>
          <TabsTrigger value="keywords">Keyword Gap</TabsTrigger>
          <TabsTrigger value="heatmap">Issues Heatmap</TabsTrigger>
          <TabsTrigger value="duplicates">Duplicate Content</TabsTrigger>
        </TabsList>

        <TabsContent value="keywords" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Compare Keywords</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Input
                placeholder="Your URL: https://example.com"
                value={yourUrl}
                onChange={(e) => setYourUrl(e.target.value)}
              />
              <Input
                placeholder="Competitor URL: https://competitor.com"
                value={compUrl}
                onChange={(e) => setCompUrl(e.target.value)}
              />
              <Button onClick={analyzeKeywords} disabled={loading}>
                {loading ? <Loader2 className="animate-spin" /> : "Analyze Gap"}
              </Button>
            </CardContent>
          </Card>

          {keywordData && <KeywordGapChart data={keywordData} />}
        </TabsContent>

        <TabsContent value="heatmap">
          <IssuesHeatmap data={heatmapData} />
        </TabsContent>

        <TabsContent value="duplicates">
          <Card>
            <CardHeader>
              <CardTitle>Duplicate Content Detection</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Analiza contenido duplicado interno y externo usando TF-IDF y difflib.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
