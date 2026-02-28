"use client";

import { useState } from "react";
import { BarChart3, Users, AlertCircle, Play, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface CompetitorData {
  name: string;
  citations: number;
  citation_rate: number;
  top_queries: string[];
  strengths: string[];
  weaknesses: string[];
}

interface AnalysisResult {
  your_citations: number;
  your_citation_rate: number;
  competitors: CompetitorData[];
  gaps: string[];
  opportunities: string[];
}

interface CompetitorAnalysisProps {
  auditId: number;
  backendUrl: string;
}

export default function CompetitorAnalysis({
  auditId,
  backendUrl,
}: CompetitorAnalysisProps) {
  const [competitors, setCompetitors] = useState<string[]>([""]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const addCompetitor = () => {
    setCompetitors([...competitors, ""]);
  };

  const updateCompetitor = (idx: number, value: string) => {
    const newCompetitors = [...competitors];
    newCompetitors[idx] = value;
    setCompetitors(newCompetitors);
  };

  const removeCompetitor = (idx: number) => {
    if (competitors.length > 1) {
      setCompetitors(competitors.filter((_, i) => i !== idx));
    }
  };

  const runAnalysis = async () => {
    const validCompetitors = competitors.filter((c) => c.trim());
    if (validCompetitors.length === 0) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/geo/competitor-analysis`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audit_id: auditId,
            competitors: validCompetitors,
          }),
        },
      );

      if (!res.ok) throw new Error("Failed to run analysis");
      const data = await res.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
          <Users className="w-5 h-5" />
          Competitor URLs or Names
        </h3>

        <div className="space-y-3 mb-4">
          {competitors.map((comp, idx) => (
            <div key={idx} className="flex gap-2">
              <Input
                placeholder={`Competitor ${idx + 1} (URL or name)`}
                value={comp}
                onChange={(e) => updateCompetitor(idx, e.target.value)}
                className="flex-1 bg-muted/30 border-border/70 text-foreground placeholder:text-muted-foreground"
              />
              {competitors.length > 1 && (
                <Button
                  variant="ghost"
                  onClick={() => removeCompetitor(idx)}
                  className="text-red-400 hover:text-red-300"
                >
                  Remove
                </Button>
              )}
            </div>
          ))}
        </div>

        <div className="flex gap-4">
          <Button
            variant="outline"
            onClick={addCompetitor}
            className="border-border/70 text-foreground"
          >
            Add Competitor
          </Button>
          <Button
            onClick={runAnalysis}
            disabled={
              loading || competitors.filter((c) => c.trim()).length === 0
            }
            className="glass-button-primary"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-foreground"></div>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Run Analysis
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

      {results && (
        <div className="space-y-6">
          {/* Your Performance */}
          <div className="bg-muted/30 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground mb-4">
              Your Performance
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-muted-foreground text-sm">Total Citations</p>
                <p className="text-2xl font-bold text-foreground">
                  {results.your_citations}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground text-sm">Citation Rate</p>
                <p className="text-2xl font-bold text-foreground">
                  {results.your_citation_rate.toFixed(1)}%
                </p>
              </div>
            </div>
          </div>

          {/* Competitors */}
          {results.competitors.length > 0 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-foreground">
                Competitor Analysis
              </h3>
              {results.competitors.map((comp, idx) => (
                <div
                  key={idx}
                  className="bg-muted/30 border border-border rounded-xl p-6"
                >
                  <div className="flex justify-between items-start mb-4">
                    <h4 className="font-semibold text-foreground text-lg">
                      {comp.name}
                    </h4>
                    <div className="text-right">
                      <p className="text-2xl font-bold text-foreground">
                        {comp.citations}
                      </p>
                      <p className="text-muted-foreground text-sm">citations</p>
                    </div>
                  </div>

                  <div className="mb-4">
                    <p className="text-muted-foreground text-sm mb-2">
                      Citation Rate: {comp.citation_rate.toFixed(1)}%
                    </p>
                    <div className="w-full bg-muted/40 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full"
                        style={{
                          width: `${Math.min(comp.citation_rate, 100)}%`,
                        }}
                      ></div>
                    </div>
                  </div>

                  {comp.top_queries.length > 0 && (
                    <div className="mb-4">
                      <p className="text-muted-foreground text-sm mb-2">
                        Top Queries:
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {comp.top_queries.map((q, qidx) => (
                          <span
                            key={qidx}
                            className="bg-muted/40 text-muted-foreground px-2 py-1 rounded text-sm"
                          >
                            {q}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-green-400 text-sm mb-2">Strengths</p>
                      <ul className="space-y-1">
                        {comp.strengths.map((s, sidx) => (
                          <li
                            key={sidx}
                            className="text-muted-foreground text-sm"
                          >
                            • {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="text-red-400 text-sm mb-2">Weaknesses</p>
                      <ul className="space-y-1">
                        {comp.weaknesses.map((w, widx) => (
                          <li
                            key={widx}
                            className="text-muted-foreground text-sm"
                          >
                            • {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Gaps & Opportunities */}
          {(results.gaps.length > 0 || results.opportunities.length > 0) && (
            <div className="grid grid-cols-2 gap-6">
              {results.gaps.length > 0 && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6">
                  <h3 className="font-semibold text-red-400 mb-4">
                    Gaps to Address
                  </h3>
                  <ul className="space-y-2">
                    {results.gaps.map((gap, idx) => (
                      <li
                        key={idx}
                        className="text-muted-foreground text-sm flex items-start gap-2"
                      >
                        <span className="text-red-400">•</span> {gap}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {results.opportunities.length > 0 && (
                <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-6">
                  <h3 className="font-semibold text-green-400 mb-4">
                    Opportunities
                  </h3>
                  <ul className="space-y-2">
                    {results.opportunities.map((opp, idx) => (
                      <li
                        key={idx}
                        className="text-muted-foreground text-sm flex items-start gap-2"
                      >
                        <CheckCircle className="w-4 h-4 text-green-400 mt-0.5" />
                        {opp}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

