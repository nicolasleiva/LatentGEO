"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"

interface KeywordGapProps {
  data: {
    your_keywords: Array<{ keyword: string; frequency: number }>
    competitor_keywords: Array<{ keyword: string; frequency: number }>
    gap_analysis: {
      missing_keywords: string[]
      unique_keywords: string[]
      common_keywords: string[]
      opportunities: Array<{ keyword: string; competitor_frequency: number }>
      gap_score: number
    }
  }
}

export function KeywordGapChart({ data }: KeywordGapProps) {
  const { gap_analysis } = data

  const chartData = [
    { name: 'Missing', value: gap_analysis.missing_keywords.length, fill: '#000000' },
    { name: 'Common', value: gap_analysis.common_keywords.length, fill: '#6b7280' },
    { name: 'Unique', value: gap_analysis.unique_keywords.length, fill: '#9ca3af' },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Keyword Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" />
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-4 text-center">
            <div className="text-3xl font-bold">{gap_analysis.gap_score.toFixed(1)}%</div>
            <div className="text-sm text-muted-foreground">Gap Score</div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top Opportunities</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {gap_analysis.opportunities.slice(0, 15).map((opp, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-muted rounded">
                <span className="font-medium">{opp.keyword}</span>
                <Badge variant="secondary">{opp.competitor_frequency}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
