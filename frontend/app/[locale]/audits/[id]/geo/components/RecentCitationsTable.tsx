'use client';

import { useEffect, useState } from 'react';
import { TrendingUp, AlertCircle } from 'lucide-react';
import { fetchWithBackendAuth } from '@/lib/backend-auth';

interface Citation {
  id: number;
  query: string;
  response_preview: string;
  llm_name: string;
  citation_type: string;
  confidence: number;
  created_at: string;
}

interface RecentCitationsTableProps {
  auditId: number;
  backendUrl: string;
}

export default function RecentCitationsTable({ auditId, backendUrl }: RecentCitationsTableProps) {
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCitations = async () => {
      try {
        const res = await fetchWithBackendAuth(`${backendUrl}/api/geo/citations/${auditId}?limit=10`);
        if (!res.ok) throw new Error('Failed to fetch citations');
        const data = await res.json();
        setCitations(data.citations || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchCitations();
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
        <span>Error loading citations: {error}</span>
      </div>
    );
  }

  if (citations.length === 0) {
    return (
      <div className="text-center py-12 bg-muted/30 rounded-2xl border border-dashed border-border">
        <TrendingUp className="w-12 h-12 text-muted-foreground/60 mx-auto mb-4" />
        <p className="text-muted-foreground">No citations found yet. Start tracking to see results.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {citations.map((citation) => (
        <div key={citation.id} className="bg-muted/30 border border-border rounded-xl p-4">
          <div className="flex justify-between items-start mb-2">
            <h4 className="font-semibold text-foreground">{citation.query}</h4>
            <span className="text-xs text-muted-foreground bg-muted/40 px-2 py-1 rounded">
              {citation.llm_name}
            </span>
          </div>
          <p className="text-muted-foreground text-sm mb-3 line-clamp-2">{citation.response_preview}</p>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className={`px-2 py-1 rounded ${
              citation.citation_type === 'direct' ? 'bg-green-500/20 text-green-400' :
              citation.citation_type === 'indirect' ? 'bg-blue-500/20 text-blue-400' :
              'bg-yellow-500/20 text-yellow-400'
            }`}>
              {citation.citation_type}
            </span>
            <span>Confidence: {(citation.confidence * 100).toFixed(0)}%</span>
            <span>{new Date(citation.created_at).toLocaleDateString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
