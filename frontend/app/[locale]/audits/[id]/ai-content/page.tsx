'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { AIContentSuggestion } from '@/lib/types'
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
        <div className="container mx-auto p-6 space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">AI Content Strategy</h1>
                    <p className="text-muted-foreground">Generate content gaps, FAQs, and outlines to improve topical authority.</p>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Generate Suggestions</CardTitle>
                    <CardDescription>Analyze your domain against specific topics using AI.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Domain</label>
                            <Input
                                placeholder="example.com"
                                value={domain}
                                onChange={e => setDomain(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Target Topics (comma separated)</label>
                            <Input
                                placeholder="e.g. cloud computing, devops"
                                value={topics}
                                onChange={e => setTopics(e.target.value)}
                            />
                        </div>
                    </div>
                    <Button onClick={handleGenerate} disabled={loading} className="w-full md:w-auto">
                        {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing Content...</> : <><Sparkles className="mr-2 h-4 w-4" /> Generate Strategy</>}
                    </Button>
                    {error && <p className="text-red-500 text-sm">{error}</p>}
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {suggestions.map((sug) => (
                    <Card key={sug.id} className="flex flex-col">
                        <CardHeader>
                            <div className="flex justify-between items-start">
                                <Badge variant={sug.priority === 'high' || sug.priority === 'critical' ? 'destructive' : 'secondary'}>
                                    {sug.priority.toUpperCase()}
                                </Badge>
                                <Badge variant="outline">{sug.suggestion_type}</Badge>
                            </div>
                            <CardTitle className="mt-2 text-xl">
                                {sug.suggestion_type === 'new_content' && <FileText className="inline mr-2 h-5 w-5 text-blue-500" />}
                                {sug.suggestion_type === 'faq' && <HelpCircle className="inline mr-2 h-5 w-5 text-orange-500" />}
                                {sug.content_outline?.title || sug.content_outline?.question || sug.topic}
                            </CardTitle>
                            <CardDescription>Topic: {sug.topic}</CardDescription>
                        </CardHeader>
                        <CardContent className="flex-grow">
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
                                    <p className="text-sm text-muted-foreground bg-muted p-3 rounded-md">
                                        {sug.content_outline.answer}
                                    </p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
