"use client";

import { useEffect, useState, useCallback, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/hooks/use-toast";
import { API_BASE_URL } from "@/lib/constants";
import type { Repository } from "@/lib/types";

import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    GitFork,
    Plus,
    Loader2,
    ExternalLink,
    RefreshCw,
    Eye,
    Shield,
    Trash2,
    Bug,
    GitPullRequest,
} from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────

function parseRepoInput(input: string): { owner: string; name: string } | null {
    const trimmed = input.trim();

    // Handle full GitHub URL
    const urlMatch = trimmed.match(
        /(?:https?:\/\/)?(?:www\.)?github\.com\/([^/]+)\/([^/\s]+)/
    );
    if (urlMatch) {
        return { owner: urlMatch[1], name: urlMatch[2].replace(/\.git$/, "") };
    }

    // Handle owner/name format
    const slashMatch = trimmed.match(/^([^/\s]+)\/([^/\s]+)$/);
    if (slashMatch) {
        return { owner: slashMatch[1], name: slashMatch[2] };
    }

    return null;
}

function healthColor(score: number | null): string {
    if (score === null) return "text-slate-500";
    if (score > 80) return "text-emerald-400";
    if (score > 50) return "text-amber-400";
    return "text-red-400";
}

function healthBg(score: number | null): string {
    if (score === null) return "bg-slate-500/10";
    if (score > 80) return "bg-emerald-500/10";
    if (score > 50) return "bg-amber-500/10";
    return "bg-red-500/10";
}

function timeAgo(iso: string | null): string {
    if (!iso) return "Never";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

const TECH_COLORS: Record<string, string> = {
    python: "bg-blue-500/15 text-blue-400 border-blue-500/20",
    typescript: "bg-sky-500/15 text-sky-400 border-sky-500/20",
    javascript: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
    react: "bg-cyan-500/15 text-cyan-400 border-cyan-500/20",
    nextjs: "bg-white/10 text-white border-white/20",
    "next.js": "bg-white/10 text-white border-white/20",
    fastapi: "bg-teal-500/15 text-teal-400 border-teal-500/20",
    docker: "bg-blue-500/15 text-blue-300 border-blue-500/20",
    rust: "bg-orange-500/15 text-orange-400 border-orange-500/20",
    go: "bg-cyan-500/15 text-cyan-300 border-cyan-500/20",
};

function techBadgeClass(tech: string): string {
    const lower = tech.toLowerCase();
    return TECH_COLORS[lower] ?? "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
}

// ── API calls ──────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        headers: { "Content-Type": "application/json", ...init?.headers },
        ...init,
    });
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`API error ${res.status}: ${body}`);
    }
    return res.json() as Promise<T>;
}

async function getRepos(): Promise<Repository[]> {
    return apiFetch<Repository[]>("/repos");
}

async function addRepo(owner: string, name: string): Promise<Repository> {
    return apiFetch<Repository>("/repos", {
        method: "POST",
        body: JSON.stringify({ owner, name }),
    });
}

async function deleteRepo(repoId: string): Promise<void> {
    await apiFetch(`/repos/${repoId}`, { method: "DELETE" });
}

async function triggerAnalysis(repoId: string): Promise<void> {
    await apiFetch(`/repos/${repoId}/analyze`, { method: "POST" });
}

async function triggerAudit(repoId: string): Promise<void> {
    await apiFetch("/swarm/plan", {
        method: "POST",
        body: JSON.stringify({ repo_id: repoId, mode: "repo_audit" }),
    });
}

// ── Page Component ─────────────────────────────────────────────────────────

