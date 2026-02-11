"use client"

import { Badge } from "@/components/ui/badge"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"

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
    { name: 'Missing', value: gap_analysis.missing_keywords.length, fill: '#ef4444' },
    { name: 'Common', value: gap_analysis.common_keywords.length, fill: '#0f766e' },
    { name: 'Unique', value: gap_analysis.unique_keywords.length, fill: '#14b8a6' },
  ]

  return (
    <div className="grid gap-6 md:grid-cols-2 h-full">
      <div className="glass-card p-6 rounded-2xl flex flex-col">
        <h3 className="text-lg font-medium mb-6 text-foreground">Keyword Distribution</h3>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))', borderRadius: '12px', backdropFilter: 'blur(10px)' }}
                itemStyle={{ color: 'hsl(var(--foreground))' }}
                cursor={{ fill: 'hsl(var(--accent))' }}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-6 text-center p-4 glass-panel rounded-xl border border-border">
          <div className="text-4xl font-bold text-foreground tracking-tight">{gap_analysis.gap_score.toFixed(1)}%</div>
          <div className="text-xs text-muted-foreground uppercase tracking-widest font-medium mt-1">Gap Score</div>
        </div>
      </div>

      <div className="glass-card p-6 rounded-2xl flex flex-col h-[500px] md:h-auto">
        <h3 className="text-lg font-medium mb-6 text-foreground">Top Opportunities</h3>
        <div className="space-y-2 flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
          {gap_analysis.opportunities.slice(0, 15).map((opp, i) => (
            <div key={i} className="flex items-center justify-between p-3 glass-panel rounded-xl border border-border hover:bg-muted/50 transition-colors group">
              <span className="font-medium text-foreground/80 group-hover:text-foreground transition-colors">{opp.keyword}</span>
              <Badge variant="secondary" className="bg-muted text-muted-foreground border-none group-hover:bg-muted/80 group-hover:text-foreground transition-colors">{opp.competitor_frequency}</Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
