"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Backlink } from "@/lib/types";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Loader2,
  Link as LinkIcon,
  ExternalLink,
  Network,
  Globe,
  ThumbsUp,
  ThumbsDown,
  Minus,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function BacklinksPage() {
  const params = useParams();
  const auditId = params.id as string;

  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);
  const [backlinks, setBacklinks] = useState<Backlink[]>([]);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    try {
      const data = await api.getBacklinks(auditId);
      setBacklinks(data);
      try {
        const audit = await api.getAudit(auditId);
        if (audit.url) {
          const url = new URL(audit.url);
          setDomain(url.hostname);
        }
      } catch {}
    } catch (e) {
      console.error(e);
    }
  }, [auditId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleAnalyze() {
    if (!domain) return;

    setLoading(true);
    setError("");

    try {
      await api.analyzeBacklinks(auditId, domain);
      const allBacklinks = await api.getBacklinks(auditId);
      setBacklinks(allBacklinks);
    } catch (e) {
      setError("Failed to analyze links.");
    } finally {
      setLoading(false);
    }
  }

  const internalLinks = backlinks.filter(
    (bl) => bl.source_url === "INTERNAL_NETWORK",
  );
  const technicalBacklinks = backlinks.filter(
    (bl) => bl.source_url === "TECHNICAL_BACKLINK",
  );
  const brandMentions = backlinks.filter(
    (bl) => bl.source_url === "BRAND_MENTION",
  );

  function parseMentionAnalysis(anchorText: string) {
    try {
      return JSON.parse(anchorText);
    } catch {
      return {
        sentiment: "neutral",
        topic: "Unknown",
        snippet: anchorText,
        recommendation: "N/A",
        relevance_score: 0,
      };
    }
  }

  function getSentimentIcon(sentiment: string) {
    if (sentiment === "positive")
      return <ThumbsUp className="h-4 w-4 text-foreground" />;
    if (sentiment === "negative")
      return <ThumbsDown className="h-4 w-4 text-muted-foreground" />;
    return <Minus className="h-4 w-4 text-muted-foreground/50" />;
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-12 space-y-8">
        <div className="flex justify-between items-center animate-fade-up">
          <div>
            <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">
              Link & Mention Analysis
            </h1>
            <p className="text-muted-foreground mt-2">
              Internal structure, technical backlinks, and AI-powered brand
              analysis.
            </p>
          </div>
        </div>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle>Start Analysis</CardTitle>
            <CardDescription>
              Comprehensive analysis of all link types and brand mentions.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col md:flex-row gap-4">
              <Input
                className="glass-input max-w-md"
                placeholder="example.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
              />
              <Button
                onClick={handleAnalyze}
                disabled={loading}
                className="glass-button-primary"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />{" "}
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Network className="mr-2 h-4 w-4" /> Analyze All
                  </>
                )}
              </Button>
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="glass-card p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
              Total
            </div>
            <div className="text-2xl font-semibold">{backlinks.length}</div>
          </Card>
          <Card className="glass-card p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
              Internal
            </div>
            <div className="text-2xl font-semibold">{internalLinks.length}</div>
          </Card>
          <Card className="glass-card p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
              Technical
            </div>
            <div className="text-2xl font-semibold">
              {technicalBacklinks.length}
            </div>
          </Card>
          <Card className="glass-card p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
              Mentions
            </div>
            <div className="text-2xl font-semibold">{brandMentions.length}</div>
          </Card>
        </div>

        <Tabs defaultValue="internal" className="w-full">
          <TabsList>
            <TabsTrigger value="internal">
              Internal Structure ({internalLinks.length})
            </TabsTrigger>
            <TabsTrigger value="technical">
              Technical Backlinks ({technicalBacklinks.length})
            </TabsTrigger>
            <TabsTrigger value="mentions">
              Brand Mentions ({brandMentions.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="internal">
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Top Internal Pages</CardTitle>
                <CardDescription>
                  Pages with the most internal incoming links.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Target Page</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Link Count</TableHead>
                      <TableHead>Follow</TableHead>
                      <TableHead>DA</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {internalLinks.map((bl) => (
                      <TableRow key={bl.id}>
                        <TableCell className="font-medium break-all">
                          {bl.target_url}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">Internal Network</Badge>
                        </TableCell>
                        <TableCell>{bl.anchor_text}</TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              bl.is_dofollow
                                ? "text-emerald-600 border-emerald-500/30"
                                : ""
                            }
                          >
                            {bl.is_dofollow ? "Dofollow" : "Nofollow"}
                          </Badge>
                        </TableCell>
                        <TableCell>{bl.domain_authority ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                    {internalLinks.length === 0 && !loading && (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="text-center py-8 text-muted-foreground"
                        >
                          No internal link data found.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="technical">
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Technical Backlinks</CardTitle>
                <CardDescription>
                  External pages linking to your domain (link: operator).
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source Page</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead>Platform</TableHead>
                      <TableHead>Follow</TableHead>
                      <TableHead>DA</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {technicalBacklinks.map((bl) => (
                      <TableRow key={bl.id}>
                        <TableCell className="font-medium break-all">
                          <a
                            href={bl.target_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center hover:underline text-brand"
                          >
                            {bl.target_url}{" "}
                            <ExternalLink className="ml-1 h-3 w-3" />
                          </a>
                        </TableCell>
                        <TableCell>{bl.anchor_text}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {new URL(bl.target_url).hostname}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              bl.is_dofollow
                                ? "text-emerald-600 border-emerald-500/30"
                                : ""
                            }
                          >
                            {bl.is_dofollow ? "Dofollow" : "Nofollow"}
                          </Badge>
                        </TableCell>
                        <TableCell>{bl.domain_authority ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                    {technicalBacklinks.length === 0 && !loading && (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="text-center py-8 text-muted-foreground"
                        >
                          No technical backlinks found.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="mentions">
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Brand Mentions (GEO Analysis)</CardTitle>
                <CardDescription>
                  AI-powered analysis of brand citations with sentiment and
                  context.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {brandMentions.map((bl) => {
                    const analysis = parseMentionAnalysis(bl.anchor_text);
                    return (
                      <div
                        key={bl.id}
                        className="border border-border rounded-lg p-4 space-y-2 glass-panel"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <a
                              href={bl.target_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-brand hover:underline font-medium flex items-center"
                            >
                              {new URL(bl.target_url).hostname}{" "}
                              <ExternalLink className="ml-1 h-3 w-3" />
                            </a>
                            <p className="text-sm text-muted-foreground mt-1">
                              {bl.target_url}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {getSentimentIcon(analysis.sentiment)}
                            <Badge
                              variant={
                                analysis.sentiment === "positive"
                                  ? "default"
                                  : analysis.sentiment === "negative"
                                    ? "destructive"
                                    : "secondary"
                              }
                            >
                              {analysis.sentiment}
                            </Badge>
                          </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-muted-foreground">
                          <div>
                            <span className="font-semibold text-foreground">
                              Topic:
                            </span>{" "}
                            {analysis.topic}
                          </div>
                          <div>
                            <span className="font-semibold text-foreground">
                              Relevance:
                            </span>{" "}
                            {analysis.relevance_score}/100
                          </div>
                          <div>
                            <span className="font-semibold text-foreground">
                              Follow:
                            </span>{" "}
                            {bl.is_dofollow ? "Dofollow" : "Nofollow"}
                          </div>
                        </div>
                        <div className="bg-muted/50 p-3 rounded border border-border">
                          <p className="text-sm">
                            <span className="font-semibold text-foreground">
                              Context:
                            </span>{" "}
                            {analysis.snippet}
                          </p>
                        </div>
                        <div className="bg-brand/10 p-3 rounded border-l-4 border-brand">
                          <p className="text-sm">
                            <span className="font-semibold text-foreground">
                              Recommendation:
                            </span>{" "}
                            {analysis.recommendation}
                          </p>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          ID: #{bl.id} · DA: {bl.domain_authority ?? "—"}
                        </div>
                      </div>
                    );
                  })}
                  {brandMentions.length === 0 && !loading && (
                    <div className="text-center py-8 text-muted-foreground">
                      No brand mentions found. Run the analysis to discover
                      citations.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
