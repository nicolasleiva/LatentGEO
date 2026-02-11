'use client'

import { Header } from '@/components/header'
import {
    Book, Zap, Globe, Code, GitBranch, BarChart3,
    Shield, Rocket, HelpCircle, ExternalLink, Search
} from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'

const docs = [
    {
        category: 'Getting Started',
        icon: Rocket,
        color: 'text-brand',
        items: [
            { title: 'Introduction to GEO', description: 'Learn what Generative Engine Optimization is and why it matters', href: '#intro' },
            { title: 'Quick Start Guide', description: 'Get your first audit running in minutes', href: '#quickstart' },
            { title: 'Understanding Your GEO Score', description: 'How we calculate and what it means', href: '#score' },
        ]
    },
    {
        category: 'Core Features',
        icon: Zap,
        color: 'text-brand',
        items: [
            { title: 'Website Auditing', description: 'Deep dive into SEO and GEO analysis', href: '#auditing' },
            { title: 'Competitor Analysis', description: 'Compare your site against competitors', href: '#competitors' },
            { title: 'AI Content Suggestions', description: 'Get AI-powered content recommendations', href: '#content' },
        ]
    },
    {
        category: 'Integrations',
        icon: GitBranch,
        color: 'text-brand',
        items: [
            { title: 'GitHub Auto-Fix', description: 'Automatically fix issues in your codebase', href: '#github' },
            { title: 'HubSpot Integration', description: 'Connect your landing pages', href: '#hubspot' },
            { title: 'API Reference', description: 'Build custom integrations', href: '#api' },
        ]
    },
    {
        category: 'Advanced',
        icon: Shield,
        color: 'text-brand',
        items: [
            { title: 'PageSpeed Insights', description: 'Core Web Vitals and performance', href: '#pagespeed' },
            { title: 'LLM Visibility', description: 'How AI models see your brand', href: '#llm' },
            { title: 'Schema Markup', description: 'Structured data optimization', href: '#schema' },
        ]
    },
]

