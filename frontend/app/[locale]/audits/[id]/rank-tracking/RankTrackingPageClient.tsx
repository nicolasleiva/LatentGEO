"use client";

import { useState } from "react";
import { Loader2, MapPin, Monitor, TrendingUp } from "lucide-react";

import { Header } from "@/components/header";
import { api } from "@/lib/api-client";
import type { RankTracking } from "@/lib/types";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type RankTrackingPageClientProps = {
  auditId: string;
  initialDomain: string;
  initialKeywords: string;
  initialRankings: RankTracking[];
};

export default function RankTrackingPageClient({
  auditId,
  initialDomain,
  initialKeywords,
  initialRankings,
}: RankTrackingPageClientProps) {
  const [form, setForm] = useState({
    domain: initialDomain,
    keywords: initialKeywords,
  });
  const [status, setStatus] = useState({ loading: false, error: "" });
  const [rankings, setRankings] = useState<RankTracking[]>(initialRankings);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleExpand = (rankId: number) => {
    setExpandedRows((current) => {
      const next = new Set(current);
      if (next.has(rankId)) {
        next.delete(rankId);
      } else {
        next.add(rankId);
      }
      return next;
    });
  };

  async function handleTrack() {
    if (!form.domain || !form.keywords) return;

    setStatus({ loading: true, error: "" });
    try {
      const keywordList = form.keywords
        .split(",")
        .map((keyword) => keyword.trim())
        .filter(Boolean);
      const newRankings = await api.trackRankings(
        auditId,
        form.domain,
        keywordList,
      );
      setRankings((previous) => [...newRankings, ...previous]);
    } catch {
      setStatus({
        loading: false,
        error: "Failed to track rankings. Ensure Google API keys are set.",
      });
      return;
    } finally {
      setStatus((current) => ({ ...current, loading: false }));
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
              Rank Tracking
            </h1>
            <p className="mt-2 text-muted-foreground">
              Check real-time positions on Google Search.
            </p>
          </div>
        </div>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle>Check Positions</CardTitle>
            <CardDescription>
              Live check using Google Custom Search API with suggested core
              keywords.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label
                  htmlFor="rank-tracking-domain"
                  className="text-sm font-medium"
                >
                  Domain
                </label>
                <Input
                  id="rank-tracking-domain"
                  className="glass-input"
                  placeholder="example.com"
                  value={form.domain}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      domain: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="rank-tracking-keywords"
                  className="text-sm font-medium"
                >
                  Core Keywords
                </label>
                <Input
                  id="rank-tracking-keywords"
                  className="glass-input"
                  placeholder="e.g. brand name, main product"
                  value={form.keywords}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      keywords: event.target.value,
                    }))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Edit the detected keyword set before launching a fresh live
                  check.
                </p>
              </div>
            </div>
            <Button
              onClick={handleTrack}
              disabled={status.loading}
              className="glass-button-primary w-full md:w-auto"
            >
              {status.loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Tracking...
                </>
              ) : (
                <>
                  <TrendingUp className="mr-2 h-4 w-4" />
                  Check Rankings
                </>
              )}
            </Button>
            {status.error ? (
              <p className="text-sm text-red-500">{status.error}</p>
            ) : null}
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
                          className={`text-lg font-bold ${
                            rank.position > 0 && rank.position <= 3
                              ? "text-foreground"
                              : rank.position > 0 && rank.position <= 10
                                ? "text-muted-foreground"
                                : "text-muted-foreground/50"
                          }`}
                        >
                          {rank.position > 0
                            ? `#${rank.position}`
                            : "Not in Top 10"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="break-all text-sm text-muted-foreground">
                      {rank.url}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className="flex items-center gap-1 text-xs"
                      >
                        <Monitor className="h-3 w-3" />
                        {rank.device || "unknown"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className="flex items-center gap-1 text-xs"
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
                          ).map((result: any) => (
                            <div
                              key={
                                result.url ||
                                result.domain ||
                                result.title ||
                                JSON.stringify(result)
                              }
                              className="flex items-center gap-1 text-xs"
                            >
                              <Badge variant="outline" className="text-xs">
                                #{result.position}
                              </Badge>
                              <span className="truncate text-muted-foreground max-w-[200px]">
                                {result.domain}
                              </span>
                            </div>
                          ))}
                          {(rank as any).top_results.length > 3 ? (
                            <Badge
                              variant="secondary"
                              className="cursor-pointer text-xs hover:bg-secondary/80"
                              onClick={() => toggleExpand(rank.id)}
                            >
                              {expandedRows.has(rank.id)
                                ? "Show less"
                                : `+${(rank as any).top_results.length - 3} more`}
                            </Badge>
                          ) : null}
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
                {rankings.length === 0 && !status.loading ? (
                  <TableRow>
                    <TableCell
                      colSpan={7}
                      className="py-8 text-center text-muted-foreground"
                    >
                      No rankings tracked yet.
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
