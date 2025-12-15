'use client'

import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
    Check, Zap, Building2, Sparkles,
    Globe, GitBranch, BarChart3, Shield, Clock
} from 'lucide-react'

const plans = [
    {
        name: 'Free',
        price: '$0',
        period: 'forever',
        description: 'Perfect for trying out Auditor GEO',
        badge: null,
        features: [
            '3 audits per month',
            'Basic GEO Score',
            '1 competitor analysis',
            'Email support',
            'Community access',
        ],
        notIncluded: [
            'GitHub Auto-Fix',
            'PageSpeed Insights',
            'API access',
            'Custom reports',
        ],
        cta: 'Get Started',
        ctaStyle: 'bg-white/10 text-white hover:bg-white/20',
        popular: false,
    },
    {
        name: 'Pro',
        price: '$49',
        period: 'per month',
        description: 'For agencies and growing businesses',
        badge: 'Most Popular',
        features: [
            'Unlimited audits',
            'Advanced GEO Score',
            '5 competitor analysis',
            'GitHub Auto-Fix',
            'PageSpeed Insights',
            'LLM Visibility tracking',
            'Priority support',
            'Custom reports',
        ],
        notIncluded: [
            'API access',
            'White-label reports',
        ],
        cta: 'Start Free Trial',
        ctaStyle: 'bg-gradient-to-r from-blue-500 to-purple-500 text-white hover:opacity-90',
        popular: true,
    },
    {
        name: 'Enterprise',
        price: 'Custom',
        period: 'contact us',
        description: 'For large teams and custom needs',
        badge: null,
        features: [
            'Everything in Pro',
            'Unlimited competitors',
            'API access',
            'White-label reports',
            'SSO authentication',
            'Dedicated support',
            'Custom integrations',
            'SLA guarantee',
        ],
        notIncluded: [],
        cta: 'Contact Sales',
        ctaStyle: 'bg-white/10 text-white hover:bg-white/20',
        popular: false,
    },
]

const faqs = [
    {
        q: 'What is GEO and why do I need it?',
        a: 'GEO (Generative Engine Optimization) ensures your content is accurately represented by AI assistants like ChatGPT and Perplexity. With 43% of consumers using AI for research, GEO is becoming essential.',
    },
    {
        q: 'Can I cancel anytime?',
        a: 'Yes! You can cancel your subscription at any time. You\'ll continue to have access until the end of your billing period.',
    },
    {
        q: 'What payment methods do you accept?',
        a: 'We accept all major credit cards (Visa, MasterCard, American Express) and PayPal. Enterprise customers can pay via invoice.',
    },
    {
        q: 'Do you offer refunds?',
        a: 'Yes, we offer a 14-day money-back guarantee. If you\'re not satisfied, contact us for a full refund.',
    },
]

