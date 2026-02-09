'use client';

import { useState } from 'react';
import { Search, Sparkles, AlertCircle, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface QueryOpportunity {
  query: string;
  intent: string;
  potential_score: number;
  volume_estimate: string;
  competition_level: string;
  recommendation: string;
}

interface QueryDiscoveryProps {
  auditId: number;
  backendUrl: string;
}

export default function QueryDiscovery({ auditId, backendUrl }: QueryDiscoveryProps) {
  const [seedQuery, setSeedQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<QueryOpportunity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const discoverQueries = async () => {
    if (!seedQuery.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${backendUrl}/api/geo/query-discovery`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audit_id: auditId,
          seed_query: seedQuery,
        }),
      });
      
      if (!res.ok) throw new Error('Failed to discover queries');
      const data = await res.json();
      setResults(data.opportunities || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-4">
        <Input
          placeholder="Enter a seed query (e.g., 'best software for...')"
          value={seedQuery}
          onChange={(e) => setSeedQuery(e.target.value)}
          className="flex-1 bg-white/5 border-white/20 text-white placeholder:text-white/40"
        />
        <Button 
          onClick={discoverQueries} 
          disabled={loading || !seedQuery.trim()}
          className="glass-button-primary"
        >
          {loading ? (
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
          ) : (
            <>
              <Sparkles className="w-4 h-4 mr-2" />
              Discover
            </>
          )}
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 py-4">
          <AlertCircle className="w-5 h-5" />
          <span>Error: {error}</span>
        </div>
      )}

      {results && results.length === 0 && (
        <div className="text-center py-12 bg-white/5 rounded-2xl border border-dashed border-white/10">
          <Search className="w-12 h-12 text-white/20 mx-auto mb-4" />
          <p className="text-white/40">No opportunities found. Try a different seed query.</p>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="space-y-4">
          <p className="text-white/60 mb-4">Found {results.length} opportunities:</p>
          {results.map((opp, idx) => (
            <div key={idx} className="bg-white/5 border border-white/10 rounded-xl p-6">
              <div className="flex justify-between items-start mb-3">
                <h4 className="font-semibold text-white text-lg">{opp.query}</h4>
                <div className="flex items-center gap-2">
                  <span className="bg-blue-500/20 text-blue-300 px-3 py-1 rounded-lg text-sm font-bold">
                    Score: {opp.potential_score}
                  </span>
                  <span className="bg-white/10 text-white/70 px-3 py-1 rounded-lg text-sm capitalize">
                    {opp.intent}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
                <div>
                  <span className="text-white/50">Volume:</span>
                  <span className="text-white ml-2">{opp.volume_estimate}</span>
                </div>
                <div>
                  <span className="text-white/50">Competition:</span>
                  <span className="text-white ml-2 capitalize">{opp.competition_level}</span>
                </div>
              </div>
              
              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <CheckCircle className="w-4 h-4 text-green-400 mt-0.5" />
                  <p className="text-green-300 text-sm">{opp.recommendation}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
