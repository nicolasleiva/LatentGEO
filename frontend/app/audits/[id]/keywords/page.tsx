'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { Keyword } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Loader2, Search, TrendingUp, DollarSign, Target } from 'lucide-react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export default function KeywordsPage() {
    const params = useParams()
    const auditId = params.id as string

    const [domain, setDomain] = useState('')
    const [seeds, setSeeds] = useState('')
    const [loading, setLoading] = useState(false)
    const [keywords, setKeywords] = useState<Keyword[]>([])
    const [error, setError] = useState('')

    const loadData = useCallback(async () => {
        try {
            const data = await api.getKeywords(auditId)
            setKeywords(data)
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

    async function handleResearch() {
        if (!domain) return

        setLoading(true)
        setError('')

        try {
            const seedList = seeds ? seeds.split(',').map(s => s.trim()).filter(s => s) : []
            const newKeywords = await api.researchKeywords(auditId, domain, seedList)
            setKeywords(prev => [...newKeywords, ...prev])
        } catch (e) {
            setError('Failed to research keywords. Ensure OpenAI/Gemini key is set.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="container mx-auto p-6 space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Semantic Keyword Research</h1>
                    <p className="text-muted-foreground">Discover high-intent keywords using AI analysis of your niche.</p>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Research Parameters</CardTitle>
                    <CardDescription>Enter seeds to guide the AI, or leave empty for broad discovery.</CardDescription>
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
                            <label className="text-sm font-medium">Seed Keywords (Optional)</label>
                            <Input
                                placeholder="e.g. software, saas"
                                value={seeds}
                                onChange={e => setSeeds(e.target.value)}
                            />
                        </div>
                    </div>
                    <Button onClick={handleResearch} disabled={loading} className="w-full md:w-auto">
                        {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Researching...</> : <><Search className="mr-2 h-4 w-4" /> Find Keywords</>}
                    </Button>
                    {error && <p className="text-red-500 text-sm">{error}</p>}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Keyword Opportunities ({keywords.length})</CardTitle>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Keyword</TableHead>
                                <TableHead>Intent</TableHead>
                                <TableHead>Volume (Est)</TableHead>
                                <TableHead>Difficulty</TableHead>
                                <TableHead>CPC</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {keywords.map((kw) => (
                                <TableRow key={kw.id}>
                                    <TableCell className="font-medium">{kw.term}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className={
                                            kw.intent.toLowerCase().includes('commercial') ? 'bg-blue-50 text-blue-700' :
                                                kw.intent.toLowerCase().includes('transactional') ? 'bg-green-50 text-green-700' :
                                                    'bg-gray-50'
                                        }>
                                            {kw.intent}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>{kw.volume.toLocaleString()}</TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-2">
                                            <div className="w-16 h-2 bg-gray-100 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full ${kw.difficulty > 70 ? 'bg-red-500' : kw.difficulty > 40 ? 'bg-yellow-500' : 'bg-green-500'}`}
                                                    style={{ width: `${kw.difficulty}%` }}
                                                />
                                            </div>
                                            <span className="text-xs text-muted-foreground">{kw.difficulty}/100</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>${kw.cpc.toFixed(2)}</TableCell>
                                </TableRow>
                            ))}
                            {keywords.length === 0 && !loading && (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                                        No keywords found. Start a research session.
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    )
}
