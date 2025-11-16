"use client"

import { useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface Issue {
  url: string
  critical: number
  high: number
  medium: number
  low: number
}

interface HeatmapProps {
  data: Issue[]
}

export function IssuesHeatmap({ data }: HeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current || !data.length) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height
    const cellHeight = height / data.length
    const cellWidth = width / 4

    ctx.clearRect(0, 0, width, height)

    // Calcular máximo para normalizar
    const maxValue = Math.max(...data.flatMap(d => [d.critical, d.high, d.medium, d.low]))

    data.forEach((item, i) => {
      const values = [item.critical, item.high, item.medium, item.low]
      const colors = ['#000000', '#4b5563', '#9ca3af', '#d1d5db']

      values.forEach((value, j) => {
        const intensity = value / maxValue
        const x = j * cellWidth
        const y = i * cellHeight

        // Color con intensidad
        ctx.fillStyle = colors[j]
        ctx.globalAlpha = 0.2 + (intensity * 0.8)
        ctx.fillRect(x, y, cellWidth - 1, cellHeight - 1)

        // Texto
        ctx.globalAlpha = 1
        ctx.fillStyle = (j === 0 && intensity > 0.5) ? '#fff' : '#000'
        ctx.font = '12px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(value.toString(), x + cellWidth / 2, y + cellHeight / 2)
      })
    })

    // Labels
    ctx.fillStyle = '#000'
    ctx.font = 'bold 14px sans-serif'
    const labels = ['Critical', 'High', 'Medium', 'Low']
    labels.forEach((label, i) => {
      ctx.fillText(label, i * cellWidth + cellWidth / 2, height - 10)
    })

  }, [data])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Issues Heatmap</CardTitle>
      </CardHeader>
      <CardContent>
        <canvas ref={canvasRef} width={800} height={400} className="w-full" />
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          {data.slice(0, 5).map((item, i) => (
            <div key={i} className="truncate">
              <span className="font-mono text-xs">{item.url}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
