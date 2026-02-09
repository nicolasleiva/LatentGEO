'use client';

import { useState } from 'react';
import { FileText, Copy, Check, Sparkles, AlertCircle, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

interface SchemaSuggestion {
  schema_type: string;
  reason: string;
  priority: 'high' | 'medium' | 'low';
  schema_json: string;
}

interface SchemaMultipleGeneratorProps {
  backendUrl: string;
}

export default function SchemaMultipleGenerator({ backendUrl }: SchemaMultipleGeneratorProps) {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SchemaSuggestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const generateSchemas = async () => {
    if (!url.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${backendUrl}/api/geo/schema-multiple`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });
      
      if (!res.ok) throw new Error('Failed to generate schemas');
      const data = await res.json();
      setResults(data.schemas || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (idx: number, json: string) => {
    navigator.clipboard.writeText(json);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'low': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      default: return 'bg-white/10 text-white/70';
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        <div className="space-y-4">
          <div>
            <Label className="text-white/70">Page URL</Label>
            <Input
              placeholder="https://example.com/page"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="mt-2 bg-white/5 border-white/20 text-white placeholder:text-white/40"
            />
          </div>
          
          <Button 
            onClick={generateSchemas} 
            disabled={loading || !url.trim()}
            className="glass-button-primary w-full"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            ) : (
              <>
                <List className="w-4 h-4 mr-2" />
                Generate Multiple Schemas
              </>
            )}
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 py-4">
          <AlertCircle className="w-5 h-5" />
          <span>Error: {error}</span>
        </div>
      )}

      {results && results.length === 0 && (
        <div className="text-center py-12 bg-white/5 rounded-2xl border border-dashed border-white/10">
          <FileText className="w-12 h-12 text-white/20 mx-auto mb-4" />
          <p className="text-white/40">No schema suggestions found for this page.</p>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="space-y-4">
          <p className="text-white/60">Found {results.length} schema recommendations:</p>
          
          {results.map((schema, idx) => (
            <div key={idx} className="bg-white/5 border border-white/10 rounded-xl p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h4 className="font-semibold text-white text-lg">{schema.schema_type}</h4>
                    <span className={`px-3 py-1 rounded-lg text-sm font-bold border ${getPriorityColor(schema.priority)}`}>
                      {schema.priority.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-white/60 text-sm">{schema.reason}</p>
                </div>
                <Button 
                  variant="outline" 
                  onClick={() => copyToClipboard(idx, schema.schema_json)}
                  className="border-white/20 text-white"
                >
                  {copiedIdx === idx ? (
                    <><Check className="w-4 h-4 mr-2" /> Copied!</>
                  ) : (
                    <><Copy className="w-4 h-4 mr-2" /> Copy</>
                  )}
                </Button>
              </div>
              
              <Textarea
                value={schema.schema_json}
                readOnly
                className="bg-black/30 border-white/10 text-green-400 font-mono text-sm min-h-[150px]"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
