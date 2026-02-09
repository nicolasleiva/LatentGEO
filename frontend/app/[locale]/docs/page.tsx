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
        color: 'text-green-400',
        items: [
            { title: 'Introduction to GEO', description: 'Learn what Generative Engine Optimization is and why it matters', href: '#intro' },
            { title: 'Quick Start Guide', description: 'Get your first audit running in minutes', href: '#quickstart' },
            { title: 'Understanding Your GEO Score', description: 'How we calculate and what it means', href: '#score' },
        ]
    },
    {
        category: 'Core Features',
        icon: Zap,
        color: 'text-blue-400',
        items: [
            { title: 'Website Auditing', description: 'Deep dive into SEO and GEO analysis', href: '#auditing' },
            { title: 'Competitor Analysis', description: 'Compare your site against competitors', href: '#competitors' },
            { title: 'AI Content Suggestions', description: 'Get AI-powered content recommendations', href: '#content' },
        ]
    },
    {
        category: 'Integrations',
        icon: GitBranch,
        color: 'text-purple-400',
        items: [
            { title: 'GitHub Auto-Fix', description: 'Automatically fix issues in your codebase', href: '#github' },
            { title: 'HubSpot Integration', description: 'Connect your landing pages', href: '#hubspot' },
            { title: 'API Reference', description: 'Build custom integrations', href: '#api' },
        ]
    },
    {
        category: 'Advanced',
        icon: Shield,
        color: 'text-yellow-400',
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
        <div className="min-h-screen bg-black text-white">
            <Header />

            <main className="max-w-6xl mx-auto px-6 py-12">
                {/* Hero */}
                <div className="text-center mb-12">
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-full text-blue-400 text-sm mb-6">
                        <Book className="w-4 h-4" />
                        Documentation
                    </div>
                    <h1 className="text-4xl md:text-5xl font-bold mb-4">
                        Learn Auditor GEO
                    </h1>
                    <p className="text-xl text-white/60 max-w-2xl mx-auto">
                        Everything you need to optimize your website for the age of generative AI search.
                    </p>
                </div>

                {/* Search */}
                <div className="max-w-xl mx-auto mb-12">
                    <div className="relative">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                        <input
                            type="text"
                            placeholder="Search documentation..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-12 pr-4 py-4 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-white/40 focus:outline-none focus:border-white/30"
                        />
                    </div>
                </div>

                {/* Documentation Sections */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {filteredDocs.map((section) => (
                        <div
                            key={section.category}
                            className="p-6 bg-white/5 border border-white/10 rounded-2xl"
                        >
                            <div className="flex items-center gap-3 mb-6">
                                <div className={`p-2 rounded-lg bg-white/5 ${section.color}`}>
                                    <section.icon className="w-5 h-5" />
                                </div>
                                <h2 className="text-lg font-semibold">{section.category}</h2>
                            </div>

                            <div className="space-y-4">
                                {section.items.map((item) => (
                                    <a
                                        key={item.title}
                                        href={item.href}
                                        className="block p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors group"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <h3 className="font-medium group-hover:text-blue-400 transition-colors">
                                                    {item.title}
                                                </h3>
                                                <p className="text-sm text-white/60 mt-1">
                                                    {item.description}
                                                </p>
                                            </div>
                                            <ExternalLink className="w-4 h-4 text-white/30 group-hover:text-white/60 transition-colors flex-shrink-0" />
                                        </div>
                                    </a>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Quick Links */}
                <div className="mt-12 p-8 bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/10 rounded-2xl">
                    <div className="flex items-center gap-3 mb-6">
                        <HelpCircle className="w-6 h-6 text-blue-400" />
                        <h2 className="text-xl font-semibold">Need Help?</h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <a
                            href="mailto:support@auditorgeo.com"
                            className="p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors text-center"
                        >
                            <p className="font-medium">Email Support</p>
                            <p className="text-sm text-white/60">Get help via email</p>
                        </a>
                        <a
                            href="https://github.com/auditorgeo/issues"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors text-center"
                        >
                            <p className="font-medium">GitHub Issues</p>
                            <p className="text-sm text-white/60">Report bugs & features</p>
                        </a>
                        <a
                            href="#"
                            className="p-4 bg-white/5 rounded-xl hover:bg-white/10 transition-colors text-center"
                        >
                            <p className="font-medium">Community</p>
                            <p className="text-sm text-white/60">Join our Discord</p>
                        </a>
                    </div>
                </div>

                {/* Content Sections */}
                <div className="mt-16 space-y-16">
                    <section id="intro" className="scroll-mt-24">
                        <h2 className="text-2xl font-bold mb-4">Introduction to GEO</h2>
                        <div className="prose prose-invert max-w-none">
                            <p className="text-white/80 leading-relaxed">
                                <strong>Generative Engine Optimization (GEO)</strong> is the practice of optimizing your
                                digital content to be accurately represented and cited by AI-powered search engines
                                and assistants like ChatGPT, Perplexity, Google SGE, and Bing Chat.
                            </p>
                            <p className="text-white/80 leading-relaxed mt-4">
                                Unlike traditional SEO which focuses on ranking in search results, GEO ensures your
                                brand, products, and services are correctly understood and recommended by AI systems
                                when users ask questions.
                            </p>
                            <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl">
                                <p className="text-blue-400 font-medium">Key Insight</p>
                                <p className="text-white/80 mt-2">
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
                            <div className="flex gap-4 p-4 bg-white/5 rounded-xl">
                                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    1
                                </div>
                                <div>
                                    <h3 className="font-medium">Enter your website URL</h3>
                                    <p className="text-white/60 text-sm mt-1">
                                        Go to the homepage and paste your website URL in the search bar.
                                    </p>
                                </div>
                            </div>
                            <div className="flex gap-4 p-4 bg-white/5 rounded-xl">
                                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    2
                                </div>
                                <div>
                                    <h3 className="font-medium">Wait for the analysis</h3>
                                    <p className="text-white/60 text-sm mt-1">
                                        Our AI crawls your site, analyzes content, and compares with competitors.
                                    </p>
                                </div>
                            </div>
                            <div className="flex gap-4 p-4 bg-white/5 rounded-xl">
                                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    3
                                </div>
                                <div>
                                    <h3 className="font-medium">Review your GEO Score</h3>
                                    <p className="text-white/60 text-sm mt-1">
                                        Get actionable insights and a prioritized fix plan to improve your visibility.
                                    </p>
                                </div>
                            </div>
                            <div className="flex gap-4 p-4 bg-white/5 rounded-xl">
                                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    4
                                </div>
                                <div>
                                    <h3 className="font-medium">Auto-fix with GitHub</h3>
                                    <p className="text-white/60 text-sm mt-1">
                                        Connect your repository and let AI automatically create pull requests with fixes.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </section>

                    <section id="score" className="scroll-mt-24">
                        <h2 className="text-2xl font-bold mb-4">Understanding Your GEO Score</h2>
                        <p className="text-white/80 mb-6">
                            Your GEO Score is calculated from multiple factors that influence how AI systems
                            understand and represent your content:
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="p-4 bg-white/5 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-green-500 rounded-full" />
                                    <span className="font-medium">Content Quality</span>
                                </div>
                                <p className="text-white/60 text-sm">
                                    Clear, authoritative content with proper structure and headings.
                                </p>
                            </div>
                            <div className="p-4 bg-white/5 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-blue-500 rounded-full" />
                                    <span className="font-medium">Schema Markup</span>
                                </div>
                                <p className="text-white/60 text-sm">
                                    Structured data that helps AI understand your content.
                                </p>
                            </div>
                            <div className="p-4 bg-white/5 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-purple-500 rounded-full" />
                                    <span className="font-medium">E-E-A-T Signals</span>
                                </div>
                                <p className="text-white/60 text-sm">
                                    Experience, Expertise, Authoritativeness, and Trustworthiness.
                                </p>
                            </div>
                            <div className="p-4 bg-white/5 rounded-xl">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-3 h-3 bg-yellow-500 rounded-full" />
                                    <span className="font-medium">Technical SEO</span>
                                </div>
                                <p className="text-white/60 text-sm">
                                    Meta tags, performance, and crawlability factors.
                                </p>
                            </div>
                        </div>
                    </section>
                </div>
            </main>

            {/* Footer */}
            <footer className="border-t border-white/5 mt-20 py-8">
                <div className="max-w-6xl mx-auto px-6 text-center text-white/40 text-sm">
                    © 2024 Auditor GEO. Documentation is continuously updated.
                </div>
            </footer>
        </div>
    )
}