export default function ReposPage() {
    const router = useRouter();
    const { toast } = useToast();
    const [repos, setRepos] = useState<Repository[] | null>(null);
    const [repoInput, setRepoInput] = useState("");
    const [isAdding, setIsAdding] = useState(false);
    const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());

    const fetchRepos = useCallback(async () => {
        try {
            const data = await getRepos();
            setRepos(data);
        } catch {
            setRepos([]);
        }
    }, []);

    useEffect(() => {
        fetchRepos();
    }, [fetchRepos]);

    // ── Add repo ────────────────────────────────────────────────────────

    const handleAddRepo = async (e: FormEvent) => {
        e.preventDefault();
        const parsed = parseRepoInput(repoInput);
        if (!parsed) {
            toast({
                title: "Invalid input",
                description:
                    'Enter a GitHub URL or owner/name (e.g. "facebook/react")',
                variant: "destructive",
            });
            return;
        }

        setIsAdding(true);
        try {
            await addRepo(parsed.owner, parsed.name);
            toast({
                title: "Repository connected",
                description: `${parsed.owner}/${parsed.name} added. Analyzing…`,
            });
            setRepoInput("");
            await fetchRepos();
        } catch (err: any) {
            toast({
                title: "Connection failed",
                description: err.message ?? "Could not connect repository",
                variant: "destructive",
            });
        } finally {
            setIsAdding(false);
        }
    };

    // ── Card actions ────────────────────────────────────────────────────

    const withLoading = async (id: string, fn: () => Promise<void>) => {
        setLoadingActions((prev) => new Set(prev).add(id));
        try {
            await fn();
        } finally {
            setLoadingActions((prev) => {
                const next = new Set(prev);
                next.delete(id);
                return next;
            });
        }
    };

    const handleReAnalyze = (repo: Repository) =>
        withLoading(`analyze-${repo.id}`, async () => {
            try {
                await triggerAnalysis(repo.id);
                toast({
                    title: "Re-analysis started",
                    description: `Analyzing ${repo.full_name}…`,
                });
                setTimeout(fetchRepos, 3000);
            } catch {
                toast({
                    title: "Analysis failed",
                    description: "Could not start re-analysis",
                    variant: "destructive",
                });
            }
        });

    const handleAudit = (repo: Repository) =>
        withLoading(`audit-${repo.id}`, async () => {
            try {
                await triggerAudit(repo.id);
                toast({ title: "Audit started", description: `Auditing ${repo.full_name}…` });
            } catch {
                toast({
                    title: "Audit failed",
                    description: "Could not start audit",
                    variant: "destructive",
                });
            }
        });

    const handleRemove = (repo: Repository) =>
        withLoading(`remove-${repo.id}`, async () => {
            try {
                await deleteRepo(repo.id);
                toast({ title: "Repository removed", description: repo.full_name });
                await fetchRepos();
            } catch {
                toast({
                    title: "Removal failed",
                    description: "Could not remove repository",
                    variant: "destructive",
                });
            }
        });

    const isActionLoading = (key: string) => loadingActions.has(key);

    // ── Render ───────────────────────────────────────────────────────────

    return (
        <div className="space-y-8">
            {/* ── Header ──────────────────────────────────────────── */}
            <div>
                <h2 className="text-2xl font-bold tracking-tight">Repositories</h2>
                <p className="text-sm text-muted-foreground">
                    Connect and manage GitHub repositories for analysis
                </p>
            </div>

            {/* ── Add Repository ───────────────────────────────────── */}
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Plus className="h-4 w-4 text-indigo-400" />
                        Connect Repository
                    </CardTitle>
                    <CardDescription>
                        Paste a GitHub URL or enter owner/name format
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleAddRepo} className="flex gap-3">
                        <div className="relative flex-1">
                            <GitFork className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <input
                                type="text"
                                value={repoInput}
                                onChange={(e) => setRepoInput(e.target.value)}
                                placeholder="facebook/react or https://github.com/facebook/react"
                                className="w-full rounded-lg border border-border/40 bg-background/50 py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition-colors"
                                disabled={isAdding}
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={isAdding || !repoInput.trim()}
                            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition-all hover:bg-indigo-500 hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isAdding ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Plus className="h-4 w-4" />
                            )}
                            {isAdding ? "Connecting…" : "Connect"}
                        </button>
                    </form>
                </CardContent>
            </Card>

            {/* ── Repository Grid ──────────────────────────────────── */}
            {repos === null ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-48 w-full rounded-xl" />
                    ))}
                </div>
            ) : repos.length === 0 ? (
                <Card className="border-border/40 bg-card/60 backdrop-blur">
                    <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 mb-4">
                            <GitFork className="h-7 w-7 text-indigo-400" />
                        </div>
                        <h3 className="text-lg font-semibold mb-1">
                            No repositories connected
                        </h3>
                        <p className="text-sm text-muted-foreground max-w-sm">
                            Connect your first GitHub repository above to start
                            analyzing code quality, security, and more.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {repos.map((repo) => (
                        <Card
                            key={repo.id}
                            className="group border-border/40 bg-card/60 backdrop-blur hover:border-indigo-500/30 transition-all animate-fade-in"
                        >
                            <CardContent className="p-5 space-y-4">
                                {/* Row 1: Name + Health Score */}
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-2 min-w-0">
                                        <a
                                            href={repo.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-1.5 text-base font-semibold text-white hover:text-indigo-400 transition-colors truncate"
                                        >
                                            {repo.full_name}
                                            <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-40" />
                                        </a>
                                    </div>
                                    <div
                                        className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-bold ${healthBg(
                                            repo.health_score
                                        )} ${healthColor(repo.health_score)}`}
                                    >
                                        {repo.health_score !== null
                                            ? repo.health_score
                                            : "—"}
                                        <span className="text-[10px] font-normal opacity-70">
                                            / 100
                                        </span>
                                    </div>
                                </div>

                                {/* Row 2: Tech Stack Badges */}
                                {repo.tech_stack.length > 0 && (
                                    <div className="flex flex-wrap gap-1.5">
                                        {repo.tech_stack.map((tech) => (
                                            <Badge
                                                key={tech}
                                                variant="outline"
                                                className={`text-[11px] px-2 py-0.5 ${techBadgeClass(
                                                    tech
                                                )}`}
                                            >
                                                {tech}
                                            </Badge>
                                        ))}
                                    </div>
                                )}

                                {/* Row 3: Analysis Summary */}
                                <p className="text-sm text-muted-foreground line-clamp-2">
                                    {repo.analysis_summary ??
                                        "Not yet analyzed. Click Re-analyze to start."}
                                </p>

                                {/* Row 4: Meta */}
                                <div className="flex items-center gap-4 text-xs text-muted-foreground/60">
                                    <span>
                                        Analyzed: {timeAgo(repo.last_analyzed)}
                                    </span>
                                    <span className="flex items-center gap-1">
                                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-slate-600" />
                                        {repo.default_branch}
                                    </span>
                                </div>

                                {/* Row 5: Actions */}
                                <div className="flex items-center gap-2 pt-1 border-t border-border/20">
                                    <ActionBtn
                                        icon={RefreshCw}
                                        label="Re-analyze"
                                        loading={isActionLoading(
                                            `analyze-${repo.id}`
                                        )}
                                        onClick={() => handleReAnalyze(repo)}
                                    />
                                    <ActionBtn
                                        icon={Eye}
                                        label="View PRs"
                                        onClick={() =>
                                            router.push(
                                                `/repos/${repo.id}/prs`
                                            )
                                        }
                                    />
                                    <ActionBtn
                                        icon={Shield}
                                        label="Audit Repo"
                                        className="text-amber-400 hover:bg-amber-500/10"
                                        loading={isActionLoading(
                                            `audit-${repo.id}`
                                        )}
                                        onClick={() => handleAudit(repo)}
                                    />
                                    <div className="flex-1" />
                                    <ActionBtn
                                        icon={Trash2}
                                        label="Remove"
                                        className="text-red-400 hover:bg-red-500/10"
                                        loading={isActionLoading(
                                            `remove-${repo.id}`
                                        )}
                                        onClick={() => handleRemove(repo)}
                                    />
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Small action button component ──────────────────────────────────────────

function ActionBtn({
    icon: Icon,
    label,
    onClick,
    loading,
    className,
}: {
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    onClick?: () => void;
    loading?: boolean;
    className?: string;
}) {
    return (
        <button
            onClick={onClick}
            disabled={loading}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:bg-white/5 hover:text-white disabled:opacity-50 ${className ?? ""}`}
            title={label}
        >
            {loading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
                <Icon className="h-3.5 w-3.5" />
            )}
            {label}
        </button>
    );
}
