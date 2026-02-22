"use client";

import { usePathname } from "next/navigation";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { withLocale } from "@/lib/locale-routing";
import {
  Check,
  Zap,
  Building2,
  Sparkles,
  Globe,
  GitBranch,
  BarChart3,
  Shield,
  Clock,
} from "lucide-react";

const plans = [
  {
    name: "Starter",
    price: "$0",
    period: "month",
    description: "For teams validating AI visibility workflows",
    badge: null,
    features: [
      "3 audits per month",
      "Baseline GEO scorecard",
      "Single-market competitor snapshot",
      "Execution backlog export",
      "Community support",
    ],
    notIncluded: [
      "Automated PR drafting",
      "Priority queue orchestration",
      "API access",
      "Team governance controls",
    ],
    cta: "Start Free",
    ctaStyle:
      "border border-border bg-background/80 text-foreground hover:bg-foreground/5",
    popular: false,
  },
  {
    name: "Growth",
    price: "$49",
    period: "month",
    description: "For in-house growth and SEO teams",
    badge: "Recommended",
    features: [
      "Unlimited audits",
      "Advanced GEO scoring model",
      "Multi-competitor intelligence",
      "Automated PR drafting",
      "PageSpeed + technical diagnostics",
      "Visibility trend tracking",
      "Priority support",
      "Custom reporting templates",
    ],
    notIncluded: ["White-label workspace controls"],
    cta: "Start Growth Plan",
    ctaStyle:
      "bg-brand text-brand-foreground hover:bg-brand/90 shadow-[0_12px_30px_rgba(16,185,129,0.25)]",
    popular: true,
  },
  {
    name: "Scale",
    price: "Custom",
    period: "contract",
    description: "For enterprise growth organizations and agencies",
    badge: null,
    features: [
      "Everything in Growth",
      "API and data pipeline access",
      "SSO and role governance",
      "White-label reporting",
      "Dedicated success architecture",
      "Custom integrations + runbooks",
      "SLA-backed support model",
    ],
    notIncluded: [],
    cta: "Talk to Sales",
    ctaStyle:
      "border border-border bg-background/80 text-foreground hover:bg-foreground/5",
    popular: false,
  },
];

const faqs = [
  {
    q: "What is GEO and why do I need it?",
    a: "GEO (Generative Engine Optimization) helps your product pages appear accurately in AI answers. As buyers increasingly research through assistants, GEO becomes a core acquisition channel.",
  },
  {
    q: "Can we switch plans as our team grows?",
    a: "Yes. You can move between plans at any time. Billing adjusts to your new tier on the next cycle.",
  },
  {
    q: "Do you provide enterprise procurement support?",
    a: "Scale plans include standard procurement workflows, legal/security review support, and invoice-based billing.",
  },
  {
    q: "How quickly can we launch?",
    a: "Most teams run their first production audit in under one day once Auth0 and repository access are configured.",
  },
];