export default function PricingPage() {
    return (
        <div className="min-h-screen bg-black text-white">
            <Header />

            <main className="max-w-6xl mx-auto px-6 py-16">
                {/* Hero */}
                <div className="text-center mb-16">
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-green-500/10 border border-green-500/20 rounded-full text-green-400 text-sm mb-6">
                        <Sparkles className="w-4 h-4" />
                        Simple, transparent pricing
                    </div>
                    <h1 className="text-4xl md:text-5xl font-bold mb-4">
                        Choose your plan
                    </h1>
                    <p className="text-xl text-white/60 max-w-2xl mx-auto">
                        Start free and scale as you grow. No hidden fees, no surprises.
                    </p>
                </div>

                {/* Pricing Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-20">
                    {plans.map((plan) => (
                        <div
                            key={plan.name}
                            className={`relative p-8 rounded-2xl border transition-all ${plan.popular
                                    ? 'bg-gradient-to-b from-blue-500/10 to-purple-500/10 border-blue-500/30 shadow-lg shadow-blue-500/10'
                                    : 'bg-white/5 border-white/10 hover:border-white/20'
                                }`}
                        >
                            {plan.badge && (
                                <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-blue-500 to-purple-500 text-white border-0">
                                    {plan.badge}
                                </Badge>
                            )}

                            <div className="mb-6">
                                <h2 className="text-xl font-bold mb-2">{plan.name}</h2>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-4xl font-bold">{plan.price}</span>
                                    <span className="text-white/60">/{plan.period}</span>
                                </div>
                                <p className="text-white/60 mt-2">{plan.description}</p>
                            </div>

                            <button
                                className={`w-full py-3 rounded-xl font-medium transition-all ${plan.ctaStyle}`}
                            >
                                {plan.cta}
                            </button>

                            <div className="mt-8 space-y-3">
                                {plan.features.map((feature) => (
                                    <div key={feature} className="flex items-center gap-3">
                                        <Check className="w-5 h-5 text-green-400 flex-shrink-0" />
                                        <span className="text-white/80">{feature}</span>
                                    </div>
                                ))}
                                {plan.notIncluded.map((feature) => (
                                    <div key={feature} className="flex items-center gap-3 opacity-50">
                                        <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                                            <div className="w-1.5 h-0.5 bg-white/40 rounded" />
                                        </div>
                                        <span className="text-white/40">{feature}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Features Comparison */}
                <div className="mb-20">
                    <h2 className="text-2xl font-bold text-center mb-8">
                        Why choose Auditor GEO?
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                        <div className="p-6 bg-white/5 border border-white/10 rounded-2xl text-center">
                            <Globe className="w-8 h-8 text-blue-400 mx-auto mb-4" />
                            <h3 className="font-semibold mb-2">GEO Focused</h3>
                            <p className="text-sm text-white/60">
                                The only tool built specifically for AI search optimization
                            </p>
                        </div>
                        <div className="p-6 bg-white/5 border border-white/10 rounded-2xl text-center">
                            <GitBranch className="w-8 h-8 text-purple-400 mx-auto mb-4" />
                            <h3 className="font-semibold mb-2">Auto-Fix</h3>
                            <p className="text-sm text-white/60">
                                Automatically fix issues with GitHub integration
                            </p>
                        </div>
                        <div className="p-6 bg-white/5 border border-white/10 rounded-2xl text-center">
                            <BarChart3 className="w-8 h-8 text-green-400 mx-auto mb-4" />
                            <h3 className="font-semibold mb-2">Competitor Intel</h3>
                            <p className="text-sm text-white/60">
                                Compare your GEO score with competitors
                            </p>
                        </div>
                        <div className="p-6 bg-white/5 border border-white/10 rounded-2xl text-center">
                            <Clock className="w-8 h-8 text-yellow-400 mx-auto mb-4" />
                            <h3 className="font-semibold mb-2">Fast Results</h3>
                            <p className="text-sm text-white/60">
                                Get actionable insights in minutes, not days
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
                                className="p-6 bg-white/5 border border-white/10 rounded-2xl"
                            >
                                <h3 className="font-semibold mb-2">{faq.q}</h3>
                                <p className="text-white/60">{faq.a}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* CTA */}
                <div className="mt-20 text-center p-12 bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/10 rounded-2xl">
                    <h2 className="text-3xl font-bold mb-4">
                        Ready to optimize for the AI era?
                    </h2>
                    <p className="text-white/60 mb-8 max-w-xl mx-auto">
                        Start your free trial today. No credit card required.
                    </p>
                    <a
                        href="/"
                        className="inline-flex items-center gap-2 px-8 py-4 bg-white text-black rounded-xl font-semibold hover:bg-white/90 transition-colors"
                    >
                        <Zap className="w-5 h-5" />
                        Start Free Audit
                    </a>
                </div>
            </main>

            {/* Footer */}
            <footer className="border-t border-white/5 mt-20 py-8">
                <div className="max-w-6xl mx-auto px-6 text-center text-white/40 text-sm">
                    © 2024 Auditor GEO. All prices in USD.
                </div>
            </footer>
        </div>
    )
}
