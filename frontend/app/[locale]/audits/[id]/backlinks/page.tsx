import {
  ExternalLink,
  Globe,
  Link as LinkIcon,
  Minus,
  Network,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";

import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { requireServerViewer, serverJson } from "@/lib/server-api";
import type { Backlink } from "@/lib/types";

import BacklinksAnalyzeForm from "./BacklinksAnalyzeForm";

type MentionAnalysis = {
  sentiment: string;
  topic: string;
  snippet: string;
  recommendation: string;
  relevance_score: number;
};

function parseMentionAnalysis(anchorText: string): MentionAnalysis {
  try {
    const parsed = JSON.parse(anchorText) as Record<string, unknown> | null;
    if (!parsed || Array.isArray(parsed)) {
      throw new Error("Invalid mention analysis payload");
    }

    const relevanceScore =
      typeof parsed.relevance_score === "number" &&
      Number.isFinite(parsed.relevance_score)
        ? Math.min(Math.max(parsed.relevance_score, 0), 100)
        : 0;

    return {
      sentiment:
        typeof parsed.sentiment === "string" ? parsed.sentiment : "neutral",
      topic: typeof parsed.topic === "string" ? parsed.topic : "Unknown",
      snippet: typeof parsed.snippet === "string" ? parsed.snippet : anchorText,
      recommendation:
        typeof parsed.recommendation === "string"
          ? parsed.recommendation
          : "N/A",
      relevance_score: relevanceScore,
    };
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
  if (sentiment === "positive") {
    return <ThumbsUp className="h-4 w-4 text-foreground" />;
  }
  if (sentiment === "negative") {
    return <ThumbsDown className="h-4 w-4 text-muted-foreground" />;
  }
  return <Minus className="h-4 w-4 text-muted-foreground/50" />;
}

function resolveDomain(url: string | null | undefined) {
  if (!url) return "";
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

export default async function BacklinksPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id: auditId } = await params;
  await requireServerViewer(`/${locale}/audits/${auditId}/backlinks`);

  const [backlinks, audit] = await Promise.all([
    serverJson<Backlink[]>(`/api/v1/backlinks/${auditId}`).catch(() => []),
    serverJson<{ url?: string }>(`/api/v1/audits/${auditId}`).catch(() => ({})),
  ]);

  const auditUrl =
    "url" in audit && typeof audit.url === "string" ? audit.url : "";
  const domain = resolveDomain(auditUrl);
  const internalLinks = backlinks.filter(
    (backlink) => backlink.source_url === "INTERNAL_NETWORK",
  );
  const technicalBacklinks = backlinks.filter(
    (backlink) => backlink.source_url === "TECHNICAL_BACKLINK",
  );
  const brandMentions = backlinks.filter(
    (backlink) => backlink.source_url === "BRAND_MENTION",
  );

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Link & Mention Analysis
            </h1>
            <p className="mt-2 text-muted-foreground">
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
          <CardContent>
            <BacklinksAnalyzeForm auditId={auditId} initialDomain={domain} />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Card className="glass-card p-5">
            <div className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
              Total
            </div>
            <div className="text-2xl font-semibold">{backlinks.length}</div>
          </Card>
          <Card className="glass-card p-5">
            <div className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
              Internal
            </div>
            <div className="text-2xl font-semibold">{internalLinks.length}</div>
          </Card>
          <Card className="glass-card p-5">
            <div className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
              Technical
            </div>
            <div className="text-2xl font-semibold">
              {technicalBacklinks.length}
            </div>
          </Card>
          <Card className="glass-card p-5">
            <div className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
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
                    {internalLinks.map((backlink) => (
                      <TableRow key={backlink.id}>
                        <TableCell className="break-all font-medium">
                          {backlink.target_url}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">Internal Network</Badge>
                        </TableCell>
                        <TableCell>{backlink.anchor_text}</TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              backlink.is_dofollow
                                ? "border-emerald-500/30 text-emerald-600"
                                : ""
                            }
                          >
                            {backlink.is_dofollow ? "Dofollow" : "Nofollow"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {backlink.domain_authority ?? "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                    {internalLinks.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="py-8 text-center text-muted-foreground"
                        >
                          No internal link data found.
                        </TableCell>
                      </TableRow>
                    ) : null}
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
                    {technicalBacklinks.map((backlink) => (
                      <TableRow key={backlink.id}>
                        <TableCell className="break-all font-medium">
                          <a
                            href={backlink.target_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center text-brand hover:underline"
                          >
                            {backlink.target_url}
                            <ExternalLink className="ml-1 h-3 w-3" />
                          </a>
                        </TableCell>
                        <TableCell>{backlink.anchor_text}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {resolveDomain(backlink.target_url) || "Unknown"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              backlink.is_dofollow
                                ? "border-emerald-500/30 text-emerald-600"
                                : ""
                            }
                          >
                            {backlink.is_dofollow ? "Dofollow" : "Nofollow"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {backlink.domain_authority ?? "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                    {technicalBacklinks.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="py-8 text-center text-muted-foreground"
                        >
                          No technical backlinks found.
                        </TableCell>
                      </TableRow>
                    ) : null}
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
                  {brandMentions.map((backlink) => {
                    const analysis = parseMentionAnalysis(backlink.anchor_text);
                    return (
                      <div
                        key={backlink.id}
                        className="glass-panel space-y-2 rounded-lg border border-border p-4"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <a
                              href={backlink.target_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center font-medium text-brand hover:underline"
                            >
                              {resolveDomain(backlink.target_url) ||
                                backlink.target_url}
                              <ExternalLink className="ml-1 h-3 w-3" />
                            </a>
                            <p className="mt-1 text-sm text-muted-foreground">
                              {backlink.target_url}
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
                        <div className="grid grid-cols-1 gap-4 text-sm text-muted-foreground md:grid-cols-3">
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
                            {backlink.is_dofollow ? "Dofollow" : "Nofollow"}
                          </div>
                        </div>
                        <div className="rounded border border-border bg-muted/50 p-3">
                          <p className="text-sm">
                            <span className="font-semibold text-foreground">
                              Context:
                            </span>{" "}
                            {analysis.snippet}
                          </p>
                        </div>
                        <div className="rounded border-l-4 border-brand bg-brand/10 p-3">
                          <p className="text-sm">
                            <span className="font-semibold text-foreground">
                              Recommendation:
                            </span>{" "}
                            {analysis.recommendation}
                          </p>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          ID: #{backlink.id} · DA:{" "}
                          {backlink.domain_authority ?? "—"}
                        </div>
                      </div>
                    );
                  })}
                  {brandMentions.length === 0 ? (
                    <div className="py-8 text-center text-muted-foreground">
                      No brand mentions found. Run the analysis to discover
                      citations.
                    </div>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