export default function PricingPage() {
  const pathname = usePathname();
  const startAuditHref = withLocale(pathname, "/");

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-16">
        {/* Hero */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-brand/10 border border-brand/20 rounded-full text-brand text-sm mb-6">
            <Sparkles className="w-4 h-4" />
            Clear pricing for real operators
          </div>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Pricing built for execution, not vanity seats.
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Start lean, prove impact, and scale governance and automation as your team matures.
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative p-8 rounded-2xl border transition-all ${
                plan.popular
                  ? "bg-gradient-to-b from-brand/10 to-foreground/5 border-brand/30 shadow-lg shadow-brand/10"
                  : "bg-background/70 border-border/70 hover:border-border"
              }`}
            >
              {plan.badge && (
                <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand text-brand-foreground border-0">
                  {plan.badge}
                </Badge>
              )}

              <div className="mb-6">
                <h2 className="text-xl font-bold mb-2">{plan.name}</h2>
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold">{plan.price}</span>
                  <span className="text-muted-foreground">/{plan.period}</span>
                </div>
                <p className="text-muted-foreground mt-2">{plan.description}</p>
              </div>

              <button
                className={`w-full py-3 rounded-xl font-medium transition-all ${plan.ctaStyle}`}
              >
                {plan.cta}
              </button>

              <div className="mt-8 space-y-3">
                {plan.features.map((feature) => (
                  <div key={feature} className="flex items-center gap-3">
                    <Check className="w-5 h-5 text-brand flex-shrink-0" />
                    <span className="text-foreground/80">{feature}</span>
                  </div>
                ))}
                {plan.notIncluded.map((feature) => (
                  <div
                    key={feature}
                    className="flex items-center gap-3 opacity-50"
                  >
                    <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                      <div className="w-1.5 h-0.5 bg-foreground/30 rounded" />
                    </div>
                    <span className="text-muted-foreground/60">{feature}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Features Comparison */}
        <div className="mb-20">
          <h2 className="text-2xl font-bold text-center mb-8">
            Operating principles
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="p-6 bg-background/70 border border-border/70 rounded-2xl text-center">
              <Globe className="w-8 h-8 text-brand mx-auto mb-4" />
              <h3 className="font-semibold mb-2">AI-First Discovery</h3>
              <p className="text-sm text-muted-foreground">
                Prioritize prompts and categories where AI visibility drives demand.
              </p>
            </div>
            <div className="p-6 bg-background/70 border border-border/70 rounded-2xl text-center">
              <GitBranch className="w-8 h-8 text-brand mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Engineering Hand-off</h3>
              <p className="text-sm text-muted-foreground">
                Move from insight to implementation-ready work with GitHub-native flow.
              </p>
            </div>
            <div className="p-6 bg-background/70 border border-border/70 rounded-2xl text-center">
              <Building2 className="w-8 h-8 text-brand mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Team Alignment</h3>
              <p className="text-sm text-muted-foreground">
                Keep product, content, and growth teams on one execution narrative.
              </p>
            </div>
            <div className="p-6 bg-background/70 border border-border/70 rounded-2xl text-center">
              <Shield className="w-8 h-8 text-brand mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Governed Scale</h3>
              <p className="text-sm text-muted-foreground">
                Enforce approvals and security controls as automation expands.
              </p>
            </div>
          </div>
        </div>

        <div className="mb-20">
          <h2 className="text-2xl font-bold text-center mb-8">
            Why teams choose LatentGEO.ai
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 bg-background/70 border border-border/70 rounded-2xl text-center">
              <BarChart3 className="w-8 h-8 text-brand mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Competitive clarity</h3>
              <p className="text-sm text-muted-foreground">
                Benchmark citation share and prioritize the battles that matter.
              </p>
            </div>
            <div className="p-6 bg-background/70 border border-border/70 rounded-2xl text-center">
              <Clock className="w-8 h-8 text-brand mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Fast operational loop</h3>
              <p className="text-sm text-muted-foreground">
                Reduce the time between insight, implementation, and validation.
              </p>
            </div>
            <div className="p-6 bg-background/70 border border-border/70 rounded-2xl text-center">
              <Zap className="w-8 h-8 text-brand mx-auto mb-4" />
              <h3 className="font-semibold mb-2">Actionable outputs</h3>
              <p className="text-sm text-muted-foreground">
                Reports, exportable plans, and execution-ready recommendations.
              </p>
            </div>
          </div>
        </div>

        {/* FAQs */}
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-8">
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {faqs.map((faq) => (
              <div
                key={faq.q}
                className="p-6 bg-background/70 border border-border/70 rounded-2xl"
              >
                <h3 className="font-semibold mb-2">{faq.q}</h3>
                <p className="text-muted-foreground">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="mt-20 text-center p-12 bg-gradient-to-br from-brand/10 to-foreground/5 border border-border/70 rounded-2xl">
          <h2 className="text-3xl font-bold mb-4">
            Ready to run AI visibility as a core growth function?
          </h2>
          <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
            Start with a free audit, then scale your operating model when the data proves impact.
          </p>
          <a
            href={startAuditHref}
            className="inline-flex items-center gap-2 px-8 py-4 bg-brand text-brand-foreground rounded-xl font-semibold hover:bg-brand/90 transition-colors shadow-[0_12px_30px_rgba(16,185,129,0.25)]"
          >
            <Zap className="w-5 h-5" />
            Run Free Audit
          </a>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-20 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-muted-foreground/60 text-sm">
          © 2026 LatentGEO.ai. Pricing shown in USD.
        </div>
      </footer>
    </div>
  );
}
