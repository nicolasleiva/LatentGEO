"use client";

import { useEffect, useState } from "react";
import { Loader2, MapPin, Monitor, TrendingUp } from "lucide-react";

import { Header } from "@/components/header";
import { api } from "@/lib/api-client";
import { formatStableDateTime } from "@/lib/dates";
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
  initialDomain?: string;
  initialKeywords?: string;
  initialRankings?: RankTracking[];
};

type RankTopResult = {
  position?: number;
  domain?: string;
  title?: string;
  url?: string;
};

type RankTrackingWithTopResults = RankTracking & {
  top_results?: RankTopResult[];
};

const compareIsoDesc = (left?: string, right?: string) => {
  const leftTime = left ? Date.parse(left) : Number.NaN;
  const rightTime = right ? Date.parse(right) : Number.NaN;
  const normalizedLeft = Number.isFinite(leftTime) ? leftTime : Number.MIN_SAFE_INTEGER;
  const normalizedRight = Number.isFinite(rightTime)
    ? rightTime
    : Number.MIN_SAFE_INTEGER;
  return normalizedRight - normalizedLeft;
};

const sortTopResults = (results?: RankTopResult[]): RankTopResult[] => {
  if (!Array.isArray(results)) return [];
  return [...results].sort((left, right) => {
    const leftPosition =
      typeof left.position === "number" ? left.position : Number.MAX_SAFE_INTEGER;
    const rightPosition =
      typeof right.position === "number"
        ? right.position
        : Number.MAX_SAFE_INTEGER;
    return leftPosition - rightPosition;
  });
};

const normalizeRanking = (
  ranking: RankTracking,
): RankTrackingWithTopResults => {
  const candidate = ranking as RankTrackingWithTopResults;
  return {
    ...candidate,
    top_results: sortTopResults(candidate.top_results),
  };
};

const sortRankings = (
  items: RankTracking[],
): RankTrackingWithTopResults[] => {
  return items.map(normalizeRanking).sort((left, right) => {
    const trackedAtOrder = compareIsoDesc(left.tracked_at, right.tracked_at);
    if (trackedAtOrder !== 0) return trackedAtOrder;
    if (left.id !== right.id) return right.id - left.id;
    return left.keyword.localeCompare(right.keyword);
  });
};

export default function RankTrackingPageClient({
  auditId,
  initialDomain = "",
  initialKeywords = "",
  initialRankings = [],
}: RankTrackingPageClientProps) {
  const [form, setForm] = useState({
    domain: initialDomain,
    keywords: initialKeywords,
  });
  const [status, setStatus] = useState({ loading: false, error: "" });
  const [rankings, setRankings] = useState<RankTrackingWithTopResults[]>(() =>
    sortRankings(initialRankings),
  );
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;

    const loadInitialState = async () => {
      try {
        const [nextRankings, audit] = await Promise.all([
          api.getRankings(auditId),
          api.getAudit(auditId),
        ]);
        if (cancelled) return;

        const auditUrl = typeof audit?.url === "string" ? audit.url : "";
        let hostname = "";
        try {
          hostname = auditUrl ? new URL(auditUrl).hostname : "";
        } catch {
          hostname = "";
        }

        const suggestedKeywords: string[] = [];
        if (hostname) {
          suggestedKeywords.push(hostname.replace(/^www\./, "").split(".")[0]);
        }
        if (typeof audit?.category === "string" && audit.category.trim()) {
          suggestedKeywords.push(audit.category.toLowerCase());
        }
        const h1 = audit?.target_audit?.content?.h1;
        if (typeof h1 === "string" && h1.trim()) {
          suggestedKeywords.push(h1.toLowerCase());
        }

        setForm({
          domain: hostname,
          keywords: Array.from(new Set(suggestedKeywords)).slice(0, 5).join(", "),
        });
        setRankings(sortRankings(nextRankings));
      } catch {
        if (cancelled) return;
      }
    };

    void loadInitialState();

    return () => {
      cancelled = true;
    };
  }, [auditId]);

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
    const normalizedDomain = form.domain.trim();
    const keywordList = form.keywords
      .split(",")
      .map((keyword) => keyword.trim())
      .filter(Boolean);

    if (!normalizedDomain || keywordList.length === 0) {
      setStatus({
        loading: false,
        error: "Enter a domain and at least one keyword.",
      });
      return;
    }

    setStatus({ loading: true, error: "" });
    try {
      const newRankings = await api.trackRankings(
        auditId,
        normalizedDomain,
        keywordList,
      );
      setRankings((previous) => sortRankings([...newRankings, ...previous]));
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
                      {rank.top_results && rank.top_results.length > 0 ? (
                        <div className="space-y-1">
                          {(expandedRows.has(rank.id)
                            ? rank.top_results
                            : rank.top_results.slice(0, 3)
                          ).map((result) => (
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
                          {rank.top_results.length > 3 ? (
                            <Badge
                              variant="secondary"
                              className="cursor-pointer text-xs hover:bg-secondary/80"
                              onClick={() => toggleExpand(rank.id)}
                            >
                              {expandedRows.has(rank.id)
                                ? "Show less"
                                : `+${rank.top_results.length - 3} more`}
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
                      {formatStableDateTime(rank.tracked_at)}
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
