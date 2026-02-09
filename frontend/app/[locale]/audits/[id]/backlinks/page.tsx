'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { Backlink } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Loader2, Link as LinkIcon, ExternalLink, Network, Globe, ThumbsUp, ThumbsDown, Minus } from 'lucide-react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export default function BacklinksPage() {
    const params = useParams()
    const auditId = params.id as string

    const [domain, setDomain] = useState('')
    const [loading, setLoading] = useState(false)
    const [backlinks, setBacklinks] = useState<Backlink[]>([])
    const [error, setError] = useState('')

    const loadData = useCallback(async () => {
        try {
            const data = await api.getBacklinks(auditId)
            setBacklinks(data)
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

    async function handleAnalyze() {
        if (!domain) return

        setLoading(true)
        setError('')

        try {
            await api.analyzeBacklinks(auditId, domain)
            const allBacklinks = await api.getBacklinks(auditId)
            setBacklinks(allBacklinks)
        } catch (e) {
            setError('Failed to analyze links.')
        } finally {
            setLoading(false)
        }
    }

    const internalLinks = backlinks.filter(bl => bl.source_url === 'INTERNAL_NETWORK')
    const technicalBacklinks = backlinks.filter(bl => bl.source_url === 'TECHNICAL_BACKLINK')
    const brandMentions = backlinks.filter(bl => bl.source_url === 'BRAND_MENTION')

    function parseMentionAnalysis(anchorText: string) {
        try {
            return JSON.parse(anchorText)
        } catch {
            return {
                sentiment: 'neutral',
                topic: 'Unknown',
                snippet: anchorText,
                recommendation: 'N/A',
                relevance_score: 0
            }
        }
    }

    function getSentimentIcon(sentiment: string) {
        if (sentiment === 'positive') return <ThumbsUp className="h-4 w-4 text-foreground" />
        if (sentiment === 'negative') return <ThumbsDown className="h-4 w-4 text-muted-foreground" />
        return <Minus className="h-4 w-4 text-muted-foreground/50" />
    }

    return (
        <div className="container mx-auto p-6 space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Link & Mention Analysis</h1>
                    <p className="text-muted-foreground">Internal structure, technical backlinks, and AI-powered brand analysis.</p>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Start Analysis</CardTitle>
                    <CardDescription>Comprehensive analysis of all link types and brand mentions.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex gap-4">
                        <Input
                            placeholder="example.com"
                            value={domain}
                            onChange={e => setDomain(e.target.value)}
                            className="max-w-md"
                        />
                        <Button onClick={handleAnalyze} disabled={loading}>
                            {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing...</> : <><Network className="mr-2 h-4 w-4" /> Analyze All</>}
                        </Button>
                    </div>
                    {error && <p className="text-red-500 text-sm">{error}</p>}
                </CardContent>
            </Card>

            <Tabs defaultValue="internal" className="w-full">
                <TabsList>
                    <TabsTrigger value="internal">Internal Structure ({internalLinks.length})</TabsTrigger>
                    <TabsTrigger value="technical">Technical Backlinks ({technicalBacklinks.length})</TabsTrigger>
                    <TabsTrigger value="mentions">Brand Mentions ({brandMentions.length})</TabsTrigger>
                </TabsList>

                <TabsContent value="internal">
                    <Card>
                        <CardHeader>
                            <CardTitle>Top Internal Pages</CardTitle>
                            <CardDescription>Pages with the most internal incoming links.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Target Page</TableHead>
                                        <TableHead>Source</TableHead>
                                        <TableHead>Link Count</TableHead>
                                        <TableHead>Type</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {internalLinks.map((bl) => (
                                        <TableRow key={bl.id}>
                                            <TableCell className="font-medium break-all">{bl.target_url}</TableCell>
                                            <TableCell><Badge variant="secondary">Internal Network</Badge></TableCell>
                                            <TableCell>{bl.anchor_text}</TableCell>
                                            <TableCell>
                                                <Badge variant="outline" className="text-green-600 border-green-200">Dofollow</Badge>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                    {internalLinks.length === 0 && !loading && (
                                        <TableRow>
                                            <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                                                No internal link data found.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="technical">
                    <Card>
                        <CardHeader>
                            <CardTitle>Technical Backlinks</CardTitle>
                            <CardDescription>External pages linking to your domain (link: operator).</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Source Page</TableHead>
                                        <TableHead>Title</TableHead>
                                        <TableHead>Platform</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {technicalBacklinks.map((bl) => (
                                        <TableRow key={bl.id}>
                                            <TableCell className="font-medium break-all">
                                                <a href={bl.target_url} target="_blank" rel="noopener noreferrer" className="flex items-center hover:underline text-blue-600">
                                                    {bl.target_url} <ExternalLink className="ml-1 h-3 w-3" />
                                                </a>
                                            </TableCell>
                                            <TableCell>{bl.anchor_text}</TableCell>
                                            <TableCell>
                                                <Badge variant="outline">{new URL(bl.target_url).hostname}</Badge>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                    {technicalBacklinks.length === 0 && !loading && (
                                        <TableRow>
                                            <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                                                No technical backlinks found.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="mentions">
                    <Card>
                        <CardHeader>
                            <CardTitle>Brand Mentions (GEO Analysis)</CardTitle>
                            <CardDescription>AI-powered analysis of brand citations with sentiment and context.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                {brandMentions.map((bl) => {
                                    const analysis = parseMentionAnalysis(bl.anchor_text)
                                    return (
                                        <div key={bl.id} className="border rounded-lg p-4 space-y-2">
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1">
                                                    <a href={bl.target_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-medium flex items-center">
                                                        {new URL(bl.target_url).hostname} <ExternalLink className="ml-1 h-3 w-3" />
                                                    </a>
                                                    <p className="text-sm text-muted-foreground mt-1">{bl.target_url}</p>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {getSentimentIcon(analysis.sentiment)}
                                                    <Badge variant={analysis.sentiment === 'positive' ? 'default' : analysis.sentiment === 'negative' ? 'destructive' : 'secondary'}>
                                                        {analysis.sentiment}
                                                    </Badge>
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div>
                                                    <span className="font-semibold">Topic:</span> {analysis.topic}
                                                </div>
                                                <div>
                                                    <span className="font-semibold">Relevance:</span> {analysis.relevance_score}/100
                                                </div>
                                            </div>
                                            <div className="bg-muted p-3 rounded">
                                                <p className="text-sm"><span className="font-semibold">Context:</span> {analysis.snippet}</p>
                                            </div>
                                            <div className="bg-blue-50 p-3 rounded border-l-4 border-blue-500">
                                                <p className="text-sm"><span className="font-semibold">Recommendation:</span> {analysis.recommendation}</p>
                                            </div>
                                        </div>
                                    )
                                })}
                                {brandMentions.length === 0 && !loading && (
                                    <div className="text-center py-8 text-muted-foreground">
                                        No brand mentions found. Run the analysis to discover citations.
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    )
}
