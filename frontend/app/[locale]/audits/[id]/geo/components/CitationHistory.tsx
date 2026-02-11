'use client';

import { useEffect, useState } from 'react';
import { History, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface HistoryData {
  month: string;
  year: number;
  citations: number;
  queries_tracked: number;
  citation_rate: number;
  top_queries: string[];
}

interface CitationHistoryProps {
  auditId: number;
  backendUrl: string;
}

export default function CitationHistory({ auditId, backendUrl }: CitationHistoryProps) {
  const [history, setHistory] = useState<HistoryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${backendUrl}/api/geo/citation-history/${auditId}`);
        if (!res.ok) throw new Error('Failed to fetch history');
        const data = await res.json();
        setHistory(data.history || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [auditId, backendUrl]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-red-400 py-4">
        <AlertCircle className="w-5 h-5" />
        <span>Error loading history: {error}</span>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="text-center py-12 bg-muted/30 rounded-2xl border border-dashed border-border">
        <History className="w-12 h-12 text-muted-foreground/60 mx-auto mb-4" />
        <p className="text-muted-foreground">No historical data available yet. Data will appear after tracking for multiple months.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {history.map((month, idx) => {
        const prevMonth = history[idx + 1];
        const trend = prevMonth ? month.citation_rate - prevMonth.citation_rate : 0;
        
        return (
          <div key={`${month.year}-${month.month}`} className="bg-muted/30 border border-border rounded-xl p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h4 className="font-semibold text-foreground text-lg">
                  {month.month} {month.year}
                </h4>
                <p className="text-muted-foreground text-sm">{month.queries_tracked} queries tracked</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-foreground">{month.citation_rate.toFixed(1)}%</span>
                {trend > 0 && <TrendingUp className="w-5 h-5 text-green-400" />}
                {trend < 0 && <TrendingDown className="w-5 h-5 text-red-400" />}
                {trend === 0 && <Minus className="w-5 h-5 text-muted-foreground" />}
              </div>
            </div>
            
            <div className="flex items-center gap-2 mb-4">
              <span className="text-muted-foreground">Citations:</span>
              <span className="font-semibold text-foreground">{month.citations}</span>
            </div>
            
            {month.top_queries.length > 0 && (
              <div>
                <p className="text-muted-foreground text-sm mb-2">Top performing queries:</p>
                <div className="flex flex-wrap gap-2">
                  {month.top_queries.map((query, qidx) => (
                    <span key={qidx} className="bg-muted/40 text-muted-foreground px-3 py-1 rounded-lg text-sm">
                      {query}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
