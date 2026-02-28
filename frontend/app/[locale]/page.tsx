"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Search,
  ArrowRight,
  Activity,
  Globe,
  Clock,
  Sparkles,
  Shield,
  Zap,
  BarChart3,
  Target,
  Link as LinkIcon,
  Rocket,
  GitPullRequest,
  FileText,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Header } from "@/components/header";
import { createAudit, listAudits } from "@/lib/api-client";
import { useCombinedProfile, useRequireAppAuth } from "@/lib/app-auth";
import { withLocale } from "@/lib/locale-routing";
import { cn } from "@/lib/utils";

interface Audit {
  id: number;
  url: string;
  domain?: string;
  status: string;
  created_at: string;
  geo_score?: number;
}

const featureCards = [
  {
    title: "AI Demand Mapping",
    description:
      "Map category questions, comparison prompts, and buying-intent moments where your brand must appear.",
    icon: Globe,
    tag: "Discovery",
  },
  {
    title: "Citation Gap Analysis",
    description:
      "Find trust and evidence gaps that prevent assistants from citing your product pages confidently.",
    icon: LinkIcon,
    tag: "Trust",
  },
  {
    title: "Conversion Friction Signals",
    description:
      "Detect copy, UX, and technical blockers that suppress qualified traffic and pipeline.",
    icon: Activity,
    tag: "Revenue",
  },
  {
    title: "Execution Priority Queue",
    description:
      "Rank experiments by impact, confidence, and implementation effort for faster shipping.",
    icon: Target,
    tag: "Ops",
  },
  {
    title: "Autonomous PR Drafting",
    description:
      "Generate implementation-ready GitHub pull requests with scoped fixes and review context.",
    icon: GitPullRequest,
    tag: "Code",
  },
  {
    title: "Competitive Motion Radar",
    description:
      "Track where competitors dominate AI citations and where your offer can overtake them.",
    icon: BarChart3,
    tag: "Benchmark",
  },
  {
    title: "Pipeline Expansion Paths",
    description:
      "Surface prompts and pages most likely to expand qualified visits, demos, and sales outcomes.",
    icon: Rocket,
    tag: "Growth",
  },
  {
    title: "Executive Operating Reviews",
    description:
      "Share concise weekly updates on visibility, citations, shipped fixes, and impact trajectory.",
    icon: FileText,
    tag: "Leadership",
  },
];

const proofChips = [
  "Own category prompts in AI answers",
  "Convert citations into qualified sessions",
  "Ship fixes through engineering workflows",
];

const loopCards = [
  {
    title: "Diagnose",
    summary:
      "Expose where AI systems misunderstand your offer, positioning, and proof.",
    detail: "Submit URL -> get ranked opportunities and citation gaps",
    icon: Target,
  },
  {
    title: "Ship",
    summary:
      "Translate insights into implementation-ready tasks your team can approve quickly.",
    detail: "Approve actions -> generate PR-ready change plans",
    icon: Zap,
  },
  {
    title: "Compound",
    summary:
      "Track visibility, citation quality, and downstream conversion signals over time.",
    detail: "Measure outcomes -> iterate by expected revenue impact",
    icon: BarChart3,
  },
];

function normalizeAuditUrl(input: string): string {
  const raw = input.trim();
  if (!raw) return "";
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) return raw;
  return `https://${raw}`;
}

function isLikelyPublicHost(hostname: string): boolean {
  if (!hostname) return false;
  if (hostname === "localhost") return true;
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(hostname)) return true;
  return hostname.includes(".");
}