export default function DocsPage() {
    const [searchQuery, setSearchQuery] = useState('')

    const filteredDocs = docs.map(section => ({
        ...section,
        items: section.items.filter(item =>
            item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.description.toLowerCase().includes(searchQuery.toLowerCase())
        )
    })).filter(section => section.items.length > 0)

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
                        Learn LatentGEO.ai
                    </h1>
                    <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                        Everything you need to optimize your website for the age of generative AI search.
                    </p>
                </div>

                {/* Search */}
                <div className="max-w-xl mx-auto mb-12">
                    <div className="relative">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground/60" />
                        <input
                            type="text"
                            placeholder="Search documentation..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-12 pr-4 py-4 bg-background/80 border border-border/70 rounded-xl text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10"
                        />
                    </div>
                </div>

                {/* Documentation Sections */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {filteredDocs.map((section) => (
                        <div
                            key={section.category}
                            className="glass-card p-6"
                        >
                            <div className="flex items-center gap-3 mb-6">
                                <div className={`p-2 rounded-lg bg-background/70 border border-border/70 ${section.color}`}>
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
                        <h2 className="text-xl font-semibold">Need Help?</h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <a
                            href="mailto:support@auditorgeo.com"
                            className="p-4 bg-background/70 border border-border/70 rounded-xl hover:bg-foreground/5 transition-colors text-center"
                        >
                            <p className="font-medium">Email Support</p>
                            <p className="text-sm text-muted-foreground">Get help via email</p>
                        </a>
                        <a
                            href="https://github.com/auditorgeo/issues"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-4 bg-background/70 border border-border/70 rounded-xl hover:bg-foreground/5 transition-colors text-center"
                        >
                            <p className="font-medium">GitHub Issues</p>
                            <p className="text-sm text-muted-foreground">Report bugs & features</p>
                        </a>
                        <a
                            href="#"
                            className="p-4 bg-background/70 border border-border/70 rounded-xl hover:bg-foreground/5 transition-colors text-center"
                        >
                            <p className="font-medium">Community</p>
                            <p className="text-sm text-muted-foreground">Join our Discord</p>
                        </a>
                    </div>
                </div>

                {/* Content Sections */}
                <div className="mt-16 space-y-16">
                    <section id="intro" className="scroll-mt-24">
                        <h2 className="text-2xl font-bold mb-4">Introduction to GEO</h2>
                        <div className="prose max-w-none max-w-none">
                            <p className="text-foreground/80 leading-relaxed">
                                <strong>Generative Engine Optimization (GEO)</strong> is the practice of optimizing your
                                digital content to be accurately represented and cited by AI-powered search engines
                                and assistants like ChatGPT, Perplexity, Google SGE, and Bing Chat.
                            </p>
                            <p className="text-foreground/80 leading-relaxed mt-4">
                                Unlike traditional SEO which focuses on ranking in search results, GEO ensures your
                                brand, products, and services are correctly understood and recommended by AI systems
                                when users ask questions.
                            </p>
                            <div className="mt-6 p-4 bg-brand/10 border border-brand/20 rounded-xl">
                                <p className="text-brand font-medium">Key Insight</p>
                                <p className="text-foreground/80 mt-2">
                                    Studies show that 43% of consumers are already using AI assistants for product
                                    research. If your content is not optimized for GEO, you are invisible to nearly
                                    half of potential customers.
                                </p>
                            </div>
                        </div>
                    </section>

                    <section id="quickstart" className="scroll-mt-24">
                        <h2 className="text-2xl font-bold mb-4">Quick Start Guide</h2>
                        <div className="space-y-4">
                            <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                                    1
                                </div>
                                <div>
                                    <h3 className="font-medium">Enter your website URL</h3>
                                    <p className="text-muted-foreground text-sm mt-1">
                                        Go to the homepage and paste your website URL in the search bar.
                                    </p>
                                </div>
                            </div>
                            <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                                    2
                                </div>
                                <div>
                                    <h3 className="font-medium">Wait for the analysis</h3>
                                    <p className="text-muted-foreground text-sm mt-1">
                                        Our AI crawls your site, analyzes content, and compares with competitors.
                                    </p>
                                </div>
                            </div>
                            <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                                    3
                                </div>
                                <div>
                                    <h3 className="font-medium">Review your GEO Score</h3>
                                    <p className="text-muted-foreground text-sm mt-1">
                                        Get actionable insights and a prioritized fix plan to improve your visibility.
                                    </p>
                                </div>
                            </div>
                            <div className="flex gap-4 p-4 bg-background/70 rounded-xl">
                                <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center flex-shrink-0">
                                    4
                                </div>
                                <div>
                                    <h3 className="font-medium">Auto-fix with GitHub</h3>
                                    <p className="text-muted-foreground text-sm mt-1">
                                        Connect your repository and let AI automatically create pull requests with fixes.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section id="score" className="scroll-mt-24">
                        <h2 className="text-2xl font-bold mb-4">Understanding Your GEO Score</h2>
                        <p className="text-foreground/80 mb-6">
                            Your GEO Score is calculated from multiple factors that influence how AI systems
                            understand and represent your content:
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="p-4 bg-background/70 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-brand rounded-full" />
                                    <span className="font-medium">Content Quality</span>
                                </div>
                                <p className="text-muted-foreground text-sm">
                                    Clear, authoritative content with proper structure and headings.
                                </p>
                            </div>
                            <div className="p-4 bg-background/70 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-brand rounded-full" />
                                    <span className="font-medium">Schema Markup</span>
                                </div>
                                <p className="text-muted-foreground text-sm">
                                    Structured data that helps AI understand your content.
                                </p>
                            </div>
                            <div className="p-4 bg-background/70 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-brand rounded-full" />
                                    <span className="font-medium">E-E-A-T Signals</span>
                                </div>
                                <p className="text-muted-foreground text-sm">
                                    Experience, Expertise, Authoritativeness, and Trustworthiness.
                                </p>
                            </div>
                            <div className="p-4 bg-background/70 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-brand rounded-full" />
                                    <span className="font-medium">Technical SEO</span>
                                </div>
                                <p className="text-muted-foreground text-sm">
                                    Meta tags, performance, and crawlability factors.
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
    )
}
