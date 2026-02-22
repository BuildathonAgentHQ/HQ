"use client";

import { useEffect, useState, useCallback, FormEvent, useRef } from "react";
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
    ChevronDown,
    LogOut,
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

const fetchOpts: RequestInit = { credentials: "include" };

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        ...fetchOpts,
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

async function triggerAudit(repoId: string) {
    return apiFetch<{ plan: unknown; message?: string }>("/swarm/plan", {
        method: "POST",
        body: JSON.stringify({ repo_id: repoId, mode: "repo_audit" }),
    });
}

// ── Page Component ─────────────────────────────────────────────────────────

interface AuthUser {
    login: string;
    name?: string;
    avatar_url?: string;
}

interface GitHubRepo {
    id: number;
    full_name: string;
    owner: string;
    name: string;
    private: boolean;
    html_url: string;
}

interface ActivePR {
    repo_id: string;
    repo_full_name: string;
    number: number;
    title: string;
    author: string;
    html_url: string;
    created_at?: string;
}

export default function ReposPage() {
    const router = useRouter();
    const { toast } = useToast();
    const [repos, setRepos] = useState<Repository[] | null>(null);
    const [repoInput, setRepoInput] = useState("");
    const [isAdding, setIsAdding] = useState(false);
    const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
    const [authUser, setAuthUser] = useState<AuthUser | null>(null);
    const [githubRepos, setGithubRepos] = useState<GitHubRepo[]>([]);
    const [authLoading, setAuthLoading] = useState(true);
    const [githubReposLoading, setGithubReposLoading] = useState(false);
    const [repoDropdownOpen, setRepoDropdownOpen] = useState(false);
    const [prDropdownOpen, setPrDropdownOpen] = useState(false);
    const [activePRs, setActivePRs] = useState<ActivePR[]>([]);
    const [activePRsLoading, setActivePRsLoading] = useState(false);
    const repoDropdownRef = useRef<HTMLDivElement>(null);
    const prDropdownRef = useRef<HTMLDivElement>(null);

    const fetchRepos = useCallback(async () => {
        try {
            const data = await getRepos();
            setRepos(data);
        } catch {
            setRepos([]);
        }
    }, []);

    const fetchActivePRs = useCallback(async () => {
        setActivePRsLoading(true);
        try {
            const data = await apiFetch<ActivePR[]>("/repos/all-prs");
            setActivePRs(data);
        } catch {
            setActivePRs([]);
        } finally {
            setActivePRsLoading(false);
        }
    }, []);

    const fetchAuth = useCallback(async () => {
        setAuthLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/auth/me`, { credentials: "include" });
            const data = await res.json();
            if (data.authenticated && data.user) {
                setAuthUser(data.user);
            } else {
                setAuthUser(null);
            }
        } catch {
            setAuthUser(null);
        } finally {
            setAuthLoading(false);
        }
    }, []);

    const fetchGithubRepos = useCallback(async () => {
        if (!authUser) return;
        setGithubReposLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/auth/github/repos`, { credentials: "include" });
            const data = await res.json();
            setGithubRepos(data.repos || []);
        } catch {
            setGithubRepos([]);
        } finally {
            setGithubReposLoading(false);
        }
    }, [authUser]);

    useEffect(() => {
        fetchRepos();
    }, [fetchRepos]);

    useEffect(() => {
        if (repos && repos.length > 0) {
            fetchActivePRs();
        } else {
            setActivePRs([]);
        }
    }, [repos, fetchActivePRs]);

    useEffect(() => {
        fetchAuth();
    }, [fetchAuth]);

    useEffect(() => {
        const onClose = (e: MouseEvent) => {
            if (repoDropdownRef.current && !repoDropdownRef.current.contains(e.target as Node)) {
                setRepoDropdownOpen(false);
            }
            if (prDropdownRef.current && !prDropdownRef.current.contains(e.target as Node)) {
                setPrDropdownOpen(false);
            }
        };
        if (repoDropdownOpen || prDropdownOpen) {
            document.addEventListener("click", onClose);
            return () => document.removeEventListener("click", onClose);
        }
    }, [repoDropdownOpen, prDropdownOpen]);

    useEffect(() => {
        if (authUser) fetchGithubRepos();
        else setGithubRepos([]);
    }, [authUser, fetchGithubRepos]);

    // Handle OAuth callback errors from URL
    useEffect(() => {
        const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
        const error = params.get("error");
        if (error) {
            toast({
                title: "GitHub sign-in failed",
                description: error === "github_oauth_not_configured"
                    ? "GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env"
                    : `Error: ${error}`,
                variant: "destructive",
            });
            window.history.replaceState({}, "", "/repos");
        }
    }, [toast]);

    const handleLogout = async () => {
        try {
            await fetch(`${API_BASE_URL}/auth/logout`, {
                method: "POST",
                credentials: "include",
            });
            setAuthUser(null);
            setGithubRepos([]);
            toast({ title: "Signed out" });
        } catch {
            setAuthUser(null);
        }
    };

    const handleAddFromDropdown = async (ghRepo: GitHubRepo) => {
        const [owner, name] = ghRepo.full_name.split("/");
        if (!owner || !name) return;
        setIsAdding(true);
        setRepoDropdownOpen(false);
        try {
            await addRepo(owner, name);
            toast({
                title: "Repository connected",
                description: `${ghRepo.full_name} added. Analyzing…`,
            });
            await fetchRepos();
        } catch (err: unknown) {
            toast({
                title: "Connection failed",
                description: err instanceof Error ? err.message : "Could not connect repository",
                variant: "destructive",
            });
        } finally {
            setIsAdding(false);
        }
    };

    const connectedFullNames = new Set((repos ?? []).map((r) => r.full_name));

    const handleSelectPR = (pr: ActivePR) => {
        setPrDropdownOpen(false);
        router.push(`/repos/${pr.repo_id}/prs/${pr.number}`);
    };

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
                const res = await triggerAudit(repo.id);
                if (res && typeof res === "object" && "plan" in res && res.plan === null) {
                    toast({
                        title: "Audit complete",
                        description: (res as { message?: string }).message ?? "No issues found to fix.",
                    });
                } else {
                    toast({ title: "Audit started", description: `Auditing ${repo.full_name}…` });
                }
            } catch (err: unknown) {
                let description = "Could not start audit";
                const msg = err instanceof Error ? err.message : String(err);
                const jsonMatch = msg.match(/\{.*\}/);
                if (jsonMatch) {
                    try {
                        const parsed = JSON.parse(jsonMatch[0]);
                        if (parsed.detail) description = parsed.detail;
                    } catch {
                        if (msg.includes(":")) description = msg.split(": ").slice(1).join(": ").trim();
                    }
                } else if (msg.includes(":")) {
                    description = msg.split(": ").slice(1).join(": ").trim();
                }
                toast({
                    title: "Audit failed",
                    description,
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

            {/* ── Auth + Add Repository ───────────────────────────────────── */}
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader className="pb-4">
                    <CardTitle className="flex items-center justify-between text-base">
                        <span className="flex items-center gap-2">
                            <Plus className="h-4 w-4 text-indigo-400" />
                            Connect Repository
                        </span>
                        {authLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        ) : authUser ? (
                            <div className="flex items-center gap-2">
                                {authUser.avatar_url && (
                                    <img
                                        src={authUser.avatar_url}
                                        alt=""
                                        className="h-6 w-6 rounded-full"
                                    />
                                )}
                                <span className="text-sm text-muted-foreground">
                                    {authUser.login}
                                </span>
                                <button
                                    onClick={handleLogout}
                                    className="rounded p-1 text-muted-foreground hover:bg-white/5 hover:text-white transition-colors"
                                    title="Sign out"
                                >
                                    <LogOut className="h-3.5 w-3.5" />
                                </button>
                            </div>
                        ) : null}
                    </CardTitle>
                    <CardDescription>
                        {authUser
                            ? "Select from your GitHub repos or paste a URL"
                            : "Sign in with GitHub to select from your repos, or paste a URL"}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    {!authUser && (
                        <div className="space-y-2">
                            <a
                                href={`${API_BASE_URL.replace("/api", "")}/api/auth/github/login`}
                                className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/50 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700/50 transition-colors"
                            >
                                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                                    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                                </svg>
                                Sign in with GitHub
                            </a>
                            <p className="text-xs text-muted-foreground">
                                You&apos;ll be redirected to GitHub to enter your username or email and password.
                            </p>
                        </div>
                    )}

                    {authUser && githubRepos.length > 0 && (
                        <div className="relative" ref={repoDropdownRef}>
                            <button
                                type="button"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setRepoDropdownOpen(!repoDropdownOpen);
                                }}
                                disabled={isAdding || githubReposLoading}
                                className="inline-flex items-center gap-2 w-full rounded-lg border border-border/40 bg-background/50 py-2.5 px-4 text-sm text-foreground hover:border-indigo-500/50 transition-colors disabled:opacity-50"
                            >
                                <GitFork className="h-4 w-4 text-muted-foreground shrink-0" />
                                {githubReposLoading ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <span className="truncate">
                                        Select a repository from your GitHub…
                                    </span>
                                )}
                                <ChevronDown className={`h-4 w-4 ml-auto shrink-0 transition-transform ${repoDropdownOpen ? "rotate-180" : ""}`} />
                            </button>
                            {repoDropdownOpen && (
                                <div className="absolute top-full left-0 right-0 mt-1 z-50 max-h-60 overflow-y-auto rounded-lg border border-border/40 bg-[#0d1117] shadow-xl py-1">
                                    {githubRepos
                                        .filter((r) => !connectedFullNames.has(r.full_name))
                                        .map((r) => (
                                            <button
                                                key={r.id}
                                                type="button"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleAddFromDropdown(r);
                                                }}
                                                className="w-full text-left px-4 py-2 text-sm hover:bg-white/5 flex items-center gap-2"
                                            >
                                                <GitFork className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                                <span className="truncate">{r.full_name}</span>
                                                {r.private && (
                                                    <span className="text-[10px] text-muted-foreground">private</span>
                                                )}
                                            </button>
                                        ))}
                                    {githubRepos.filter((r) => !connectedFullNames.has(r.full_name)).length === 0 && (
                                        <p className="px-4 py-3 text-sm text-muted-foreground">
                                            All your repos are already connected
                                        </p>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    <form onSubmit={handleAddRepo} className="flex gap-3">
                        <div className="relative flex-1">
                            <GitFork className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <input
                                type="text"
                                value={repoInput}
                                onChange={(e) => setRepoInput(e.target.value)}
                                placeholder="Or paste: facebook/react or https://github.com/owner/repo"
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

            {/* ── Active PRs dropdown (when repos connected) ───────────── */}
            {repos && repos.length > 0 && (
                <Card className="border-border/40 bg-card/60 backdrop-blur">
                    <CardHeader className="pb-4">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <GitPullRequest className="h-4 w-4 text-indigo-400" />
                            Connect to PR
                        </CardTitle>
                        <CardDescription>
                            Select an active PR from your connected repositories to view and review
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="relative" ref={prDropdownRef}>
                            <button
                                type="button"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setPrDropdownOpen(!prDropdownOpen);
                                }}
                                disabled={activePRsLoading}
                                className="inline-flex items-center gap-2 w-full rounded-lg border border-border/40 bg-background/50 py-2.5 px-4 text-sm text-foreground hover:border-indigo-500/50 transition-colors disabled:opacity-50"
                            >
                                <GitPullRequest className="h-4 w-4 text-muted-foreground shrink-0" />
                                {activePRsLoading ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <span className="truncate">
                                        {activePRs.length > 0
                                            ? `Select from ${activePRs.length} active PR${activePRs.length === 1 ? "" : "s"}…`
                                            : "No active PRs in connected repos"}
                                    </span>
                                )}
                                <ChevronDown className={`h-4 w-4 ml-auto shrink-0 transition-transform ${prDropdownOpen ? "rotate-180" : ""}`} />
                            </button>
                            {prDropdownOpen && activePRs.length > 0 && (
                                <div className="absolute top-full left-0 right-0 mt-1 z-50 max-h-60 overflow-y-auto rounded-lg border border-border/40 bg-[#0d1117] shadow-xl py-1">
                                    {activePRs.map((pr) => (
                                        <button
                                            key={`${pr.repo_id}-${pr.number}`}
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleSelectPR(pr);
                                            }}
                                            className="w-full text-left px-4 py-2 text-sm hover:bg-white/5 flex flex-col gap-0.5"
                                        >
                                            <span className="font-medium truncate">{pr.title}</span>
                                            <span className="text-xs text-muted-foreground">
                                                {pr.repo_full_name} #{pr.number} · {pr.author}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

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
                                        icon={Shield}
                                        label="Audit Repo"
                                        className="text-amber-400 hover:bg-amber-500/10"
                                        loading={isActionLoading(
                                            `audit-${repo.id}`
                                        )}
                                        onClick={() => handleAudit(repo)}
                                    />
                                    <ActionBtn
                                        icon={RefreshCw}
                                        label="Re-analyze"
                                        loading={isActionLoading(
                                            `analyze-${repo.id}`
                                        )}
                                        onClick={() => handleReAnalyze(repo)}
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
