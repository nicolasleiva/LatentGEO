"use client";

import { useEffect, useRef } from "react";

interface Issue {
  url: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface HeatmapProps {
  data: Issue[];
}

export function IssuesHeatmap({ data }: HeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || !data.length) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const cellHeight = (height - 30) / data.length; // Reserve space for labels
    const cellWidth = width / 4;

    ctx.clearRect(0, 0, width, height);

    // Calcular máximo para normalizar
    const maxValue =
      Math.max(...data.flatMap((d) => [d.critical, d.high, d.medium, d.low])) ||
      1;

    data.forEach((item, i) => {
      const values = [item.critical, item.high, item.medium, item.low];
      // Red, Orange, Yellow, Blue
      const colors = ["#ef4444", "#f97316", "#eab308", "#3b82f6"];

      values.forEach((value, j) => {
        const intensity = value / maxValue;
        const x = j * cellWidth;
        const y = i * cellHeight;

        // Color con intensidad
        ctx.fillStyle = colors[j];
        ctx.globalAlpha = 0.1 + intensity * 0.9;

        // Rounded rect simulation (just fill for now)
        ctx.beginPath();
        ctx.roundRect(x + 2, y + 2, cellWidth - 4, cellHeight - 4, 8);
        ctx.fill();

        // Texto
        ctx.globalAlpha = 1;
        ctx.fillStyle = "#fff";
        ctx.font = "14px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        if (value > 0) {
          ctx.fillText(value.toString(), x + cellWidth / 2, y + cellHeight / 2);
        }
      });
    });

    // Labels
    ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
    ctx.font = "500 12px Inter, sans-serif";
    const labels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
    labels.forEach((label, i) => {
      ctx.fillText(label, i * cellWidth + cellWidth / 2, height - 10);
    });
  }, [data]);

  return (
    <div className="glass-card p-6 rounded-2xl">
      <h3 className="text-lg font-medium mb-6 text-foreground">
        Issues Heatmap
      </h3>
      <div className="relative w-full aspect-[2/1] bg-muted/20 rounded-xl overflow-hidden border border-border">
        <canvas
          ref={canvasRef}
          width={800}
          height={400}
          className="w-full h-full object-contain"
        />
      </div>
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-2">
        {data.slice(0, 6).map((item, i) => (
          <div
            key={i}
            className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors"
          >
            <span className="text-muted-foreground text-xs font-mono w-4 text-right">
              {i + 1}
            </span>
            <span
              className="font-mono text-xs text-foreground truncate"
              title={item.url}
            >
              {item.url}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
