'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Header } from '@/components/header';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Github, GitPullRequest, CheckCircle2, XCircle, Clock, ExternalLink, ArrowLeft, AlertCircle } from 'lucide-react';

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

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    useEffect(() => {
        fetchAudit();
        fetchConnections();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const fetchAudit = async () => {
        try {
            const res = await fetch(`${backendUrl}/api/audits/${auditId}`);
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
            const res = await fetch(`${backendUrl}/api/github/connections`);
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
            const res = await fetch(`${backendUrl}/api/github/repositories/${connectionId}`);
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
            const res = await fetch(
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
                    <Clock className="h-8 w-8 animate-spin text-white" />
                </main>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen flex-col pb-20">
            <Header />

            <main className="flex-1 container mx-auto px-6 py-8">
                {/* Back button */}
                <Button
                    variant="ghost"
                    onClick={() => router.push(`/audits/${auditId}`)}
                    className="mb-8 text-white/50 hover:text-white hover:bg-white/10 pl-0"
                >
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back to Audit
                </Button>

                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-white mb-2">GitHub Auto-Fix</h1>
                    <p className="text-white/60">
                        Automatically create a Pull Request with AI-powered SEO/GEO fixes for your repository
                    </p>
                </div>

                {/* No GitHub connection */}
                {connections.length === 0 && (
                    <Card className="glass-card p-12 border-white/10 text-center">
                        <div className="max-w-md mx-auto">
                            <div className="mb-6 flex justify-center">
                                <div className="p-6 rounded-full bg-purple-500/20">
                                    <Github className="h-12 w-12 text-purple-400" />
                                </div>
                            </div>
                            <h2 className="text-2xl font-bold text-white mb-4">Connect GitHub</h2>
                            <p className="text-white/60 mb-8">
                                To use Auto-Fix, you need to connect your GitHub account. We&apos;ll create Pull Requests with
                                AI-generated fixes for all detected SEO/GEO issues.
                            </p>
                            <Button onClick={connectGitHub} className="bg-purple-600 hover:bg-purple-700 text-white px-8 py-6 text-lg">
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
                        <Card className="glass-card p-6 border-white/10">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="p-3 rounded-lg bg-green-500/20">
                                        <CheckCircle2 className="h-6 w-6 text-green-400" />
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-semibold text-white">GitHub Connected</h3>
                                        <p className="text-sm text-white/60">
                                            You&apos;re connected as <span className="text-white font-medium">{connections[0].github_username}</span>
                                        </p>
                                    </div>
                                </div>
                                <Badge className="border-green-500/50 text-green-400 bg-green-500/10">
                                    Active
                                </Badge>
                            </div>
                        </Card>

                        {/* Configuration */}
                        <Card className="glass-card p-8 border-white/10">
                            <h3 className="text-xl font-bold text-white mb-6">Configure Auto-Fix</h3>

                            <div className="space-y-6">
                                {/* Connection Selector */}
                                <div>
                                    <label className="block text-sm font-medium text-white/70 mb-3">
                                        GitHub Account
                                    </label>
                                    <select
                                        value={selectedConnection || ''}
                                        onChange={(e) => handleConnectionChange(e.target.value)}
                                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
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
                                    <label className="block text-sm font-medium text-white/70 mb-3">
                                        Target Repository
                                    </label>
                                    {reposLoading ? (
                                        <div className="flex items-center gap-2 text-white/50 py-3">
                                            <Clock className="h-4 w-4 animate-spin" />
                                            Loading repositories...
                                        </div>
                                    ) : repositories.length === 0 ? (
                                        <div className="flex items-center gap-2 text-white/50 py-3">
                                            <AlertCircle className="h-4 w-4" />
                                            No repositories found. Please sync your repositories first.
                                        </div>
                                    ) : (
                                        <select
                                            value={selectedRepo || ''}
                                            onChange={(e) => setSelectedRepo(e.target.value)}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
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
                                    <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                                        <h4 className="text-sm font-semibold text-white mb-4">What will be fixed:</h4>
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                            <div className="bg-black/20 p-4 rounded-lg">
                                                <div className="text-2xl font-bold text-red-400 mb-1">{audit.critical_issues || 0}</div>
                                                <div className="text-xs text-white/60">Critical Issues</div>
                                            </div>
                                            <div className="bg-black/20 p-4 rounded-lg">
                                                <div className="text-2xl font-bold text-orange-400 mb-1">{audit.high_issues || 0}</div>
                                                <div className="text-xs text-white/60">High Priority Issues</div>
                                            </div>
                                            <div className="bg-black/20 p-4 rounded-lg">
                                                <div className="text-2xl font-bold text-yellow-400 mb-1">{audit.medium_issues || 0}</div>
                                                <div className="text-xs text-white/60">Medium Priority Issues</div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Create PR Button */}
                                <Button
                                    onClick={createAutoFixPR}
                                    disabled={!selectedRepo || creating}
                                    className="w-full bg-purple-600 hover:bg-purple-700 text-white py-6 text-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
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
                                    ? 'bg-green-500/10 border-green-500/50'
                                    : 'bg-red-500/10 border-red-500/50'
                                    }`}
                            >
                                {prResult.success ? (
                                    <div className="space-y-4">
                                        <div className="flex items-center gap-3">
                                            <CheckCircle2 className="h-8 w-8 text-green-400" />
                                            <div>
                                                <h3 className="text-xl font-bold text-green-400">Pull Request Created Successfully!</h3>
                                                <p className="text-white/70 mt-1">
                                                    {prResult.data.files_modified} files modified with {prResult.data.fixes_applied} AI-powered fixes
                                                </p>
                                            </div>
                                        </div>

                                        {prResult.data.pr?.html_url && (
                                            <div className="pt-4 border-t border-white/10">
                                                <Button
                                                    onClick={() => window.open(prResult.data.pr.html_url, '_blank')}
                                                    className="bg-green-600 hover:bg-green-700 text-white"
                                                >
                                                    <ExternalLink className="h-4 w-4 mr-2" />
                                                    View Pull Request on GitHub
                                                </Button>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex items-start gap-3">
                                        <XCircle className="h-8 w-8 text-red-400 flex-shrink-0 mt-1" />
                                        <div>
                                            <h3 className="text-xl font-bold text-red-400 mb-2">Error Creating Pull Request</h3>
                                            <p className="text-white/70">{prResult.error}</p>
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
