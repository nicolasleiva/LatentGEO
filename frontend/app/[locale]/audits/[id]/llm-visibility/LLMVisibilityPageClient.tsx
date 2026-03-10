"use client";

import { useState } from "react";
import { CheckCircle, Loader2, Search, XCircle } from "lucide-react";

import { Header } from "@/components/header";
import { api } from "@/lib/api-client";
import type { LLMVisibility } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

type LLMVisibilityPageClientProps = {
  auditId: string;
  initialResults: LLMVisibility[];
  initialBrandName: string;
};

export default function LLMVisibilityPageClient({
  auditId,
  initialResults,
  initialBrandName,
}: LLMVisibilityPageClientProps) {
  const [brandName, setBrandName] = useState(initialBrandName);
  const [queries, setQueries] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<LLMVisibility[]>(initialResults);
  const [error, setError] = useState("");

  async function handleCheck() {
    const normalizedBrandName = brandName.trim();
    const queryList = queries
      .split(",")
      .map((query) => query.trim())
      .filter(Boolean);

    if (!normalizedBrandName || queryList.length === 0) {
      setError("Enter a brand name and at least one query.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const newResults = await api.checkLLMVisibility(
        auditId,
        normalizedBrandName,
        queryList,
      );
      setResults((previous) => [...newResults, ...previous]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to check visibility. Ensure Kimi/NVIDIA key is set.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
              LLM Visibility Tracker
            </h1>
            <p className="mt-2 text-muted-foreground">
              Monitor your brand&apos;s presence across AI search results and
              model recommendations.
            </p>
          </div>
        </div>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="text-lg font-medium">
              Check Visibility
            </CardTitle>
            <CardDescription>
              Enter your brand name and queries to check if you are recommended
              by AI.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Brand Name</label>
                <Input
                  className="glass-input"
                  placeholder="e.g. Acme Corp"
                  value={brandName}
                  onChange={(event) => setBrandName(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Queries (comma separated)
                </label>
                <Input
                  className="glass-input"
                  placeholder="e.g. best seo tools, top marketing agencies"
                  value={queries}
                  onChange={(event) => setQueries(event.target.value)}
                />
              </div>
            </div>
            <Button
              onClick={handleCheck}
              disabled={loading}
              className="glass-button-primary w-full md:w-auto"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking AI Models...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Check Visibility
                </>
              )}
            </Button>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4">
          {results.map((result) => (
            <Card key={result.id} className="glass-card overflow-hidden">
              <div
                className={`h-1 w-full ${result.is_visible ? "bg-brand" : "bg-muted-foreground/30"}`}
              />
              <CardContent className="p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="mb-2 flex items-center gap-2">
                      <Badge variant="outline">{result.llm_name}</Badge>
                      <Badge
                        variant="outline"
                        className="text-muted-foreground"
                      >
                        #{result.id}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        {new Date(result.checked_at).toLocaleString()}
                      </span>
                    </div>
                    <h3 className="mb-1 text-lg font-semibold">
                      Query: &quot;{result.query}&quot;
                    </h3>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {result.is_visible ? (
                        <Badge
                          variant="outline"
                          className="border-brand bg-brand text-brand-foreground"
                        >
                          <CheckCircle className="mr-1 h-3 w-3" />
                          Visible
                        </Badge>
                      ) : (
                        <Badge
                          variant="outline"
                          className="border-border text-muted-foreground"
                        >
                          <XCircle className="mr-1 h-3 w-3" />
                          Not Visible
                        </Badge>
                      )}
                      {result.rank !== undefined && result.rank !== null ? (
                        <Badge variant="secondary">Rank #{result.rank}</Badge>
                      ) : null}
                    </div>
                  </div>
                </div>
                {result.citation_text ? (
                  <div className="glass-panel mt-4 rounded-lg border border-border p-4 text-sm italic text-foreground">
                    &quot;{result.citation_text}&quot;
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
          {results.length === 0 && !loading ? (
            <div className="py-12 text-center text-muted-foreground">
              No visibility checks performed yet.
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}
