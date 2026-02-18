"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { RankTracking } from "@/lib/types";
import { Header } from "@/components/header";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, TrendingUp, MapPin, Monitor } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function RankTrackingPage() {
  const params = useParams();
  const auditId = params.id as string;

  const [domain, setDomain] = useState("");
  const [keywords, setKeywords] = useState("");
  const [loading, setLoading] = useState(false);
  const [rankings, setRankings] = useState<RankTracking[]>([]);
  const [error, setError] = useState("");
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleExpand = (rankId: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(rankId)) {
      newExpanded.delete(rankId);
    } else {
      newExpanded.add(rankId);
    }
    setExpandedRows(newExpanded);
  };

  const loadData = useCallback(async () => {
    try {
      const data = await api.getRankings(auditId);
      setRankings(data);
      try {
        const audit = await api.getAudit(auditId);
        if (audit.url) {
          const url = new URL(audit.url);
          setDomain(url.hostname);

          // Extract core keywords from audit analysis
          const suggestedKeywords: string[] = [];

          // 1. Brand name
          const brandName = url.hostname.replace("www.", "").split(".")[0];
          suggestedKeywords.push(brandName);

          // 2. Category (e.g., "AI Coding Assistant")
          if ((audit as any).category) {
            suggestedKeywords.push((audit as any).category.toLowerCase());
          }

          // 3. Extract from target_audit content if available
          if ((audit as any).target_audit?.content?.h1) {
            suggestedKeywords.push(
              (audit as any).target_audit.content.h1.toLowerCase(),
            );
          }

          // Remove duplicates and take top 5
          const uniqueKeywords = [...new Set(suggestedKeywords)].slice(0, 5);
          setKeywords(uniqueKeywords.join(", "));
        }
      } catch {}
    } catch (e) {
      console.error(e);
    }
  }, [auditId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleTrack() {
    if (!domain || !keywords) return;

    setLoading(true);
    setError("");

    try {
      const keywordList = keywords
        .split(",")
        .map((k) => k.trim())
        .filter((k) => k);
      const newRankings = await api.trackRankings(auditId, domain, keywordList);
      setRankings((prev) => [...newRankings, ...prev]);
    } catch (e) {
      setError("Failed to track rankings. Ensure Google API keys are set.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-12 space-y-8">
        <div className="flex justify-between items-center animate-fade-up">
          <div>
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
              Rank Tracking
            </h1>
            <p className="text-muted-foreground mt-2">
              Check real-time positions on Google Search.
            </p>
          </div>
        </div>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle>Check Positions</CardTitle>
            <CardDescription>
              Live check using Google Custom Search API with auto-detected core
              keywords.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Domain</label>
                <Input
                  className="glass-input"
                  placeholder="example.com"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Core Keywords (from site analysis)
                </label>
                <Input
                  className="glass-input"
                  placeholder="e.g. brand name, main product"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Auto-detected from your site content. Edit as needed.
                </p>
              </div>
            </div>
            <Button
              onClick={handleTrack}
              disabled={loading}
              className="w-full md:w-auto glass-button-primary"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Tracking...
                </>
              ) : (
                <>
                  <TrendingUp className="mr-2 h-4 w-4" /> Check Rankings
                </>
              )}
            </Button>
            {error && <p className="text-red-500 text-sm">{error}</p>}
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle>Ranking History ({rankings.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Keyword</TableHead>
                  <TableHead>Your Position</TableHead>
                  <TableHead>Your URL</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Top 10 Competitors</TableHead>
                  <TableHead>Tracked At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rankings.map((rank) => (
                  <TableRow key={rank.id}>
                    <TableCell className="font-medium">
                      {rank.keyword}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-lg font-bold ${rank.position > 0 && rank.position <= 3 ? "text-foreground" : rank.position > 0 && rank.position <= 10 ? "text-muted-foreground" : "text-muted-foreground/50"}`}
                        >
                          {rank.position > 0
                            ? `#${rank.position}`
                            : "Not in Top 10"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground break-all">
                      {rank.url}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className="text-xs flex items-center gap-1"
                      >
                        <Monitor className="h-3 w-3" />
                        {rank.device || "unknown"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className="text-xs flex items-center gap-1"
                      >
                        <MapPin className="h-3 w-3" />
                        {rank.location || "global"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {(rank as any).top_results &&
                      (rank as any).top_results.length > 0 ? (
                        <div className="space-y-1">
                          {(expandedRows.has(rank.id)
                            ? (rank as any).top_results
                            : (rank as any).top_results.slice(0, 3)
                          ).map((result: any, idx: number) => (
                            <div
                              key={idx}
                              className="text-xs flex items-center gap-1"
                            >
                              <Badge variant="outline" className="text-xs">
                                #{result.position}
                              </Badge>
                              <span className="text-muted-foreground truncate max-w-[200px]">
                                {result.domain}
                              </span>
                            </div>
                          ))}
                          {(rank as any).top_results.length > 3 && (
                            <Badge
                              variant="secondary"
                              className="text-xs cursor-pointer hover:bg-secondary/80"
                              onClick={() => toggleExpand(rank.id)}
                            >
                              {expandedRows.has(rank.id)
                                ? "Show less"
                                : `+${(rank as any).top_results.length - 3} more`}
                            </Badge>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          No data
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(rank.tracked_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
                {rankings.length === 0 && !loading && (
                  <TableRow>
                    <TableCell
                      colSpan={7}
                      className="text-center py-8 text-muted-foreground"
                    >
                      No rankings tracked yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
