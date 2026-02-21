"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useToast } from "@/hooks/use-toast";
import { API_BASE_URL } from "@/lib/constants";
import type { PRReview, CodeIssue } from "@/lib/types";

import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    ArrowLeft,
    Loader2,
    Bug,
    Lock,
    Zap,
    FlaskConical,
    AlertTriangle,
    Wrench,
    CheckCircle2,
    MessageSquare,
    RefreshCw,
    Shield,
} from "lucide-react";

// ── API helpers ────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        headers: { "Content-Type": "application/json", ...init?.headers },
        ...init,
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json() as Promise<T>;
}

interface PRSummary {
    number: number;
    title: string;
    author: string;
    created_at: string;
    review?: PRReview;
}

// ── Risk / verdict visuals ─────────────────────────────────────────────────

const RISK_CONFIG: Record<string, { emoji: string; color: string; bg: string }> = {
    low: { emoji: "🟢", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
    medium: { emoji: "🟡", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20" },
    high: { emoji: "🟠", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20" },
    critical: { emoji: "🔴", color: "text-red-400", bg: "bg-red-500/10 border-red-500/20" },
};

const VERDICT_CONFIG: Record<string, { emoji: string; label: string; color: string }> = {
    approve: { emoji: "✅", label: "Approve", color: "text-emerald-400" },
    request_changes: { emoji: "🔄", label: "Request Changes", color: "text-orange-400" },
    needs_discussion: { emoji: "💬", label: "Needs Discussion", color: "text-amber-400" },
};

const ISSUE_TYPE_ICONS: Record<string, { icon: typeof Bug; emoji: string }> = {
    bug: { icon: Bug, emoji: "🐛" },
    security: { icon: Lock, emoji: "🔒" },
    performance: { icon: Zap, emoji: "⚡" },
    testing: { icon: FlaskConical, emoji: "🧪" },
    error_handling: { icon: AlertTriangle, emoji: "⚠️" },
    style: { icon: Wrench, emoji: "🎨" },
    breaking: { icon: AlertTriangle, emoji: "💥" },
    refactor: { icon: Wrench, emoji: "🔧" },
};

function countIssuesByType(issues: CodeIssue[]): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const i of issues) {
        counts[i.issue_type] = (counts[i.issue_type] || 0) + 1;
    }
    return counts;
}

function timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

// ── Page Component ─────────────────────────────────────────────────────────

export default function PRListPage() {
    const { repoId } = useParams<{ repoId: string }>();
    const router = useRouter();
    const { toast } = useToast();

    const [prs, setPrs] = useState<PRSummary[] | null>(null);
    const [reviewing, setReviewing] = useState<Set<number>>(new Set());
    const [reviewingAll, setReviewingAll] = useState(false);

    const fetchPRs = useCallback(async () => {
        try {
            const data = await apiFetch<PRSummary[]>(`/repos/${repoId}/prs`);
            setPrs(data);
        } catch {
            setPrs([]);
        }
    }, [repoId]);

    useEffect(() => {
        fetchPRs();
    }, [fetchPRs]);

    // ── Actions ─────────────────────────────────────────────────────────

    const handleReviewPR = async (prNumber: number) => {
        setReviewing((prev) => new Set(prev).add(prNumber));
        try {
            const review = await apiFetch<{ plan: unknown }>("/swarm/plan", {
                method: "POST",
                body: JSON.stringify({
                    repo_id: repoId,
                    pr_number: prNumber,
                    mode: "pr_review",
                }),
            });
            toast({ title: "PR reviewed", description: `PR #${prNumber} analysis complete` });
            await fetchPRs();
        } catch {
            toast({ title: "Review failed", variant: "destructive" });
        } finally {
            setReviewing((prev) => {
                const next = new Set(prev);
                next.delete(prNumber);
                return next;
            });
        }
    };

    const handleQuickFixAll = async (prNumber: number) => {
        setReviewing((prev) => new Set(prev).add(prNumber));
        try {
            // Create plan + execute
            const planRes = await apiFetch<{ plan: { id: string } | null }>("/swarm/plan", {
                method: "POST",
                body: JSON.stringify({ repo_id: repoId, pr_number: prNumber, mode: "pr_review" }),
            });
            if (planRes.plan?.id) {
                await apiFetch(`/swarm/plans/${planRes.plan.id}/execute`, { method: "POST" });
                toast({ title: "Swarm dispatched", description: `Fixing PR #${prNumber} issues…` });
            }
        } catch {
            toast({ title: "Quick fix failed", variant: "destructive" });
        } finally {
            setReviewing((prev) => {
                const next = new Set(prev);
                next.delete(prNumber);
                return next;
            });
        }
    };

    const handleReviewAll = async () => {
        setReviewingAll(true);
        try {
            const allPrs = prs ?? [];
            for (const pr of allPrs) {
                await apiFetch("/swarm/plan", {
                    method: "POST",
                    body: JSON.stringify({ repo_id: repoId, pr_number: pr.number, mode: "pr_review" }),
                });
            }
            toast({ title: "All PRs reviewed", description: `${allPrs.length} PR reviews triggered` });
            await fetchPRs();
        } catch {
            toast({ title: "Bulk review failed", variant: "destructive" });
        } finally {
            setReviewingAll(false);
        }
    };

    // Sort by risk level (critical first)
    const sortedPrs = (prs ?? []).sort((a, b) => {
        const order = { critical: 0, high: 1, medium: 2, low: 3 };
        const ra = order[a.review?.risk_level ?? "low"] ?? 4;
        const rb = order[b.review?.risk_level ?? "low"] ?? 4;
        return ra - rb;
    });

    // ── Render ──────────────────────────────────────────────────────────

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.push("/repos")}
                        className="rounded-lg p-2 hover:bg-white/5 transition-colors"
                    >
                        <ArrowLeft className="h-4 w-4 text-slate-400" />
                    </button>
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">Pull Requests</h2>
                        <p className="text-sm text-muted-foreground">
                            Claude-powered analysis of open PRs
                        </p>
                    </div>
                </div>
                <button
                    onClick={handleReviewAll}
                    disabled={reviewingAll || !prs?.length}
                    className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-500 disabled:opacity-50 transition-all"
                >
                    {reviewingAll ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Shield className="h-4 w-4" />
                    )}
                    Review All PRs
                </button>
            </div>

            {/* PR List */}
            {prs === null ? (
                <div className="space-y-4">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-40 w-full rounded-xl" />
                    ))}
                </div>
            ) : sortedPrs.length === 0 ? (
                <Card className="border-border/40 bg-card/60 backdrop-blur">
                    <CardContent className="flex flex-col items-center py-16 text-center">
                        <CheckCircle2 className="h-10 w-10 text-emerald-400 mb-3" />
                        <h3 className="text-lg font-semibold">No open PRs</h3>
                        <p className="text-sm text-muted-foreground">
                            All clear — no open pull requests to review
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-4">
                    {sortedPrs.map((pr) => {
                        const review = pr.review;
                        const risk = RISK_CONFIG[review?.risk_level ?? "low"];
                        const verdict = VERDICT_CONFIG[review?.verdict ?? "needs_discussion"];
                        const issueCounts = review ? countIssuesByType(review.issues) : {};
                        const isLoading = reviewing.has(pr.number);

                        return (
                            <Card
                                key={pr.number}
                                className="group border-border/40 bg-card/60 backdrop-blur hover:border-indigo-500/30 transition-all animate-fade-in"
                            >
                                <CardContent className="p-5 space-y-3">
                                    {/* Row 1: Title + risk + verdict */}
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="text-xs text-muted-foreground font-mono">
                                                    #{pr.number}
                                                </span>
                                                <h3 className="text-base font-semibold text-white truncate">
                                                    {pr.title}
                                                </h3>
                                            </div>
                                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                                <span>{pr.author}</span>
                                                <span>·</span>
                                                <span>{timeAgo(pr.created_at)}</span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            {review && (
                                                <>
                                                    <Badge
                                                        variant="outline"
                                                        className={`text-xs ${risk.bg}`}
                                                    >
                                                        {risk.emoji} {review.risk_level}
                                                    </Badge>
                                                    <Badge
                                                        variant="outline"
                                                        className={`text-xs ${verdict.color} border-current/20`}
                                                    >
                                                        {verdict.emoji} {verdict.label}
                                                    </Badge>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* Row 2: Summary */}
                                    {review?.summary && (
                                        <p className="text-sm text-muted-foreground line-clamp-2">
                                            {review.summary}
                                        </p>
                                    )}

                                    {/* Row 3: Issue counts */}
                                    {review && Object.keys(issueCounts).length > 0 && (
                                        <div className="flex items-center gap-3 flex-wrap">
                                            {Object.entries(issueCounts).map(([type, count]) => {
                                                const cfg = ISSUE_TYPE_ICONS[type];
                                                return (
                                                    <span
                                                        key={type}
                                                        className="inline-flex items-center gap-1 text-xs text-muted-foreground"
                                                    >
                                                        {cfg?.emoji ?? "📋"} {count} {type.replace("_", " ")}
                                                    </span>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {/* Row 4: Actions */}
                                    <div className="flex items-center gap-2 pt-2 border-t border-border/20">
                                        <button
                                            onClick={() =>
                                                router.push(`/repos/${repoId}/prs/${pr.number}`)
                                            }
                                            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600/20 px-3 py-1.5 text-xs font-medium text-indigo-400 hover:bg-indigo-600/30 transition-colors"
                                        >
                                            <MessageSquare className="h-3.5 w-3.5" />
                                            Review & Fix
                                        </button>
                                        <button
                                            onClick={() => handleQuickFixAll(pr.number)}
                                            disabled={isLoading}
                                            className="inline-flex items-center gap-1.5 rounded-md bg-amber-600/20 px-3 py-1.5 text-xs font-medium text-amber-400 hover:bg-amber-600/30 disabled:opacity-50 transition-colors"
                                        >
                                            {isLoading ? (
                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <Zap className="h-3.5 w-3.5" />
                                            )}
                                            Quick Fix All
                                        </button>
                                        {!review && (
                                            <button
                                                onClick={() => handleReviewPR(pr.number)}
                                                disabled={isLoading}
                                                className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-slate-400 hover:bg-white/5 hover:text-white disabled:opacity-50 transition-colors"
                                            >
                                                {isLoading ? (
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                ) : (
                                                    <RefreshCw className="h-3.5 w-3.5" />
                                                )}
                                                Analyze
                                            </button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
