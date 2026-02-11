'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { LLMVisibility } from '@/lib/types'
import { Header } from '@/components/header'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Loader2, CheckCircle, XCircle, Search } from 'lucide-react'

export default function LLMVisibilityPage() {
    const params = useParams()
    const auditId = params.id as string

    const [brandName, setBrandName] = useState('')
    const [queries, setQueries] = useState('')
    const [loading, setLoading] = useState(false)
    const [results, setResults] = useState<LLMVisibility[]>([])
    const [error, setError] = useState('')

    const loadData = useCallback(async () => {
        try {
            const data = await api.getLLMVisibility(auditId)
            setResults(data)
        } catch (e) {
            console.error(e)
        }
    }, [auditId])

    useEffect(() => {
        loadData()
    }, [loadData])

    async function handleCheck() {
        if (!brandName || !queries) return

        setLoading(true)
        setError('')

        try {
            const queryList = queries.split(',').map(q => q.trim()).filter(q => q)
            const newResults = await api.checkLLMVisibility(auditId, brandName, queryList)
            setResults(prev => [...newResults, ...prev])
        } catch (e) {
            setError('Failed to check visibility. Ensure OpenAI/Gemini keys are set.')
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
                        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">LLM Visibility Tracker</h1>
                        <p className="text-muted-foreground mt-2">
                            Monitor your brand&apos;s presence across AI search results and model recommendations.
                        </p>
                    </div>
                </div>

                <Card className="glass-card">
                    <CardHeader>
                        <CardTitle className="text-lg font-medium">Check Visibility</CardTitle>
                        <CardDescription>Enter your brand name and queries to check if you are recommended by AI.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Brand Name</label>
                                <Input
                                    className="glass-input"
                                    placeholder="e.g. Acme Corp"
                                    value={brandName}
                                    onChange={e => setBrandName(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Queries (comma separated)</label>
                                <Input
                                    className="glass-input"
                                    placeholder="e.g. best seo tools, top marketing agencies"
                                    value={queries}
                                    onChange={e => setQueries(e.target.value)}
                                />
                            </div>
                        </div>
                        <Button onClick={handleCheck} disabled={loading} className="w-full md:w-auto glass-button-primary">
                            {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Checking AI Models...</> : <><Search className="mr-2 h-4 w-4" /> Check Visibility</>}
                        </Button>
                        {error && <p className="text-destructive text-sm">{error}</p>}
                    </CardContent>
                </Card>

                <div className="grid grid-cols-1 gap-4">
                    {results.map((result) => (
                        <Card key={result.id} className="glass-card overflow-hidden">
                            <div className={`h-1 w-full ${result.is_visible ? 'bg-brand' : 'bg-muted-foreground/30'}`} />
                            <CardContent className="p-6">
                                <div className="flex flex-wrap items-start justify-between gap-4">
                                    <div>
                                        <div className="flex items-center gap-2 mb-2">
                                            <Badge variant="outline">{result.llm_name}</Badge>
                                            <Badge variant="outline" className="text-muted-foreground">
                                                #{result.id}
                                            </Badge>
                                            <span className="text-sm text-muted-foreground">
                                                {new Date(result.checked_at).toLocaleString()}
                                            </span>
                                        </div>
                                        <h3 className="text-lg font-semibold mb-1">Query: &quot;{result.query}&quot;</h3>
                                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                                            {result.is_visible ? (
                                                <Badge variant="outline" className="bg-brand text-brand-foreground border-brand">
                                                    <CheckCircle className="w-3 h-3 mr-1" /> Visible
                                                </Badge>
                                            ) : (
                                                <Badge variant="outline" className="text-muted-foreground border-border">
                                                    <XCircle className="w-3 h-3 mr-1" /> Not Visible
                                                </Badge>
                                            )}
                                            {result.rank !== undefined && result.rank !== null && (
                                                <Badge variant="secondary">Rank #{result.rank}</Badge>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                {result.citation_text && (
                                    <div className="mt-4 p-4 glass-panel rounded-lg border border-border text-sm italic text-foreground">
                                        &quot;{result.citation_text}&quot;
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                    {results.length === 0 && !loading && (
                        <div className="text-center py-12 text-muted-foreground">
                            No visibility checks performed yet.
                        </div>
                    )}
                </div>
            </main>
        </div>
    )
}
