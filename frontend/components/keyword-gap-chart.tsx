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
    { name: 'Missing', value: gap_analysis.missing_keywords.length, fill: '#ef4444' }, // Red
    { name: 'Common', value: gap_analysis.common_keywords.length, fill: '#3b82f6' },  // Blue
    { name: 'Unique', value: gap_analysis.unique_keywords.length, fill: '#10b981' },  // Green
  ]

  return (
    <div className="grid gap-6 md:grid-cols-2 h-full">
      <div className="glass p-6 rounded-2xl flex flex-col">
        <h3 className="text-lg font-medium mb-6 text-white">Keyword Distribution</h3>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="rgba(255,255,255,0.5)"
                tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                stroke="rgba(255,255,255,0.5)"
                tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', borderColor: 'rgba(255,255,255,0.1)', color: '#fff', borderRadius: '12px', backdropFilter: 'blur(10px)' }}
                itemStyle={{ color: '#fff' }}
                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-6 text-center p-4 bg-white/5 rounded-xl border border-white/5">
          <div className="text-4xl font-bold text-white tracking-tight">{gap_analysis.gap_score.toFixed(1)}%</div>
          <div className="text-xs text-white/40 uppercase tracking-widest font-medium mt-1">Gap Score</div>
        </div>
      </div>

      <div className="glass p-6 rounded-2xl flex flex-col h-[500px] md:h-auto">
        <h3 className="text-lg font-medium mb-6 text-white">Top Opportunities</h3>
        <div className="space-y-2 flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
          {gap_analysis.opportunities.slice(0, 15).map((opp, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5 hover:bg-white/10 transition-colors group">
              <span className="font-medium text-white/80 group-hover:text-white transition-colors">{opp.keyword}</span>
              <Badge variant="secondary" className="bg-white/10 text-white/50 border-none group-hover:bg-white/20 group-hover:text-white transition-colors">{opp.competitor_frequency}</Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
