'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Github, GitPullRequest, CheckCircle2, XCircle, Clock, ExternalLink, Settings, ArrowLeft, AlertCircle, LogOut } from 'lucide-react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';

interface GitHubIntegrationProps {
    auditId: string;
    auditUrl: string;
}

export function GitHubIntegration({ auditId, auditUrl }: GitHubIntegrationProps) {
    const [connections, setConnections] = useState<any[]>([]);
    const [repositories, setRepositories] = useState<any[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<string | null>(null);
    const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [creating, setCreating] = useState(false);
    const [prResult, setPrResult] = useState<any>(null);

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    useEffect(() => {
        fetchConnections();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

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
        setLoading(true);
        try {
            const res = await fetch(`${backendUrl}/api/github/repos/${connectionId}`);
            if (res.ok) {
                const data = await res.json();
                setRepositories(data);
            }
        } catch (err) {
            console.error('Error fetching repositories:', err);
        } finally {
            setLoading(false);
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

    if (connections.length === 0) {
        return (
            <Card className="glass-card p-6">
                <div className="flex items-start gap-4">
                    <div className="p-3 rounded-lg bg-brand/10">
                        <Github className="h-6 w-6 text-brand" />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-lg font-semibold text-foreground mb-2">GitHub Auto-Fix</h3>
                        <p className="text-muted-foreground mb-4">
                            Connect your GitHub account to automatically create Pull Requests with AI-powered SEO/GEO fixes.
                        </p>
                        <Button onClick={connectGitHub} className="bg-brand text-brand-foreground hover:bg-brand/90">
                            <Github className="h-4 w-4 mr-2" />
                            Connect GitHub
                        </Button>
                    </div>
                </div>
            </Card>
        );
    }

    return (
        <Card className="glass-card p-6">
            <div className="flex items-start gap-4">
                <div className="p-3 rounded-lg bg-brand/10">
                    <GitPullRequest className="h-6 w-6 text-brand" />
                </div>
                <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-lg font-semibold text-foreground">GitHub Auto-Fix</h3>
                        <div className="flex items-center gap-2">
                            <Badge variant="outline" className="border-green-500/50 text-green-400">
                                <CheckCircle2 className="h-3 w-3 mr-1" />
                                Connected
                            </Badge>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setConnections([])}
                                className="h-6 px-2 text-xs"
                                title="Disconnect to switch account"
                            >
                                <LogOut className="h-3 w-3" />
                            </Button>
                        </div>
                    </div>
                    <p className="text-muted-foreground mb-4">
                        Create a Pull Request with AI-generated fixes for all detected SEO/GEO issues.
                    </p>

                    <div className="space-y-4">
                        {/* Connection Selector */}
                        <div>
                            <label className="text-sm text-muted-foreground mb-2 block">GitHub Account</label>
                            <select
                                value={selectedConnection || ''}
                                onChange={(e) => handleConnectionChange(e.target.value)}
                                className="glass-input w-full px-4 py-2"
                            >
                                {connections.map((conn) => (
                                    <option key={conn.id} value={conn.id}>
                                        {conn.username}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Repository Selector */}
                        {loading ? (
                            <div className="text-muted-foreground text-sm">Loading repositories...</div>
                        ) : (
                            <div>
                                <label className="text-sm text-muted-foreground mb-2 block">Repository</label>
                                <select
                                    value={selectedRepo || ''}
                                    onChange={(e) => setSelectedRepo(e.target.value)}
                                    className="glass-input w-full px-4 py-2"
                                    disabled={repositories.length === 0}
                                >
                                    <option value="">Select a repository...</option>
                                    {repositories.map((repo) => (
                                        <option key={repo.id} value={repo.id}>
                                            {repo.full_name} ({repo.site_type || 'unknown'})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {/* Create PR Button */}
                        <Button
                            onClick={createAutoFixPR}
                            disabled={!selectedRepo || creating}
                            className="w-full bg-brand text-brand-foreground hover:bg-brand/90"
                        >
                            {creating ? (
                                <>
                                    <Clock className="h-4 w-4 mr-2 animate-spin" />
                                    Creating Pull Request...
                                </>
                            ) : (
                                <>
                                    <GitPullRequest className="h-4 w-4 mr-2" />
                                    Create Auto-Fix PR
                                </>
                            )}
                        </Button>

                        {/* Result */}
                        {prResult && (
                            <div
                                className={`p-4 rounded-lg border ${prResult.success
                                    ? 'bg-green-500/10 border-green-500/50'
                                    : 'bg-red-500/10 border-red-500/50'
                                    }`}
                            >
                                {prResult.success ? (
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2 text-green-400 font-medium">
                                            <CheckCircle2 className="h-5 w-5" />
                                            Pull Request Created!
                                        </div>
                                        <p className="text-foreground/70 text-sm">
                                            {prResult.data.files_modified} files modified with {prResult.data.fixes_applied} fixes
                                        </p>
                                        {prResult.data.pr?.html_url && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => window.open(prResult.data.pr.html_url, '_blank')}
                                                className="border-green-500/50 text-green-400 hover:bg-green-500/10"
                                            >
                                                <ExternalLink className="h-4 w-4 mr-2" />
                                                View Pull Request
                                            </Button>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex items-start gap-2 text-red-400">
                                        <XCircle className="h-5 w-5 mt-0.5" />
                                        <div>
                                            <div className="font-medium">Error Creating PR</div>
                                            <div className="text-sm text-foreground/70 mt-1">{prResult.error}</div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </Card>
    );
}
