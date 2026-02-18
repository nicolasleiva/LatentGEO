"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  CheckCircle,
  XCircle,
  Wand2,
  ArrowLeft,
  AlertCircle,
} from "lucide-react";

interface AnalysisResult {
  score: number;
  summary: string;
  pillars: {
    direct_answer: { score: number; feedback: string };
    structure: { score: number; feedback: string };
    authority: { score: number; feedback: string };
    semantics: { score: number; feedback: string };
  };
  suggestions: { type: "critical" | "improvement" | "info"; text: string }[];
  missing_entities: string[];
}

export default function ContentEditorPage() {
  const router = useRouter();
  const [content, setContent] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);

  const handleAnalyze = async () => {
    if (!content || !keyword) return;

    setLoading(true);
    try {
      const data = await api.analyzeContent(content, keyword);
      setAnalysis(data);
    } catch (error) {
      console.error("Analysis failed:", error);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-green-500";
    if (score >= 50) return "text-yellow-500";
    return "text-red-500";
  };

  return (
    <div className="h-screen flex flex-col text-foreground">
      {/* Header */}
      <div className="h-16 border-b border-border flex items-center justify-between px-6 glass-card z-10 shrink-0">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.push("/")}>
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>
          <div className="h-6 w-px bg-border" />
          <h1 className="font-semibold text-lg tracking-tight">
            GEO Content Editor
          </h1>
          <div className="h-6 w-px bg-border" />
          <input
            placeholder="Target Keyword (e.g. 'best crm')"
            className="glass-input px-4 py-1.5 rounded-lg w-80 text-sm outline-none"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-4">
          {analysis && (
            <div className="flex items-center gap-2 px-4 py-1.5 glass-panel rounded-lg border border-border">
              <span className="text-sm text-muted-foreground">GEO Score:</span>
              <span
                className={`text-xl font-bold ${getScoreColor(analysis.score)}`}
              >
                {analysis.score}
              </span>
            </div>
          )}
          <Button
            onClick={handleAnalyze}
            disabled={loading || !content || !keyword}
          >
            {loading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Wand2 className="mr-2 h-4 w-4" />
            )}
            Analyze Content
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden p-6 gap-6">
        {/* Editor Area (Left) */}
        <div className="flex-1 glass-card p-0 overflow-hidden flex flex-col relative group">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand/40 to-foreground/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <textarea
            placeholder="Start writing your content here... Focus on direct answers and clear structure."
            className="w-full h-full bg-transparent p-8 text-lg leading-relaxed resize-none border-none focus:ring-0 text-foreground placeholder:text-muted-foreground outline-none scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </div>

        {/* Analysis Panel (Right) */}
        <div className="w-96 glass-card overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
          {!analysis ? (
            <div className="text-center text-muted-foreground py-20 flex flex-col items-center">
              <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-6">
                <Wand2 className="h-8 w-8 opacity-50" />
              </div>
              <p className="text-lg font-medium mb-2">Ready to Optimize</p>
              <p className="text-sm max-w-[200px]">
                Enter a keyword and content to get real-time GEO analysis.
              </p>
            </div>
          ) : (
            <>
              {/* Summary */}
              <div className="p-4 glass-panel rounded-xl border border-border">
                <p className="text-sm italic text-foreground leading-relaxed">
                  &ldquo;{analysis.summary}&rdquo;
                </p>
              </div>

              {/* Pillars */}
              <div className="space-y-5">
                <h3 className="font-medium text-xs uppercase tracking-widest text-muted-foreground">
                  GEO Pillars
                </h3>

                {Object.entries(analysis.pillars).map(
                  ([key, data]: [string, any]) => (
                    <div key={key} className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="capitalize text-foreground">
                          {key.replace("_", " ")}
                        </span>
                        <span
                          className={
                            data.score >= 7
                              ? "text-green-500"
                              : "text-yellow-500"
                          }
                        >
                          {data.score}/10
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-1000 ${data.score >= 7 ? "bg-green-500" : "bg-yellow-500"}`}
                          style={{ width: `${data.score * 10}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {data.feedback}
                      </p>
                    </div>
                  ),
                )}
              </div>

              {/* Suggestions */}
              <div className="space-y-4">
                <h3 className="font-medium text-xs uppercase tracking-widest text-muted-foreground">
                  Action Items
                </h3>
                {analysis.suggestions.map((s, idx) => (
                  <div
                    key={idx}
                    className="flex gap-3 items-start p-3 rounded-xl glass-panel border border-border hover:bg-muted/50 transition-colors"
                  >
                    {s.type === "critical" ? (
                      <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                    ) : (
                      <CheckCircle className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                    )}
                    <p className="text-xs leading-relaxed text-foreground">
                      {s.text}
                    </p>
                  </div>
                ))}
              </div>

              {/* Missing Entities */}
              {analysis.missing_entities.length > 0 && (
                <div className="space-y-3">
                  <h3 className="font-medium text-xs uppercase tracking-widest text-muted-foreground">
                    Missing Entities
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {analysis.missing_entities.map((entity, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {entity}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
