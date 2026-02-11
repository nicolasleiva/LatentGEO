"use client"

import { useState } from "react"
import { api } from "@/lib/api"
import { Header } from "@/components/header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CoreWebVitalsChart } from "@/components/core-web-vitals-chart"
import { Loader2 } from "lucide-react"

export default function PageSpeedPage() {
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any>(null)

  const analyze = async () => {
    if (!url) return
    setLoading(true)
    try {
      const result = await api.comparePageSpeed(url)
      setData(result)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="max-w-5xl mx-auto px-6 py-12 space-y-8">
        <div className="animate-fade-up">
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">Core Web Vitals & PageSpeed</h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Run a lab-based PageSpeed snapshot and validate performance signals that impact SEO and AI visibility.
          </p>
        </div>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle>Analyze a URL</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col md:flex-row gap-3">
            <Input
              className="glass-input"
              placeholder="https://example.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && analyze()}
            />
            <Button onClick={analyze} disabled={loading} className="glass-button-primary">
              {loading ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : null}
              {loading ? "Analyzing..." : "Analyze"}
            </Button>
          </CardContent>
        </Card>

        {data && <CoreWebVitalsChart data={data} />}
      </main>
    </div>
  )
}