export default function HomePage() {
  const router = useRouter();
  const pathname = usePathname();
  const auth = useRequireAppAuth();
  const profile = useCombinedProfile(auth);
  const user = auth.ready ? profile : null;
  const authLoading = auth.loading || !auth.ready;
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleFeatures, setVisibleFeatures] = useState(0);

  const localePath = useCallback(
    (path: string) => {
      return withLocale(pathname, path);
    },
    [pathname],
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setVisibleFeatures((prev) =>
        prev >= featureCards.length ? featureCards.length : prev + 1,
      );
    }, 120);
    return () => window.clearInterval(timer);
  }, []);

  const recentAuditsQuery = useQuery({
    queryKey: ["audits", "recent"],
    queryFn: listAudits,
    enabled: Boolean(user) && !authLoading,
    select: (data) =>
      data
        .sort(
          (a: Audit, b: Audit) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        )
        .slice(0, 6),
  });

  const audits = (recentAuditsQuery.data as Audit[] | undefined) ?? [];
  const loading = recentAuditsQuery.isLoading;

  const createAuditMutation = useMutation({
    mutationFn: (payload: { url: string }) => createAudit(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["audits"] });
    },
  });

  const handleAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();

    setError(null);

    if (!url || !url.trim()) {
      setError("Please enter a valid URL");
      return;
    }

    const normalizedUrl = normalizeAuditUrl(url);
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(normalizedUrl);
      if (!isLikelyPublicHost(parsedUrl.hostname)) {
        throw new Error("Invalid host");
      }
    } catch {
      setError("Please enter a valid domain or URL (e.g., ceibo.digital)");
      return;
    }

    setSubmitting(true);
    try {
      const newAudit = await createAuditMutation.mutateAsync({
        url: normalizedUrl,
      });
      router.push(localePath(`/audits/${newAudit.id}`));
    } catch (error: any) {
      console.error("Error creating audit:", error);
      const errorMessage = error.message || "Please verify the server is running.";
      setError(`Connection error: ${errorMessage}`);
      setSubmitting(false);
    }
  };

  useEffect(() => {
    if (user && !authLoading) {
      const pendingUrl = sessionStorage.getItem("pendingAuditUrl");
      if (pendingUrl) {
        sessionStorage.removeItem("pendingAuditUrl");
        setUrl(pendingUrl);
      }
    }
  }, [user, authLoading]);

  // Loading State while checking auth
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Only render content if authenticated
  if (!user) return null;

  return (
    <div className="min-h-screen text-foreground">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <section className="relative overflow-hidden rounded-[2rem] border border-border/70 bg-card/80 p-6 sm:p-10 lg:p-14">
          <div className="absolute -top-20 -left-16 h-64 w-64 rounded-full bg-brand/10 blur-3xl" />
          <div className="absolute -bottom-20 -right-16 h-72 w-72 rounded-full bg-foreground/10 blur-3xl" />

          <div className="relative z-10 grid gap-12 lg:grid-cols-[1.08fr_0.92fr] items-start">
            <div className="space-y-8">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-foreground/5 border border-foreground/10 rounded-full text-foreground/80 text-sm">
                <Sparkles className="w-4 h-4 text-brand" />
                AI search operating system
              </div>

              <h1 className="text-4xl md:text-6xl lg:text-7xl font-semibold tracking-tight leading-[0.95]">
                Own your category in AI answers.
              </h1>

              <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
                Run one audit, get a prioritized execution map, and move from insight to shipped changes.
              </p>

              <p className="text-sm text-foreground/80 max-w-2xl">
                From URL -&gt; high-impact gaps -&gt; implementation-ready actions.
              </p>

              <p className="text-sm text-muted-foreground max-w-2xl">
                Built for product marketing, SEO, and growth engineering teams.
              </p>

              <form
                onSubmit={handleAudit}
                className="max-w-2xl relative"
                id="start-audit"
              >
                <div className="relative flex flex-col gap-2">
                  <div className="relative flex items-center glass-panel border border-border rounded-2xl p-2 shadow-2xl">
                    <Search className="w-5 h-5 text-muted-foreground ml-4" />
                    <input
                      type="text"
                      placeholder="Paste a public page URL (e.g., ceibo.digital)"
                      className="flex-1 bg-transparent border-none text-foreground placeholder:text-muted-foreground focus:ring-0 px-4 py-4 outline-none text-base"
                      value={url}
                      onChange={(e) => {
                        setUrl(e.target.value);
                        setError(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !submitting) {
                          e.preventDefault();
                          handleAudit(e as any);
                        }
                      }}
                      required
                      disabled={submitting}
                    />
                    <button
                      type="submit"
                      disabled={submitting || !url.trim()}
                      className="glass-button-primary px-6 py-3 rounded-xl flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      onClick={(e) => {
                        e.preventDefault();
                        handleAudit(e as any);
                      }}
                    >
                      {submitting ? (
                        <>
                          <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          Building your report
                        </>
                      ) : (
                        <>
                          Run free audit <ArrowRight className="w-5 h-5" />
                        </>
                      )}
                    </button>
                  </div>
                  {error && (
                    <div className="text-red-600 text-sm px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                      {error}
                    </div>
                  )}
                </div>
              </form>

              <div
                className="grid grid-cols-1 sm:grid-cols-3 gap-3"
                aria-label="Proof chips"
              >
                {proofChips.map((chip) => (
                  <div
                    key={chip}
                    className="rounded-xl border border-border/70 bg-background/70 px-4 py-3"
                  >
                    <p className="text-sm font-semibold">{chip}</p>
                  </div>
                ))}
              </div>
            </div>

            <aside aria-label="Growth loop highlights" className="space-y-4">
              {loopCards.map((item) => {
                const Icon = item.icon;
                return (
                  <article
                    key={item.title}
                    className="glass-card p-6 sm:p-7 relative overflow-hidden"
                  >
                    <div className="absolute -top-16 -right-14 h-40 w-40 rounded-full bg-brand/20 blur-2xl" />
                    <div className="relative z-10 space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs uppercase tracking-widest text-muted-foreground">
                          {item.title}
                        </p>
                        <Icon className="h-4 w-4 text-brand" />
                      </div>
                      <p className="text-base sm:text-lg font-semibold leading-tight">
                        {item.summary}
                      </p>
                      <div className="rounded-xl border border-border/70 bg-background/70 px-4 py-3">
                        <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
                          Operating step
                        </p>
                        <p className="text-sm text-foreground/85 mt-1">
                          {item.detail}
                        </p>
                      </div>
                    </div>
                  </article>
                );
              })}

              <div className="rounded-2xl border border-border/70 bg-background/75 p-5 flex items-start gap-3">
                <Shield className="h-5 w-5 text-brand mt-0.5" />
                <div>
                  <p className="text-sm font-semibold">Secure by design</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Scoped access, approval checkpoints, and traceable actions keep automation controlled.
                  </p>
                </div>
              </div>
            </aside>
          </div>
        </section>

        <section className="mt-16 sm:mt-20">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-widest text-muted-foreground">
                Capabilities
              </p>
              <h2 className="text-3xl md:text-4xl font-semibold tracking-tight mt-2">
                Everything needed to run AI visibility like an operating function.
              </h2>
            </div>
            <p className="text-muted-foreground max-w-xl">
              Purpose-built modules connect discovery, remediation, and measurement without context switching.
            </p>
          </div>

          <div className="mt-8 grid sm:grid-cols-2 xl:grid-cols-5 gap-4">
            {featureCards.map((feature, index) => {
              const Icon = feature.icon;
              const isVisible = index < visibleFeatures;
              return (
                <article
                  key={feature.title}
                  className={cn(
                    "rounded-2xl border border-border/70 bg-card/75 p-5 transition-all duration-500 ease-out",
                    isVisible
                      ? "translate-y-0 opacity-100"
                      : "translate-y-4 opacity-0",
                  )}
                  style={{ transitionDelay: `${index * 45}ms` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="h-10 w-10 rounded-xl bg-brand/10 text-brand flex items-center justify-center">
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-[11px] uppercase tracking-widest text-muted-foreground">
                      {feature.tag}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold mt-4">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                    {feature.description}
                  </p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="mt-16 space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-semibold tracking-tight">
              Recent audit operations
            </h2>
            {audits.length > 0 && (
              <Button
                variant="ghost"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => router.push(localePath("/audits"))}
              >
                View queue
              </Button>
            )}
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="glass-card h-48 animate-pulse" />
              ))}
            </div>
          ) : audits.length === 0 ? (
            <div className="text-center py-16 glass-card">
              <Globe className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-muted-foreground mb-2">
                No audits yet
              </h3>
              <p className="text-muted-foreground/70 mb-4">
                Submit your first URL to generate an AI visibility baseline.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {audits.map((audit) => (
                <div
                  key={audit.id}
                  onClick={() =>
                    router.push(localePath(`/audits/${audit.id}`))
                  }
                  className="p-6 glass-card cursor-pointer group hover:-translate-y-1"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="p-2 bg-muted/50 rounded-lg">
                      <Globe className="w-5 h-5 text-brand" />
                    </div>
                    <Badge
                      variant="outline"
                      className={`
                      ${
                        audit.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                          : audit.status === "failed"
                            ? "bg-red-500/10 text-red-600 border-red-500/20"
                            : audit.status === "running"
                              ? "bg-brand/10 text-brand border-brand/20"
                              : "bg-amber-500/10 text-amber-600 border-amber-500/20"
                      }
                    `}
                    >
                      {audit.status}
                    </Badge>
                  </div>

                  <h3 className="text-lg font-medium truncate mb-1 group-hover:text-brand transition-colors">
                    {audit.domain ||
                      (() => {
                        try {
                          return new URL(audit.url).hostname.replace(
                            "www.",
                            "",
                          );
                        } catch {
                          return audit.url;
                        }
                      })()}
                  </h3>
                  <p className="text-sm text-muted-foreground truncate mb-4">
                    {audit.url}
                  </p>

                  <div className="flex justify-between items-center pt-4 border-t border-border text-sm">
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      {new Date(audit.created_at).toLocaleDateString()}
                    </span>
                    {audit.status === "completed" && audit.geo_score && (
                      <span className="text-emerald-600 font-medium">
                        GEO: {Math.round(audit.geo_score)}%
                      </span>
                    )}
                    <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-border mt-20 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-muted-foreground text-sm">
          © 2026 LatentGEO.ai. Built for AI-era growth teams.
        </div>
      </footer>
    </div>
  );
}
