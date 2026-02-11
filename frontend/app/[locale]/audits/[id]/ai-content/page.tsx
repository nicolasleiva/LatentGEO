'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { AIContentSuggestion } from '@/lib/types'
import { Header } from '@/components/header'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Loader2, Sparkles, FileText, HelpCircle } from 'lucide-react'

export default function AIContentPage() {
    const params = useParams()
    const auditId = params.id as string

    const [domain, setDomain] = useState('')
    const [topics, setTopics] = useState('')
    const [loading, setLoading] = useState(false)
    const [suggestions, setSuggestions] = useState<AIContentSuggestion[]>([])
    const [error, setError] = useState('')

    const loadData = useCallback(async () => {
        try {
            const data = await api.getAIContent(auditId)
            setSuggestions(data)

            // Try to get domain from audit details if available (simplified)
            try {
                const audit = await api.getAudit(auditId)
                if (audit.url) {
                    const url = new URL(audit.url)
                    setDomain(url.hostname)
                }
            } catch { }
        } catch (e) {
            console.error(e)
        }
    }, [auditId])

    useEffect(() => {
        loadData()
    }, [loadData])

    async function handleGenerate() {
        if (!domain || !topics) return

        setLoading(true)
        setError('')

        try {
            const topicList = topics.split(',').map(t => t.trim()).filter(t => t)
            const newSuggestions = await api.generateAIContent(auditId, domain, topicList)
            setSuggestions(prev => [...newSuggestions, ...prev])
        } catch (e) {
            setError('Failed to generate suggestions. Ensure OpenAI/Gemini key is set.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-background text-foreground">
            <Header />
            <main className="max-w-6xl mx-auto px-6 py-12 space-y-8">
                <div className="flex justify-between items-center animate-fade-up">
                    <div>
                        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">AI Content Strategy</h1>
                        <p className="text-muted-foreground mt-2">Generate content gaps, FAQs, and outlines to improve topical authority.</p>
                    </div>
                </div>

                <Card className="glass-card">
                    <CardHeader>
                        <CardTitle>Generate Suggestions</CardTitle>
                        <CardDescription>Analyze your domain against specific topics using AI.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Domain</label>
                                <Input
                                    className="glass-input"
                                    placeholder="example.com"
                                    value={domain}
                                    onChange={e => setDomain(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Target Topics (comma separated)</label>
                                <Input
                                    className="glass-input"
                                    placeholder="e.g. cloud computing, devops"
                                    value={topics}
                                    onChange={e => setTopics(e.target.value)}
                                />
                            </div>
                        </div>
                        <Button onClick={handleGenerate} disabled={loading} className="w-full md:w-auto glass-button-primary">
                            {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing Content...</> : <><Sparkles className="mr-2 h-4 w-4" /> Generate Strategy</>}
                        </Button>
                        {error && <p className="text-red-500 text-sm">{error}</p>}
                    </CardContent>
                </Card>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {suggestions.map((sug) => (
                        <Card key={sug.id} className="glass-card flex flex-col">
                            <CardHeader>
                                <div className="flex flex-wrap justify-between items-start gap-2">
                                    <Badge variant={sug.priority === 'high' || sug.priority === 'critical' ? 'destructive' : 'secondary'}>
                                        {sug.priority.toUpperCase()}
                                    </Badge>
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <Badge variant="outline">{sug.suggestion_type}</Badge>
                                        <Badge variant="outline">#{sug.id}</Badge>
                                        <span>{new Date(sug.created_at).toLocaleDateString()}</span>
                                    </div>
                                </div>
                                <CardTitle className="mt-2 text-xl">
                                    {sug.suggestion_type === 'new_content' && <FileText className="inline mr-2 h-5 w-5 text-brand" />}
                                    {sug.suggestion_type === 'faq' && <HelpCircle className="inline mr-2 h-5 w-5 text-amber-500" />}
                                    {sug.content_outline?.title || sug.content_outline?.question || sug.topic}
                                </CardTitle>
                                <CardDescription>Topic: {sug.topic}</CardDescription>
                                {sug.page_url && (
                                    <p className="text-xs text-muted-foreground mt-2 break-all">Page: {sug.page_url}</p>
                                )}
                            </CardHeader>
                            <CardContent className="flex-grow space-y-3">
                                {sug.suggestion_type === 'new_content' && sug.content_outline?.sections && (
                                    <div className="space-y-2">
                                        <p className="font-semibold text-sm">Suggested Outline:</p>
                                        <ul className="list-disc list-inside text-sm text-muted-foreground">
                                            {sug.content_outline.sections.map((sec: string, i: number) => (
                                                <li key={i}>{sec}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {sug.suggestion_type === 'faq' && sug.content_outline?.answer && (
                                    <div className="space-y-2">
                                        <p className="font-semibold text-sm">Suggested Answer:</p>
                                        <p className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-md border border-border">
                                            {sug.content_outline.answer}
                                        </p>
                                    </div>
                                )}
                                {!['new_content', 'faq'].includes(sug.suggestion_type) && sug.content_outline && (
                                    <div className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-md border border-border font-mono whitespace-pre-wrap">
                                        {JSON.stringify(sug.content_outline, null, 2)}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                    {suggestions.length === 0 && !loading && (
                        <Card className="glass-card p-10 text-center md:col-span-2">
                            <Sparkles className="h-10 w-10 text-muted-foreground/60 mx-auto mb-4" />
                            <h3 className="text-lg font-semibold text-foreground mb-2">No AI suggestions yet</h3>
                            <p className="text-muted-foreground">Generate a strategy to see content opportunities and outlines.</p>
                        </Card>
                    )}
                </div>
            </main>
        </div>
    )
}
