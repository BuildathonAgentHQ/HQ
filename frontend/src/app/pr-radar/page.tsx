"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/hooks/use-toast";
import { API_BASE_URL, WS_URL } from "@/lib/constants";
import { useWebSocket } from "@/hooks/use-websocket";
import type { PRRiskScore, PRReview, CodeIssue } from "@/lib/types";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TestPreviewModal, type TestPreviewState } from "@/components/test-preview-modal";
import { RepoSelector } from "@/components/repo-selector";

import {
    GitPullRequest,
    AlertTriangle,
    CheckCircle2,
    ShieldAlert,
    Clock,
    Users,
    TestTube2,
    GitBranch,
    Loader2,
    Eye,
    Zap,
    Bot,
    Bug,
    Lock,
    Wrench,
    ArrowUpDown,
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

// ── Visual configs ─────────────────────────────────────────────────────────

const RISK_CONFIG: Record<string, { emoji: string; color: string; bg: string; textColor: string }> = {
    low: { emoji: "🟢", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20", textColor: "text-green-500" },
    medium: { emoji: "🟡", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20", textColor: "text-yellow-500" },
    high: { emoji: "🟠", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20", textColor: "text-orange-500" },
    critical: { emoji: "🔴", color: "text-red-400", bg: "bg-red-500/10 border-red-500/20", textColor: "text-red-500" },
};

const VERDICT_CONFIG: Record<string, { emoji: string; label: string; color: string }> = {
    approve: { emoji: "✅", label: "Approve", color: "text-emerald-400" },
    request_changes: { emoji: "🔄", label: "Request Changes", color: "text-orange-400" },
    needs_discussion: { emoji: "💬", label: "Needs Discussion", color: "text-amber-400" },
};

const ISSUE_EMOJI: Record<string, string> = {
    bug: "🐛",
    security: "🔒",
    performance: "⚡",
    testing: "🧪",
    error_handling: "⚠️",
    style: "🎨",
    breaking: "💥",
    refactor: "🔧",
};

function countIssuesByType(issues: CodeIssue[]): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const i of issues) counts[i.issue_type] = (counts[i.issue_type] || 0) + 1;
    return counts;
}

// ── Extended PR type (heuristic + Claude review) ───────────────────────────

interface PRWithReview {
    // Heuristic fields
    pr_id: string;
    pr_number: number;
    title: string;
    author: string;
    risk_score: number;
    risk_level: "low" | "medium" | "high" | "critical";
    factors: {
        diff_size: number;
        core_files_changed: boolean;
        missing_tests: boolean;
        churn_score: number;
        has_dependency_overlap: boolean;
    };
    reviewers_suggested: string[];
    // Claude review (optional — may not be available yet)
    review?: PRReview;
}

export default function PRRadarPage() {
    const router = useRouter();
    const { toast } = useToast();
    const { events } = useWebSocket(WS_URL);
    const [prs, setPrs] = useState<PRWithReview[]>([]);
    const [loading, setLoading] = useState(true);
    const [reviewing, setReviewing] = useState<Set<number>>(new Set());
    const [fixing, setFixing] = useState<Set<number>>(new Set());
    const [testPreview, setTestPreview] = useState<TestPreviewState>({ status: "idle", prNumber: null, taskId: null, code: null });
    const [selectedPR, setSelectedPR] = useState<number | null>(null);
    const [repoId, setRepoId] = useState<string | null>(null);
    const [sortMode, setSortMode] = useState<"criticality" | "time">("criticality");

    const fetchPRs = useCallback(async () => {
        try {
            // Fetch repos to get repo_id for swarm calls
            const reposRes = await fetch(`${API_BASE_URL}/repos`);
            if (reposRes.ok) {
                const repos = await reposRes.json();
                if (repos.length > 0) {
                    setRepoId(repos[0].id);
                }
            }
            const res = await fetch(`${API_BASE_URL}/control-plane/prs`);
            if (res.ok) {
                const data = await res.json();
                setPrs(data);
            }
        } catch {
            // pass
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPRs();
    }, [fetchPRs]);

    // ── Actions ─────────────────────────────────────────────────────────

    const handleDeepReview = async (prNumber: number) => {
        if (!repoId) {
            toast({ title: "No repository connected", description: "Connect a repo first", variant: "destructive" });
            return;
        }
        setReviewing((prev) => new Set(prev).add(prNumber));
        try {
            await apiFetch("/swarm/plan", {
                method: "POST",
                body: JSON.stringify({ repo_id: repoId, pr_number: prNumber, mode: "pr_review" }),
            });
            toast({ title: "Review started", description: `Claude is analyzing PR #${prNumber}…` });
            // Refresh after a delay to get the review
            setTimeout(fetchPRs, 5000);
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

    const handleFixIssues = async (prNumber: number) => {
        if (!repoId) {
            toast({ title: "No repository connected", variant: "destructive" });
            return;
        }
        setFixing((prev) => new Set(prev).add(prNumber));
        try {
            const planRes = await apiFetch<{ plan: { id: string } | null }>("/swarm/plan", {
                method: "POST",
                body: JSON.stringify({ repo_id: repoId, pr_number: prNumber, mode: "fix_issues" }),
            });
            if (planRes.plan?.id) {
                await apiFetch(`/swarm/plans/${planRes.plan.id}/execute`, { method: "POST" });
                toast({ title: "Swarm dispatched", description: `Fixing issues on PR #${prNumber}…` });
            }
        } catch {
            toast({ title: "Fix failed", variant: "destructive" });
        } finally {
            setFixing((prev) => {
                const next = new Set(prev);
                next.delete(prNumber);
                return next;
            });
        }
    };

    // ── WebSocket listener for Test Generation ─────────────────────────────
    useEffect(() => {
        if (!testPreview.taskId || testPreview.status !== "generating") return;

        // Find the most recent event for our task
        const relevantEvents = events.filter(e => e.task_id === testPreview.taskId);
        if (relevantEvents.length === 0) return;

        const latest = relevantEvents[0]; // Events are latest-first

        // Handle live status text updates (e.g. "Reading files...", "Writing tests...")
        if (latest.event_type === "status_update" && latest.payload?.message) {
            setTestPreview(prev => ({
                ...prev,
                liveStatus: latest.payload.message as string
            }));
        }

        // Handle completion
        if (latest.event_type === "task_lifecycle" &&
            (latest.payload?.status === "completed" || latest.payload?.status === "failed" || latest.payload?.status === "success")) {

            // Task is done. Fetch the exact code output immediately.
            setTestPreview(prev => ({ ...prev, liveStatus: "Finalizing code output..." }));

            fetch(`${API_BASE_URL}/tasks/${testPreview.taskId}/output`)
                .then(res => res.json())
                .then(outData => {
                    setTestPreview(prev => ({
                        ...prev,
                        status: "reviewing",
                        code: outData.output || "No output collected. Check backend logs."
                    }));
                })
                .catch(e => {
                    console.error("Failed to fetch final output:", e);
                    setTestPreview(prev => ({
                        ...prev,
                        status: "reviewing",
                        code: "Error retrieving generated tests."
                    }));
                });
        }
    }, [events, testPreview.taskId, testPreview.status]);

    const generateTests = async (prNumber: number) => {
        try {
            const res = await fetch(`${API_BASE_URL}/tasks/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    task: `Write unit tests for untested files in PR #${prNumber}.`,
                    engine: "claude-code",
                    agent_type: "test_writer",
                    budget_limit: 2.0,
                }),
            });
            if (!res.ok) throw new Error("Failed to start task");
            const taskObj = await res.json();

            // Set state to start showing the modal. The useEffect block above will handle listening for WebSocket events
            setTestPreview({
                status: "generating",
                prNumber,
                taskId: taskObj.id,
                code: null,
                liveStatus: "Starting test generator agent..."
            });

        } catch {
            toast({ title: "Failed to dispatch", variant: "destructive" });
        }
    };

    const handleApproveTest = async (taskId: string) => {
        setTestPreview(prev => ({ ...prev, status: "applying" }));
        try {
            // Tell the task to proceed via approve endpoint
            await fetch(`${API_BASE_URL}/tasks/${taskId}/approve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });

            toast({ title: "Tests Approved", description: `PR updates will be pushed shortly.` });
            setTestPreview({ status: "idle", prNumber: null, taskId: null, code: null });
        } catch {
            toast({ title: "Failed to approve", variant: "destructive" });
            setTestPreview(prev => ({ ...prev, status: "reviewing" }));
        }
    };

    // ── Render ──────────────────────────────────────────────────────────

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                        <GitPullRequest className="h-7 w-7 text-indigo-500" />
                        PR Reviews
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Heuristic risk analysis + Claude deep reviews of open pull requests
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <RepoSelector
                        selectedRepoId={repoId}
                        onRepoChange={(id) => {
                            setRepoId(id);
                            // Refetch PRs when repo changes
                            setLoading(true);
                            fetch(`${API_BASE_URL}/control-plane/prs`)
                                .then((r) => r.ok ? r.json() : [])
                                .then(setPrs)
                                .catch(() => { })
                                .finally(() => setLoading(false));
                        }}
                    />
                    <span className="text-xs text-muted-foreground">Sort:</span>
                    <button
                        onClick={() => setSortMode(sortMode === "criticality" ? "time" : "criticality")}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border/40 bg-card/60 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
                    >
                        <ArrowUpDown className="h-3 w-3" />
                        {sortMode === "criticality" ? "Criticality" : "Recent"}
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-44 w-full rounded-xl" />
                    ))}
                </div>
            ) : prs.length === 0 ? (
                <Card className="border-border/40 bg-card/60 backdrop-blur">
                    <CardContent className="flex flex-col items-center justify-center p-12 text-center">
                        <CheckCircle2 className="h-10 w-10 text-emerald-400 mb-4" />
                        <p className="text-lg font-medium">Inbox Zero</p>
                        <p className="text-sm text-muted-foreground">No open pull requests found.</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-4">
                    {[...prs].sort((a, b) => {
                        if (sortMode === "criticality") return b.risk_score - a.risk_score;
                        // sort by time — higher PR number = more recent
                        return b.pr_number - a.pr_number;
                    }).map((pr) => {
                        const risk = RISK_CONFIG[pr.risk_level] ?? RISK_CONFIG.low;
                        const review = pr.review;
                        const verdict = review ? VERDICT_CONFIG[review.verdict] : null;
                        const issueCounts = review ? countIssuesByType(review.issues) : {};
                        const isReviewing = reviewing.has(pr.pr_number);
                        const isFixing = fixing.has(pr.pr_number);

                        return (
                            <Card key={pr.pr_id} className="border-border/40 bg-card/60 backdrop-blur overflow-hidden hover:border-indigo-500/30 transition-all">
                                <div className="flex flex-col md:flex-row">
                                    {/* Risk Score Panel */}
                                    <div className={`p-6 flex flex-col items-center justify-center border-b md:border-b-0 md:border-r border-border/30 min-w-[140px] ${risk.textColor} bg-black/20`}>
                                        <span className="text-4xl font-black tracking-tighter">{pr.risk_score}</span>
                                        <Badge variant="outline" className={`mt-2 uppercase tracking-wide text-[10px] font-bold ${risk.bg}`}>
                                            {risk.emoji} {pr.risk_level}
                                        </Badge>
                                        {verdict && (
                                            <Badge variant="outline" className={`mt-1.5 text-[10px] ${verdict.color}`}>
                                                {verdict.emoji} {verdict.label}
                                            </Badge>
                                        )}
                                    </div>

                                    {/* Details Panel */}
                                    <div className="p-5 flex-1 flex flex-col space-y-3">
                                        {/* Title + author */}
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <h3 className="text-base font-bold text-white mb-0.5 flex items-center gap-2">
                                                    {pr.title}
                                                    <span className="text-muted-foreground text-sm font-normal">#{pr.pr_number}</span>
                                                </h3>
                                                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                                    <span className="flex items-center gap-1"><Users className="h-3 w-3" /> {pr.author}</span>
                                                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> Recently updated</span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Claude summary */}
                                        {review?.summary && (
                                            <p className="text-sm text-muted-foreground line-clamp-2 bg-indigo-500/[0.04] rounded-md px-3 py-2 border-l-2 border-indigo-500/30">
                                                <Bot className="h-3.5 w-3.5 inline mr-1 text-indigo-400" />
                                                {review.summary}
                                            </p>
                                        )}

                                        {/* Heuristic factors */}
                                        <div className="flex flex-wrap gap-2">
                                            {pr.factors.diff_size > 500 && (
                                                <Badge variant="secondary" className="text-[10px] bg-slate-800">Large Diff ({pr.factors.diff_size})</Badge>
                                            )}
                                            {pr.factors.core_files_changed && (
                                                <Badge variant="secondary" className="text-[10px] bg-slate-800 text-orange-400 border-orange-500/30">Core Files</Badge>
                                            )}
                                            {pr.factors.missing_tests && (
                                                <Badge variant="secondary" className="text-[10px] bg-slate-800 text-red-400 border-red-500/30">Missing Tests</Badge>
                                            )}
                                            {pr.factors.has_dependency_overlap && (
                                                <Badge variant="secondary" className="text-[10px] bg-slate-800 text-amber-400 border-amber-500/30">
                                                    <GitBranch className="h-3 w-3 mr-1" />Dep Overlap
                                                </Badge>
                                            )}
                                        </div>

                                        {/* Claude issue counts */}
                                        {Object.keys(issueCounts).length > 0 && (
                                            <div className="flex items-center gap-3 flex-wrap">
                                                {Object.entries(issueCounts).map(([type, count]) => (
                                                    <span key={type} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                                                        {ISSUE_EMOJI[type] ?? "📋"} {count} {type.replace("_", " ")}
                                                    </span>
                                                ))}
                                            </div>
                                        )}

                                        {/* Claude issues inline (top 3) */}
                                        {review && review.issues.length > 0 && (
                                            <div className="space-y-1">
                                                {review.issues.slice(0, 3).map((issue) => (
                                                    <div key={issue.id} className="flex items-start gap-2 text-xs rounded-md bg-card/80 px-2.5 py-1.5 border border-border/20">
                                                        <span>{ISSUE_EMOJI[issue.issue_type] ?? "📋"}</span>
                                                        <div className="min-w-0 flex-1">
                                                            <span className="font-mono text-indigo-400/80 text-[10px]">{issue.file_path}</span>
                                                            <p className="text-muted-foreground truncate">{issue.description}</p>
                                                        </div>
                                                        <Badge variant="outline" className={`text-[9px] shrink-0 ${issue.severity === "critical" ? "text-red-400 border-red-500/20"
                                                            : issue.severity === "high" ? "text-orange-400 border-orange-500/20"
                                                                : "text-slate-400 border-slate-500/20"
                                                            }`}>{issue.severity}</Badge>
                                                    </div>
                                                ))}
                                                {review.issues.length > 3 && (
                                                    <p className="text-[10px] text-muted-foreground/60 pl-5">
                                                        +{review.issues.length - 3} more issues
                                                    </p>
                                                )}
                                            </div>
                                        )}

                                        {/* Actions */}
                                        <div className="flex items-center gap-2 pt-2 border-t border-border/20">
                                            {/* Suggested reviewers */}
                                            {pr.reviewers_suggested.length > 0 && (
                                                <div className="flex items-center gap-1 mr-auto">
                                                    <span className="text-[10px] text-muted-foreground/60">Reviewers:</span>
                                                    {pr.reviewers_suggested.map((rev, i) => (
                                                        <Badge key={i} variant="outline" className="text-[10px] border-border/30 text-slate-400">{rev}</Badge>
                                                    ))}
                                                </div>
                                            )}

                                            {/* Deep Review */}
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                className="h-7 text-xs border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10"
                                                onClick={() => handleDeepReview(pr.pr_number)}
                                                disabled={isReviewing}
                                            >
                                                {isReviewing ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Eye className="h-3.5 w-3.5 mr-1" />}
                                                Review
                                            </Button>

                                            {/* Fix issues */}
                                            {review && review.issues.length > 0 && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="h-7 text-xs border-violet-500/30 text-violet-400 hover:bg-violet-500/10"
                                                    onClick={() => handleFixIssues(pr.pr_number)}
                                                    disabled={isFixing}
                                                >
                                                    {isFixing ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Wrench className="h-3.5 w-3.5 mr-1" />}
                                                    Fix {review.issues.length} Issues
                                                </Button>
                                            )}

                                            {/* Generate tests */}
                                            {pr.factors.missing_tests && (
                                                <Button
                                                    size="sm"
                                                    className="h-7 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                                                    onClick={() => generateTests(pr.pr_number)}
                                                >
                                                    <TestTube2 className="h-3.5 w-3.5 mr-1" />
                                                    Gen Tests
                                                </Button>
                                            )}

                                            {/* View detail */}
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="h-7 text-xs text-slate-400 hover:text-white"
                                                onClick={() => setSelectedPR(selectedPR === pr.pr_number ? null : pr.pr_number)}
                                            >
                                                {selectedPR === pr.pr_number ? "Hide ↑" : "View →"}
                                            </Button>
                                        </div>
                                    </div>
                                </div>

                                {/* ── Expanded Review Detail ──────── */}
                                {selectedPR === pr.pr_number && review && (
                                    <div className="border-t border-border/20 bg-card/40 p-5 space-y-4">
                                        <div className="flex items-center gap-3">
                                            <h4 className="text-sm font-bold text-white">Full Review — PR #{pr.pr_number}</h4>
                                            {verdict && (
                                                <Badge className={verdict.color}>
                                                    {verdict.emoji} {verdict.label}
                                                </Badge>
                                            )}
                                        </div>

                                        {review.summary && (
                                            <div className="bg-indigo-500/[0.06] rounded-lg p-4 border border-indigo-500/20">
                                                <p className="text-sm text-slate-300 leading-relaxed">{review.summary}</p>
                                            </div>
                                        )}

                                        {review.issues.length > 0 && (
                                            <div className="space-y-2">
                                                <h5 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Issues ({review.issues.length})</h5>
                                                {review.issues.map((issue) => (
                                                    <div key={issue.id} className="flex items-start gap-3 text-sm rounded-md bg-card/80 px-3 py-2 border border-border/20">
                                                        <span className="text-base">{ISSUE_EMOJI[issue.issue_type] ?? "📋"}</span>
                                                        <div className="min-w-0 flex-1">
                                                            <div className="flex items-center gap-2 mb-1">
                                                                <span className="font-mono text-indigo-400 text-xs">{issue.file_path}</span>
                                                                <Badge variant="outline" className={`text-[9px] ${issue.severity === "critical" ? "text-red-400" : issue.severity === "high" ? "text-orange-400" : "text-slate-400"}`}>
                                                                    {issue.severity}
                                                                </Badge>
                                                            </div>
                                                            <p className="text-muted-foreground text-xs">{issue.description}</p>
                                                            {issue.suggestion && (
                                                                <p className="text-emerald-400/80 text-xs mt-1">💡 {issue.suggestion}</p>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {review.issues.length === 0 && (
                                            <p className="text-sm text-emerald-400">✅ No issues found — this PR looks clean!</p>
                                        )}
                                    </div>
                                )}

                                {selectedPR === pr.pr_number && !review && (
                                    <div className="border-t border-border/20 bg-card/40 p-5 text-center">
                                        <p className="text-sm text-muted-foreground">No review data yet. Click &quot;Review&quot; to start a Claude analysis.</p>
                                    </div>
                                )}
                            </Card>
                        );
                    })}
                </div>
            )}

            <TestPreviewModal
                preview={testPreview}
                onDismiss={() => setTestPreview({ status: "idle", prNumber: null, taskId: null, code: null })}
                onApprove={handleApproveTest}
            />
        </div>
    );
}
