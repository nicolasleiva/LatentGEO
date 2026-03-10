import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Clock,
  FileText,
  GitPullRequest,
  Globe,
  Link as LinkIcon,
  Rocket,
  Shield,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";

import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import HomeAuditForm from "./HomeAuditForm";

export interface HomeAudit {
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

type HomePageClientProps = {
  initialAudits: HomeAudit[];
  locale: string;
  viewer: {
    id?: string;
    email?: string;
    name?: string;
    picture?: string | null;
  };
};

const getAuditDisplayDomain = (audit: HomeAudit) => {
  if (audit.domain) {
    return audit.domain;
  }

  try {
    return new URL(audit.url).hostname.replace("www.", "");
  } catch {
    return audit.url;
  }
};

export default function HomePageClient({
  initialAudits,
  locale,
  viewer: _viewer,
}: HomePageClientProps) {
  return (
    <div className="min-h-screen text-foreground">
      <Header />

      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14">
        <section className="relative overflow-hidden rounded-[2rem] border border-border/70 bg-card/80 p-6 sm:p-10 lg:p-14">
          <div className="absolute -left-16 -top-20 h-64 w-64 rounded-full bg-brand/10 blur-3xl" />
          <div className="absolute -bottom-20 -right-16 h-72 w-72 rounded-full bg-foreground/10 blur-3xl" />

          <div className="relative z-10 grid items-start gap-12 lg:grid-cols-[1.08fr_0.92fr]">
            <div className="space-y-8">
              <div className="inline-flex items-center gap-2 rounded-full border border-foreground/10 bg-foreground/5 px-4 py-2 text-sm text-foreground/80">
                <Sparkles className="h-4 w-4 text-brand" />
                AI search operating system
              </div>

              <h1 className="text-4xl font-semibold leading-[0.95] tracking-tight md:text-6xl lg:text-7xl">
                Own your category in AI answers.
              </h1>

              <p className="max-w-2xl text-lg leading-relaxed text-muted-foreground">
                Run one audit, get a prioritized execution map, and move from
                insight to shipped changes.
              </p>

              <p className="max-w-2xl text-sm text-foreground/80">
                From URL -&gt; high-impact gaps -&gt; implementation-ready
                actions.
              </p>

              <p className="max-w-2xl text-sm text-muted-foreground">
                Built for product marketing, SEO, and growth engineering teams.
              </p>

              <HomeAuditForm locale={locale} />

              <div
                className="grid grid-cols-1 gap-3 sm:grid-cols-3"
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
                    className="glass-card relative overflow-hidden p-6 sm:p-7"
                  >
                    <div className="absolute -right-14 -top-16 h-40 w-40 rounded-full bg-brand/20 blur-2xl" />
                    <div className="relative z-10 space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs uppercase tracking-widest text-muted-foreground">
                          {item.title}
                        </p>
                        <Icon className="h-4 w-4 text-brand" />
                      </div>
                      <p className="text-base font-semibold leading-tight sm:text-lg">
                        {item.summary}
                      </p>
                      <div className="rounded-xl border border-border/70 bg-background/70 px-4 py-3">
                        <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
                          Operating step
                        </p>
                        <p className="mt-1 text-sm text-foreground/85">
                          {item.detail}
                        </p>
                      </div>
                    </div>
                  </article>
                );
              })}

              <div className="flex items-start gap-3 rounded-2xl border border-border/70 bg-background/75 p-5">
                <Shield className="mt-0.5 h-5 w-5 text-brand" />
                <div>
                  <p className="text-sm font-semibold">Secure by design</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Scoped access, approval checkpoints, and traceable actions
                    keep automation controlled.
                  </p>
                </div>
              </div>
            </aside>
          </div>
        </section>

        <section className="mt-16 sm:mt-20">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm uppercase tracking-widest text-muted-foreground">
                Capabilities
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                Everything needed to run AI visibility like an operating
                function.
              </h2>
            </div>
            <p className="max-w-xl text-muted-foreground">
              Purpose-built modules connect discovery, remediation, and
              measurement without context switching.
            </p>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {featureCards.map((feature) => {
              const Icon = feature.icon;
              return (
                <article
                  key={feature.title}
                  className="rounded-2xl border border-border/70 bg-card/75 p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 text-brand">
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-[11px] uppercase tracking-widest text-muted-foreground">
                      {feature.tag}
                    </span>
                  </div>
                  <h3 className="mt-4 text-base font-semibold">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {feature.description}
                  </p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="mt-16 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold tracking-tight">
              Recent audit operations
            </h2>
            {initialAudits.length > 0 && (
              <Button
                asChild
                variant="ghost"
                className="text-muted-foreground hover:text-foreground"
              >
                <Link href={`/${locale}/audits`}>View queue</Link>
              </Button>
            )}
          </div>

          {initialAudits.length === 0 ? (
            <div className="glass-card py-16 text-center">
              <Globe className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" />
              <h3 className="mb-2 text-xl font-medium text-muted-foreground">
                No audits yet
              </h3>
              <p className="mb-4 text-muted-foreground/70">
                Submit your first URL to generate an AI visibility baseline.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
              {initialAudits.map((audit) => (
                <Link
                  key={audit.id}
                  href={`/${locale}/audits/${audit.id}`}
                  className="glass-card group block p-6"
                >
                  <div className="mb-4 flex items-center justify-between">
                    <div className="rounded-lg bg-muted/50 p-2">
                      <Globe className="h-5 w-5 text-brand" />
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        audit.status === "completed"
                          ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-600"
                          : audit.status === "failed"
                            ? "border-red-500/20 bg-red-500/10 text-red-600"
                            : audit.status === "running"
                              ? "border-brand/20 bg-brand/10 text-brand"
                              : "border-amber-500/20 bg-amber-500/10 text-amber-600"
                      }
                    >
                      {audit.status}
                    </Badge>
                  </div>

                  <h3 className="mb-1 truncate text-lg font-medium transition-colors group-hover:text-brand">
                    {getAuditDisplayDomain(audit)}
                  </h3>
                  <p className="mb-4 truncate text-sm text-muted-foreground">
                    {audit.url}
                  </p>

                  <div className="flex items-center justify-between border-t border-border pt-4 text-sm">
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {new Date(audit.created_at).toLocaleDateString()}
                    </span>
                    {audit.status === "completed" && audit.geo_score ? (
                      <span className="font-medium text-emerald-600">
                        GEO: {Math.round(audit.geo_score)}%
                      </span>
                    ) : null}
                    <ArrowRight className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-foreground" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="mt-20 border-t border-border py-8">
        <div className="mx-auto max-w-6xl px-6 text-center text-sm text-muted-foreground">
          © 2026 LatentGEO.ai. Built for AI-era growth teams.
        </div>
      </footer>
    </div>
  );
}
