"use client"

import { useState } from "react"
import { api } from "@/lib/api"
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
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-3xl font-bold">Core Web Vitals & PageSpeed</h1>

      <Card>
        <CardHeader>
          <CardTitle>Analizar URL</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Input
            placeholder="https://example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && analyze()}
          />
          <Button onClick={analyze} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : "Analizar"}
          </Button>
        </CardContent>
      </Card>

      {data && <CoreWebVitalsChart data={data} />}
    </div>
  )
}
