'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Header } from '@/components/header';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Github, GitPullRequest, CheckCircle2, XCircle, Clock, ExternalLink, ArrowLeft, AlertCircle } from 'lucide-react';
import { API_URL } from '@/lib/api';
import { fetchWithBackendAuth } from '@/lib/backend-auth';

export default function GitHubAutoFixPage() {
    const params = useParams();
    const router = useRouter();
    const auditId = params.id as string;

    const [audit, setAudit] = useState<any>(null);
    const [connections, setConnections] = useState<any[]>([]);
    const [repositories, setRepositories] = useState<any[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<string | null>(null);
    const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [reposLoading, setReposLoading] = useState(false);
    const [creating, setCreating] = useState(false);
    const [prResult, setPrResult] = useState<any>(null);

    const backendUrl = API_URL;

    useEffect(() => {
        fetchAudit();
        fetchConnections();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const fetchAudit = async () => {
        try {
            const res = await fetchWithBackendAuth(`${backendUrl}/api/audits/${auditId}`);
            if (res.ok) {
                const data = await res.json();
                setAudit(data);
            }
        } catch (err) {
            console.error('Error fetching audit:', err);
        } finally {
            setLoading(false);
        }
    };

    const fetchConnections = async () => {
        try {
            const res = await fetchWithBackendAuth(`${backendUrl}/api/github/connections`);
            if (res.ok) {
                const data = await res.json();
                setConnections(data);
                if (data.length > 0) {
                    setSelectedConnection(data[0].id);
                    fetchRepositories(data[0].id);
                }
            }
        } catch (err) {
            console.error('Error fetching connections:', err);
        }
    };

    const fetchRepositories = async (connectionId: string) => {
        setReposLoading(true);
        try {
            const res = await fetchWithBackendAuth(`${backendUrl}/api/github/repos/${connectionId}`);
            if (res.ok) {
                const data = await res.json();
                setRepositories(data);
            }
        } catch (err) {
            console.error('Error fetching repositories:', err);
        } finally {
            setReposLoading(false);
        }
    };

    const handleConnectionChange = (connectionId: string) => {
        setSelectedConnection(connectionId);
        setSelectedRepo(null);
        fetchRepositories(connectionId);
    };

    const createAutoFixPR = async () => {
        if (!selectedConnection || !selectedRepo) return;

        setCreating(true);
        setPrResult(null);

        try {
            const res = await fetchWithBackendAuth(
                `${backendUrl}/api/github/create-auto-fix-pr/${selectedConnection}/${selectedRepo}`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ audit_id: parseInt(auditId) }),
                }
            );

            const data = await res.json();

            if (res.ok) {
                setPrResult({ success: true, data });
            } else {
                setPrResult({ success: false, error: data.detail || 'Error creating PR' });
            }
        } catch (err: any) {
            setPrResult({ success: false, error: err.message });
        } finally {
            setCreating(false);
        }
    };

    const connectGitHub = () => {
        window.location.href = `${backendUrl}/api/github/oauth/authorize`;
    };

    if (loading) {
        return (
            <div className="flex min-h-screen flex-col">
                <Header />
                <main className="flex-1 flex items-center justify-center">
                    <Clock className="h-8 w-8 animate-spin text-muted-foreground" />
                </main>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen flex-col pb-20 bg-background text-foreground">
            <Header />

            <main className="flex-1 container mx-auto px-6 py-8">
                {/* Back button */}
                <Button
                    variant="ghost"
                    onClick={() => router.push(`/audits/${auditId}`)}
                    className="mb-8 text-muted-foreground hover:text-foreground hover:bg-muted/50 pl-0"
                >
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back to Audit
                </Button>

                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-3xl md:text-4xl font-semibold tracking-tight mb-2">GitHub Auto-Fix</h1>
                    <p className="text-muted-foreground">
                        Automatically create a Pull Request with AI-powered SEO/GEO fixes for your repository
                    </p>
                </div>

                {/* No GitHub connection */}
                {connections.length === 0 && (
                    <Card className="glass-card p-12 border border-border text-center">
                        <div className="max-w-md mx-auto">
                            <div className="mb-6 flex justify-center">
                                <div className="p-6 rounded-full bg-brand/10">
                                    <Github className="h-12 w-12 text-brand" />
                                </div>
                            </div>
                            <h2 className="text-2xl font-semibold text-foreground mb-4">Connect GitHub</h2>
                            <p className="text-muted-foreground mb-8">
                                To use Auto-Fix, you need to connect your GitHub account. We&apos;ll create Pull Requests with
                                AI-generated fixes for all detected SEO/GEO issues.
                            </p>
                            <Button onClick={connectGitHub} className="bg-brand text-brand-foreground hover:bg-brand/90 px-8 py-6 text-lg">
                                <Github className="h-5 w-5 mr-2" />
                                Connect GitHub Account
                            </Button>
                        </div>
                    </Card>
                )}

                {/* GitHub connected */}
                {connections.length > 0 && (
                    <div className="space-y-6">
                        {/* Connection Info */}
                        <Card className="glass-card p-6 border border-border">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="p-3 rounded-lg bg-emerald-500/10">
                                        <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-semibold text-foreground">GitHub Connected</h3>
                                        <p className="text-sm text-muted-foreground">
                                            You&apos;re connected as <span className="text-foreground font-medium">{connections[0].github_username}</span>
                                        </p>
                                    </div>
                                </div>
                                <Badge className="border-emerald-500/30 text-emerald-600 bg-emerald-500/10">
                                    Active
                                </Badge>
                            </div>
                        </Card>

                        {/* Configuration */}
                        <Card className="glass-card p-8 border border-border">
                            <h3 className="text-xl font-semibold text-foreground mb-6">Configure Auto-Fix</h3>

                            <div className="space-y-6">
                                {/* Connection Selector */}
                                <div>
                                    <label className="block text-sm font-medium text-muted-foreground mb-3">
                                        GitHub Account
                                    </label>
                                    <select
                                        value={selectedConnection || ''}
                                        onChange={(e) => handleConnectionChange(e.target.value)}
                                        className="glass-input w-full px-4 py-3"
                                    >
                                        {connections.map((conn) => (
                                            <option key={conn.id} value={conn.id} className="bg-gray-900">
                                                {conn.github_username}
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                {/* Repository Selector */}
                                <div>
                                    <label className="block text-sm font-medium text-muted-foreground mb-3">
                                        Target Repository
                                    </label>
                                    {reposLoading ? (
                                        <div className="flex items-center gap-2 text-muted-foreground py-3">
                                            <Clock className="h-4 w-4 animate-spin" />
                                            Loading repositories...
                                        </div>
                                    ) : repositories.length === 0 ? (
                                        <div className="flex items-center gap-2 text-muted-foreground py-3">
                                            <AlertCircle className="h-4 w-4" />
                                            No repositories found. Please sync your repositories first.
                                        </div>
                                    ) : (
                                        <select
                                            value={selectedRepo || ''}
                                            onChange={(e) => setSelectedRepo(e.target.value)}
                                            className="glass-input w-full px-4 py-3"
                                        >
                                            <option value="" className="bg-gray-900">Select a repository...</option>
                                            {repositories.map((repo) => (
                                                <option key={repo.id} value={repo.id} className="bg-gray-900">
                                                    {repo.full_name} ({repo.site_type || 'unknown'})
                                                </option>
                                            ))}
                                        </select>
                                    )}
                                </div>

                                {/* What will be fixed */}
                                {audit && (
                                    <div className="glass-panel border border-border rounded-xl p-6">
                                        <h4 className="text-sm font-semibold text-foreground mb-4">What will be fixed:</h4>
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                            <div className="bg-muted/50 p-4 rounded-lg border border-border">
                                                <div className="text-2xl font-bold text-red-500 mb-1">{audit.critical_issues || 0}</div>
                                                <div className="text-xs text-muted-foreground">Critical Issues</div>
                                            </div>
                                            <div className="bg-muted/50 p-4 rounded-lg border border-border">
                                                <div className="text-2xl font-bold text-orange-500 mb-1">{audit.high_issues || 0}</div>
                                                <div className="text-xs text-muted-foreground">High Priority Issues</div>
                                            </div>
                                            <div className="bg-muted/50 p-4 rounded-lg border border-border">
                                                <div className="text-2xl font-bold text-amber-500 mb-1">{audit.medium_issues || 0}</div>
                                                <div className="text-xs text-muted-foreground">Medium Priority Issues</div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Create PR Button */}
                                <Button
                                    onClick={createAutoFixPR}
                                    disabled={!selectedRepo || creating}
                                    className="w-full bg-brand text-brand-foreground hover:bg-brand/90 py-6 text-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {creating ? (
                                        <>
                                            <Clock className="h-5 w-5 mr-2 animate-spin" />
                                            Creating Pull Request...
                                        </>
                                    ) : (
                                        <>
                                            <GitPullRequest className="h-5 w-5 mr-2" />
                                            Create Auto-Fix Pull Request
                                        </>
                                    )}
                                </Button>
                            </div>
                        </Card>

                        {/* Result */}
                        {prResult && (
                            <Card
                                className={`p-6 border ${prResult.success
                                    ? 'bg-emerald-500/10 border-emerald-500/30'
                                    : 'bg-red-500/10 border-red-500/30'
                                    }`}
                            >
                                {prResult.success ? (
                                    <div className="space-y-4">
                                        <div className="flex items-center gap-3">
                                            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                                            <div>
                                                <h3 className="text-xl font-bold text-emerald-600">Pull Request Created Successfully!</h3>
                                                <p className="text-muted-foreground mt-1">
                                                    {prResult.data.files_modified} files modified with {prResult.data.fixes_applied} AI-powered fixes
                                                </p>
                                            </div>
                                        </div>

                                        {prResult.data.pr?.html_url && (
                                            <div className="pt-4 border-t border-border/70">
                                                <Button
                                                    onClick={() => window.open(prResult.data.pr.html_url, '_blank')}
                                                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                                                >
                                                    <ExternalLink className="h-4 w-4 mr-2" />
                                                    View Pull Request on GitHub
                                                </Button>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex items-start gap-3">
                                        <XCircle className="h-8 w-8 text-red-500 flex-shrink-0 mt-1" />
                                        <div>
                                            <h3 className="text-xl font-bold text-red-500 mb-2">Error Creating Pull Request</h3>
                                            <p className="text-muted-foreground">{prResult.error}</p>
                                        </div>
                                    </div>
                                )}
                            </Card>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}
