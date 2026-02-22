"use client";

import { Header } from "@/components/header";
import {
  Book,
  Zap,
  Globe,
  Code,
  GitBranch,
  BarChart3,
  Shield,
  Rocket,
  HelpCircle,
  ExternalLink,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

const docs = [
  {
    category: "Execution Tracks",
    icon: Rocket,
    color: "text-brand",
    items: [
      {
        title: "AI Visibility Baseline",
        description:
          "Run your first audit and capture where your offer is underrepresented in AI answers.",
        href: "#intro",
      },
      {
        title: "First 48 Hours Playbook",
        description:
          "How to prioritize fixes, align owners, and create an execution backlog quickly.",
        href: "#quickstart",
      },
      {
        title: "Score Interpretation",
        description:
          "Understand score components and how they map to technical and content workstreams.",
        href: "#score",
      },
    ],
  },
  {
    category: "Core Workflows",
    icon: Zap,
    color: "text-brand",
    items: [
      {
        title: "Audit Operations",
        description: "Manage audit queue, reruns, and baseline comparisons over time.",
        href: "#auditing",
      },
      {
        title: "Competitive Positioning",
        description:
          "Benchmark citation share and identify opportunities to overtake key competitors.",
        href: "#competitors",
      },
      {
        title: "Content and Entity Improvements",
        description:
          "Strengthen page structure and entity clarity to increase citation confidence.",
        href: "#content",
      },
    ],
  },
  {
    category: "Integrations",
    icon: GitBranch,
    color: "text-brand",
    items: [
      {
        title: "GitHub Delivery Loop",
        description:
          "Generate implementation-ready PR workflows from audit findings.",
        href: "#github",
      },
      {
        title: "HubSpot Publishing Flow",
        description: "Sync and optimize key landing pages for AI-era discoverability.",
        href: "#hubspot",
      },
      {
        title: "Typed API Client",
        description: "Use OpenAPI-generated types and client modules across your stack.",
        href: "#api",
      },
    ],
  },
  {
    category: "Governance",
    icon: Shield,
    color: "text-brand",
    items: [
      {
        title: "Quality Gates",
        description: "Set merge criteria for type-check, lint, unit tests, and E2E checks.",
        href: "#pagespeed",
      },
      {
        title: "Release Strategy",
        description: "Use canaries, flags, and rollback-safe iteration by PR phase.",
        href: "#llm",
      },
      {
        title: "Security and Access",
        description: "Control auth, scoped sessions, and operational traceability.",
        href: "#schema",
      },
    ],
  },
];

export default function DocsPage() {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredDocs = docs
    .map((section) => ({
      ...section,
      items: section.items.filter(
        (item) =>
          item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.description.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    }))
    .filter((section) => section.items.length > 0);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-12">
        {/* Hero */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-brand/10 border border-brand/20 rounded-full text-brand text-sm mb-6">
            <Book className="w-4 h-4" />
            Documentation
          </div>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Playbooks for running LatentGEO.ai in production
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Practical guides for audit operations, AI visibility growth, and delivery workflows.
          </p>
        </div>

        {/* Search */}
        <div className="max-w-xl mx-auto mb-12">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground/60" />
            <input
              type="text"
              placeholder="Search playbooks and workflows..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-4 bg-background/80 border border-border/70 rounded-xl text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10"
            />
          </div>
        </div>

        {/* Documentation Sections */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {filteredDocs.map((section) => (
            <div key={section.category} className="glass-card p-6">
              <div className="flex items-center gap-3 mb-6">
                <div
                  className={`p-2 rounded-lg bg-background/70 border border-border/70 ${section.color}`}
                >
                  <section.icon className="w-5 h-5" />
                </div>
                <h2 className="text-lg font-semibold">{section.category}</h2>
              </div>

              <div className="space-y-4">
                {section.items.map((item) => (
                  <a
                    key={item.title}
                    href={item.href}
                    className="block p-4 bg-background/70 border border-border/70 rounded-xl hover:bg-foreground/5 transition-colors group"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-medium group-hover:text-brand transition-colors">
                          {item.title}
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          {item.description}
                        </p>
                      </div>
                      <ExternalLink className="w-4 h-4 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors flex-shrink-0" />
                    </div>
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Quick Links */}
        <div className="mt-12 p-8 glass-card rounded-2xl">
          <div className="flex items-center gap-3 mb-6">
            <HelpCircle className="w-6 h-6 text-brand" />
            <h2 className="text-xl font-semibold">Support Channels</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <a
              href="mailto:support@auditorgeo.com"
              className="p-4 bg-background/70 border border-border/70 rounded-xl hover:bg-foreground/5 transition-colors text-center"
            >
              <p className="font-medium">Support Email</p>
              <p className="text-sm text-muted-foreground">
                Response for product and ops questions
              </p>
            </a>
            <a
              href="https://github.com/auditorgeo/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 bg-background/70 border border-border/70 rounded-xl hover:bg-foreground/5 transition-colors text-center"
            >
              <p className="font-medium">Issue Tracker</p>
              <p className="text-sm text-muted-foreground">
                Bug reports and feature requests
              </p>
            </a>
            <a
              href="https://github.com/auditorgeo/discussions"
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 bg-background/70 border border-border/70 rounded-xl hover:bg-foreground/5 transition-colors text-center"
            >
              <p className="font-medium">Discussions</p>
              <p className="text-sm text-muted-foreground">
                Community and implementation threads
              </p>
            </a>
          </div>
        </div>

        {/* Content Sections */}
        <div className="mt-16 space-y-16">
          <section id="intro" className="scroll-mt-24">
            <h2 className="text-2xl font-bold mb-4">AI Visibility Baseline</h2>
            <div className="prose max-w-none max-w-none">
              <p className="text-foreground/80 leading-relaxed">
                <strong>Generative Engine Optimization (GEO)</strong> is the
                practice of optimizing your digital content to be accurately
                represented and cited by AI-powered search engines and
                assistants like ChatGPT, Perplexity, Google SGE, and Bing Chat.
              </p>
              <p className="text-foreground/80 leading-relaxed mt-4">
                Unlike traditional SEO, GEO optimizes how assistants understand
                your entities, compare your offering, and decide whether to cite
                your pages in high-intent responses.
              </p>
              <div className="mt-6 p-4 bg-brand/10 border border-brand/20 rounded-xl">
                <p className="text-brand font-medium">Operating Insight</p>
                <p className="text-foreground/80 mt-2">
                  AI discovery now influences category framing. If your pages are
                  not citation-ready, competitors define the narrative first.
                </p>
              </div>
            </div>
          </section>

          <section id="quickstart" className="scroll-mt-24">
            <h2 className="text-2xl font-bold mb-4">First 48 Hours Playbook</h2>
            <div className="space-y-4">
              <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                  1
                </div>
                <div>
                  <h3 className="font-medium">Run a baseline audit</h3>
                  <p className="text-muted-foreground text-sm mt-1">
                    Submit your primary demand page and establish an initial AI visibility baseline.
                  </p>
                </div>
              </div>
              <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                  2
                </div>
                <div>
                  <h3 className="font-medium">Review ranked opportunities</h3>
                  <p className="text-muted-foreground text-sm mt-1">
                    Validate the highest-impact issues across structure, evidence, and competitor positioning.
                  </p>
                </div>
              </div>
              <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                  3
                </div>
                <div>
                  <h3 className="font-medium">Align owners and priority</h3>
                  <p className="text-muted-foreground text-sm mt-1">
                    Convert findings into an execution queue owned by content, SEO, and engineering.
                  </p>
                </div>
              </div>
              <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                  4
                </div>
                <div>
                  <h3 className="font-medium">Ship and re-measure</h3>
                  <p className="text-muted-foreground text-sm mt-1">
                    Deliver fixes through your workflow and re-run audits to verify trajectory.
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section id="score" className="scroll-mt-24">
            <h2 className="text-2xl font-bold mb-4">
              Understanding the GEO Score
            </h2>
            <p className="text-foreground/80 mb-6">
              The score combines technical quality and semantic clarity signals that affect AI response reliability:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-background/70 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-brand rounded-full" />
                  <span className="font-medium">Content Quality</span>
                </div>
                <p className="text-muted-foreground text-sm">
                  Clear, authority-oriented content with strong structure and intent matching.
                </p>
              </div>
              <div className="p-4 bg-background/70 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-brand rounded-full" />
                  <span className="font-medium">Schema Markup</span>
                </div>
                <p className="text-muted-foreground text-sm">
                  Structured data that improves entity interpretation and response confidence.
                </p>
              </div>
              <div className="p-4 bg-background/70 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-brand rounded-full" />
                  <span className="font-medium">E-E-A-T Signals</span>
                </div>
                <p className="text-muted-foreground text-sm">
                  Experience, expertise, authority, and trust evidence for assistant ranking logic.
                </p>
              </div>
              <div className="p-4 bg-background/70 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 bg-brand rounded-full" />
                  <span className="font-medium">Technical SEO</span>
                </div>
                <p className="text-muted-foreground text-sm">
                  Performance, crawlability, and implementation hygiene across critical pages.
                </p>
              </div>
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-20 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-muted-foreground/60 text-sm">
          © 2026 LatentGEO.ai. Documentation is continuously updated.
        </div>
      </footer>
    </div>
  );
}
