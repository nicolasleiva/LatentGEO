"use client";

import { useState } from "react";
import {
  Award,
  AlertCircle,
  Sparkles,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { fetchWithBackendAuth } from "@/lib/backend-auth";

interface AnalysisResult {
  score: number;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  geo_readiness: string;
}

interface ContentAnalyzeProps {
  backendUrl: string;
}

export default function ContentAnalyze({ backendUrl }: ContentAnalyzeProps) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyzeContent = async () => {
    if (!content.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetchWithBackendAuth(
        `${backendUrl}/api/v1/geo/analyze-content`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        },
      );

      if (!res.ok) throw new Error("Failed to analyze content");
      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-green-400";
    if (score >= 60) return "text-yellow-400";
    return "text-red-400";
  };

  const getScoreBg = (score: number) => {
    if (score >= 80) return "bg-green-500/20";
    if (score >= 60) return "bg-yellow-500/20";
    return "bg-red-500/20";
  };

  return (
    <div className="space-y-6">
      <div className="bg-muted/30 border border-border rounded-xl p-6">
        <div className="space-y-4">
          <div>
            <Label className="text-muted-foreground">Content to Analyze</Label>
            <Textarea
              placeholder="Paste your content here to analyze GEO optimization..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="mt-2 min-h-[200px] bg-muted/30 border-border/70 text-foreground placeholder:text-muted-foreground"
            />
          </div>

          <Button
            onClick={analyzeContent}
            disabled={loading || !content.trim()}
            className="glass-button-primary w-full"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-foreground"></div>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Analyze Content
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

      {result && (
        <div className="space-y-6">
          {/* Score */}
          <div
            className={`${getScoreBg(result.score)} border border-border rounded-xl p-6 text-center`}
          >
            <p className="text-muted-foreground text-sm mb-2">
              GEO Readiness Score
            </p>
            <p className={`text-5xl font-bold ${getScoreColor(result.score)}`}>
              {result.score}/100
            </p>
            <p className="text-muted-foreground mt-2">{result.geo_readiness}</p>
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Strengths */}
            {result.strengths.length > 0 && (
              <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-6">
                <h4 className="font-semibold text-green-400 mb-4 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5" />
                  Strengths
                </h4>
                <ul className="space-y-2">
                  {result.strengths.map((strength) => (
                    <li
                      key={strength}
                      className="text-muted-foreground text-sm flex items-start gap-2"
                    >
                      <span className="text-green-400">•</span> {strength}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Weaknesses */}
            {result.weaknesses.length > 0 && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6">
                <h4 className="font-semibold text-red-400 mb-4 flex items-center gap-2">
                  <XCircle className="w-5 h-5" />
                  Gaps to Fix
                </h4>
                <ul className="space-y-2">
                  {result.weaknesses.map((weakness) => (
                    <li
                      key={weakness}
                      className="text-muted-foreground text-sm flex items-start gap-2"
                    >
                      <span className="text-red-400">•</span> {weakness}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-6">
              <h4 className="font-semibold text-blue-400 mb-4 flex items-center gap-2">
                <Award className="w-5 h-5" />
                Recommendations
              </h4>
              <ul className="space-y-2">
                {result.recommendations.map((rec) => (
                  <li
                    key={rec}
                    className="text-muted-foreground text-sm flex items-start gap-2"
                  >
                    <span className="text-blue-400">•</span> {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

