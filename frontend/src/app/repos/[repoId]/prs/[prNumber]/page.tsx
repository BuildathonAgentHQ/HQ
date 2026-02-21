"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useToast } from "@/hooks/use-toast";
import { useWebSocket } from "@/hooks/use-websocket";
import { API_BASE_URL, WS_URL } from "@/lib/constants";
import type { PRReview, CodeIssue, FixProposal, SwarmPlan, SwarmTask } from "@/lib/types";
import { SwarmMonitor } from "@/components/swarm-monitor";
import { FixDiffViewer } from "@/components/fix-diff-viewer";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    XCircle,
    Eye,
    X,
    ChevronDown,
    ChevronUp,
    Sparkles,
    Send,
    Play,
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

const RISK_STYLES: Record<string, { emoji: string; color: string; bg: string }> = {
    low: { emoji: "🟢", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
    medium: { emoji: "🟡", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20" },
    high: { emoji: "🟠", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20" },
    critical: { emoji: "🔴", color: "text-red-400", bg: "bg-red-500/10 border-red-500/20" },
};

const VERDICT_STYLES: Record<string, { emoji: string; label: string; color: string; bg: string }> = {
    approve: { emoji: "✅", label: "Approve", color: "text-emerald-400", bg: "bg-emerald-500/10" },
    request_changes: { emoji: "🔄", label: "Request Changes", color: "text-orange-400", bg: "bg-orange-500/10" },
    needs_discussion: { emoji: "💬", label: "Needs Discussion", color: "text-amber-400", bg: "bg-amber-500/10" },
};

const SEVERITY_STYLES: Record<string, string> = {
    critical: "bg-red-500/15 text-red-400 border-red-500/20",
    high: "bg-orange-500/15 text-orange-400 border-orange-500/20",
    medium: "bg-amber-500/15 text-amber-400 border-amber-500/20",
    low: "bg-slate-500/15 text-slate-400 border-slate-500/20",
};

const TYPE_EMOJI: Record<string, string> = {
    bug: "🐛",
    security: "🔒",
    performance: "⚡",
    error_handling: "⚠️",
    testing: "🧪",
    style: "🎨",
    breaking: "💥",
    refactor: "🔧",
};

const STATUS_STYLES: Record<string, { label: string; color: string }> = {
    open: { label: "Open", color: "text-blue-400" },
    fixing: { label: "Fixing…", color: "text-amber-400" },
    fixed: { label: "Fixed", color: "text-emerald-400" },
    dismissed: { label: "Dismissed", color: "text-slate-500" },
};

// ── Page Component ─────────────────────────────────────────────────────────

export default function PRDetailPage() {
    const { repoId, prNumber } = useParams<{ repoId: string; prNumber: string }>();
    const router = useRouter();
    const { toast } = useToast();
    const { events } = useWebSocket(WS_URL);

    const [review, setReview] = useState<PRReview | null>(null);
    const [loading, setLoading] = useState(true);
    const [fixes, setFixes] = useState<FixProposal[]>([]);
    const [expandedIssue, setExpandedIssue] = useState<string | null>(null);
    const [fixingIssues, setFixingIssues] = useState<Set<string>>(new Set());
    const [activePlan, setActivePlan] = useState<SwarmPlan | null>(null);
    const [swarmBusy, setSwarmBusy] = useState(false);
    const [applyingAll, setApplyingAll] = useState(false);

    // ── Fetch review ────────────────────────────────────────────────────

    const fetchReview = useCallback(async () => {
        try {
            const data = await apiFetch<PRReview>(
                `/repos/${repoId}/prs/${prNumber}/review`
            );
            setReview(data);
        } catch {
            // PR may not have been reviewed yet — trigger review
            try {
                const planRes = await apiFetch<{ plan: SwarmPlan | null }>("/swarm/plan", {
                    method: "POST",
                    body: JSON.stringify({
                        repo_id: repoId,
                        pr_number: Number(prNumber),
                        mode: "pr_review",
                    }),
                });
                if (planRes.plan) setActivePlan(planRes.plan);

                // Fetch the newly created review
                const newData = await apiFetch<PRReview>(
                    `/repos/${repoId}/prs/${prNumber}/review`
                );
                setReview(newData);

                toast({ title: "PR review completed", description: "Claude has finished analyzing this PR." });
            } catch {
                // pass
            }
        } finally {
            setLoading(false);
        }
    }, [repoId, prNumber, toast]);

    useEffect(() => {
        fetchReview();
    }, [fetchReview]);

    // ── Fetch fixes when plan completes ─────────────────────────────────

    const fetchFixes = useCallback(async (planId: string) => {
        try {
            const data = await apiFetch<FixProposal[]>(`/swarm/plans/${planId}/fixes`);
            setFixes(data);
        } catch {
            // pass
        }
    }, []);

    // Listen for swarm events to update state
    useEffect(() => {
        const last = events[events.length - 1];
        if (!last) return;
        const payload = last.payload as Record<string, unknown> | undefined;
        if (!payload) return;

        if (last.event_type === "swarm_completed" && activePlan) {
            fetchFixes(activePlan.id);
            fetchReview();
            setSwarmBusy(false);
        }
        if (last.event_type === "swarm_agent_started" || last.event_type === "swarm_agent_completed") {
            // Update swarm progress
            if (activePlan) {
                setActivePlan((prev) =>
                    prev
                        ? {
                            ...prev,
                            tasks: prev.tasks.map((t) =>
                                t.id === payload.task_id
                                    ? {
                                        ...t,
                                        status:
                                            last.event_type === "swarm_agent_started"
                                                ? "running"
                                                : ((payload.status as SwarmTask["status"]) ?? "success"),
                                    }
                                    : t
                            ),
                        }
                        : prev
                );
            }
        }
    }, [events, activePlan, fetchFixes, fetchReview]);

    // ── Actions ─────────────────────────────────────────────────────────

    const handleFixIssue = async (issue: CodeIssue) => {
        setFixingIssues((prev) => new Set(prev).add(issue.id));
        try {
            const planRes = await apiFetch<{ plan: SwarmPlan | null }>("/swarm/plan", {
                method: "POST",
                body: JSON.stringify({
                    repo_id: repoId,
                    pr_number: Number(prNumber),
                    mode: "fix_issues",
                }),
            });
            if (planRes.plan?.id) {
                await apiFetch(`/swarm/plans/${planRes.plan.id}/execute`, { method: "POST" });
                setActivePlan(planRes.plan);
                toast({ title: "Fix in progress", description: `Fixing: ${issue.description.slice(0, 50)}…` });
            }
        } catch {
            toast({ title: "Fix failed", variant: "destructive" });
        } finally {
            setFixingIssues((prev) => {
                const next = new Set(prev);
                next.delete(issue.id);
                return next;
            });
        }
    };

    const handleDismissIssue = async (issue: CodeIssue) => {
        try {
            await apiFetch(`/swarm/issues/${issue.id}`, {
                method: "PATCH",
                body: JSON.stringify({ status: "dismissed" }),
            });
            setReview((prev) =>
                prev
                    ? {
                        ...prev,
                        issues: prev.issues.map((i) =>
                            i.id === issue.id ? { ...i, status: "dismissed" } : i
                        ),
                    }
                    : prev
            );
        } catch {
            toast({ title: "Could not dismiss", variant: "destructive" });
        }
    };

    const handleApplyFix = async (fix: FixProposal) => {
        if (!activePlan) return;
        try {
            await apiFetch(`/swarm/plans/${activePlan.id}/apply`, {
                method: "POST",
                body: JSON.stringify({ fix_ids: [fix.id] }),
            });
            setFixes((prev) => prev.map((f) => (f.id === fix.id ? { ...f, status: "applied" } : f)));
            toast({ title: "Fix applied", description: fix.file_path });
        } catch {
            toast({ title: "Apply failed", variant: "destructive" });
        }
    };

    const handleRejectFix = (fix: FixProposal) => {
        setFixes((prev) => prev.map((f) => (f.id === fix.id ? { ...f, status: "rejected" } : f)));
    };

    const handleFixAll = async () => {
        setSwarmBusy(true);
        try {
            const planRes = await apiFetch<{ plan: SwarmPlan | null }>("/swarm/plan", {
                method: "POST",
                body: JSON.stringify({
                    repo_id: repoId,
                    pr_number: Number(prNumber),
                    mode: "fix_issues",
                }),
            });
            if (planRes.plan?.id) {
                setActivePlan(planRes.plan);
                await apiFetch(`/swarm/plans/${planRes.plan.id}/execute`, { method: "POST" });
                toast({ title: "Swarm dispatched", description: "Fixing all issues…" });
            }
        } catch {
            toast({ title: "Fix all failed", variant: "destructive" });
            setSwarmBusy(false);
        }
    };

    const handleApplyAllApproved = async () => {
        if (!activePlan) return;
        setApplyingAll(true);
        try {
            const result = await apiFetch<{ pr_url: string; fixes_applied: number }>(
                `/swarm/plans/${activePlan.id}/apply-all`,
                { method: "POST" }
            );
            toast({
                title: "PR created",
                description: `${result.fixes_applied} fixes applied → ${result.pr_url}`,
            });
        } catch {
            toast({ title: "Apply all failed", variant: "destructive" });
        } finally {
            setApplyingAll(false);
        }
    };

    // ── Swarm progress ──────────────────────────────────────────────────

    const runningTask = activePlan?.tasks.find((t) => t.status === "running");
    const completedCount = activePlan?.tasks.filter((t) => t.status === "success" || t.status === "failed").length ?? 0;
    const totalTasks = activePlan?.tasks.length ?? 0;

    // ── Render ──────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="space-y-6">
                <Skeleton className="h-10 w-64" />
                <div className="grid grid-cols-12 gap-6">
                    <Skeleton className="col-span-5 h-96" />
                    <Skeleton className="col-span-4 h-96" />
                    <Skeleton className="col-span-3 h-96" />
                </div>
            </div>
        );
    }

    const risk = RISK_STYLES[review?.risk_level ?? "low"];
    const verdict = VERDICT_STYLES[review?.verdict ?? "needs_discussion"];
    const proposedFixes = fixes.filter((f) => f.status === "proposed" || f.status === "approved");

    return (
        <div className="space-y-4">
            {/* ── Header ──────────────────────────────────────────── */}
            <div className="flex items-center gap-3">
                <button
                    onClick={() => router.push(`/repos/${repoId}/prs`)}
                    className="rounded-lg p-2 hover:bg-white/5 transition-colors"
                >
                    <ArrowLeft className="h-4 w-4 text-slate-400" />
                </button>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground font-mono">
                            #{prNumber}
                        </span>
                        <h2 className="text-xl font-bold tracking-tight truncate">
                            {review?.pr_title ?? `PR #${prNumber}`}
                        </h2>
                    </div>
                    {review && (
                        <p className="text-xs text-muted-foreground">
                            by {review.pr_author}
                        </p>
                    )}
                </div>
                {review && (
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className={`text-sm ${risk.bg}`}>
                            {risk.emoji} {review.risk_level}
                        </Badge>
                        <Badge variant="outline" className={`text-sm ${verdict.bg} ${verdict.color}`}>
                            {verdict.emoji} {verdict.label}
                        </Badge>
                    </div>
                )}
            </div>

            {/* ── Swarm Monitor Pipeline ──────────────────────────── */}
            {activePlan && activePlan.tasks.length > 0 && (
                <SwarmMonitor plan={activePlan} className="mb-2" />
            )}

            {/* ── Main 3-panel layout ─────────────────────────────── */}
            <div className="grid grid-cols-12 gap-4">
                {/* LEFT: PR Details (5 cols) */}
                <div className="col-span-12 lg:col-span-5 space-y-4">
                    {/* Summary */}
                    {review && (
                        <Card className="border-border/40 bg-card/60 backdrop-blur">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                                    <Sparkles className="h-4 w-4 text-indigo-400" />
                                    Claude&apos;s Analysis
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {review.summary}
                                </p>

                                {/* Verdict explanation */}
                                <div className={`rounded-lg p-3 ${verdict.bg}`}>
                                    <p className={`text-sm font-medium ${verdict.color}`}>
                                        {verdict.emoji} Verdict: {verdict.label}
                                    </p>
                                </div>

                                {/* Praise */}
                                {review.praise.length > 0 && (
                                    <div className="space-y-2">
                                        <h4 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                                            ✨ Done Well
                                        </h4>
                                        <ul className="space-y-1">
                                            {review.praise.map((p, i) => (
                                                <li
                                                    key={i}
                                                    className="text-xs text-muted-foreground flex items-start gap-2"
                                                >
                                                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                                                    {p}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Missing tests */}
                                {review.missing_tests.length > 0 && (
                                    <div className="space-y-2">
                                        <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                                            🧪 Missing Tests
                                        </h4>
                                        <ul className="space-y-1">
                                            {review.missing_tests.map((t, i) => (
                                                <li
                                                    key={i}
                                                    className="text-xs text-muted-foreground"
                                                >
                                                    <span className="font-mono text-amber-400/80">
                                                        {t.file}
                                                    </span>{" "}
                                                    — {t.description}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {/* Empty state */}
                    {!review && (
                        <Card className="border-border/40 bg-card/60 backdrop-blur">
                            <CardContent className="flex flex-col items-center py-12 text-center">
                                <Loader2 className="h-8 w-8 text-indigo-400 animate-spin mb-3" />
                                <h3 className="text-sm font-semibold">Analyzing PR…</h3>
                                <p className="text-xs text-muted-foreground">
                                    Claude is reviewing the changes
                                </p>
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* MIDDLE: Issues (4 cols) */}
                <div className="col-span-12 lg:col-span-4 space-y-3">
                    <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                        <Bug className="h-4 w-4 text-red-400" />
                        Issues
                        {review && (
                            <Badge variant="secondary" className="text-[10px] ml-auto">
                                {review.issues.filter((i) => i.status !== "dismissed").length}
                            </Badge>
                        )}
                    </h3>

                    <div className="space-y-2 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
                        {!review?.issues.length && (
                            <Card className="border-border/40 bg-card/60">
                                <CardContent className="py-8 text-center">
                                    <CheckCircle2 className="h-6 w-6 text-emerald-400 mx-auto mb-2" />
                                    <p className="text-xs text-muted-foreground">
                                        No issues found
                                    </p>
                                </CardContent>
                            </Card>
                        )}

                        {review?.issues.map((issue) => {
                            const isExpanded = expandedIssue === issue.id;
                            const isFixing = fixingIssues.has(issue.id);
                            const status = STATUS_STYLES[issue.status] ?? STATUS_STYLES.open;

                            return (
                                <Card
                                    key={issue.id}
                                    className={`border-border/40 bg-card/60 backdrop-blur transition-all ${issue.status === "dismissed" ? "opacity-50" : ""
                                        }`}
                                >
                                    <CardContent className="p-3 space-y-2">
                                        {/* File + badges */}
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <p className="text-xs font-mono text-indigo-400 truncate">
                                                    {issue.file_path}
                                                    {issue.line_number && (
                                                        <span className="text-muted-foreground">
                                                            :{issue.line_number}
                                                        </span>
                                                    )}
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-1.5 shrink-0">
                                                <Badge
                                                    variant="outline"
                                                    className={`text-[10px] ${SEVERITY_STYLES[issue.severity] ?? ""
                                                        }`}
                                                >
                                                    {issue.severity}
                                                </Badge>
                                                <span className="text-xs">
                                                    {TYPE_EMOJI[issue.issue_type] ?? "📋"}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Description */}
                                        <p className="text-xs text-foreground/90">
                                            {issue.description}
                                        </p>

                                        {/* Suggestion */}
                                        {issue.suggestion && (
                                            <p className="text-xs text-muted-foreground italic">
                                                💡 {issue.suggestion}
                                            </p>
                                        )}

                                        {/* Status + actions */}
                                        <div className="flex items-center justify-between pt-1 border-t border-border/20">
                                            <span className={`text-[10px] font-medium ${status.color}`}>
                                                {status.label}
                                            </span>
                                            <div className="flex items-center gap-1">
                                                {issue.status === "open" && (
                                                    <>
                                                        <button
                                                            onClick={() => handleFixIssue(issue)}
                                                            disabled={isFixing}
                                                            className="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium text-indigo-400 hover:bg-indigo-500/10 disabled:opacity-50 transition-colors"
                                                        >
                                                            {isFixing ? (
                                                                <Loader2 className="h-3 w-3 animate-spin" />
                                                            ) : (
                                                                <Wrench className="h-3 w-3" />
                                                            )}
                                                            Fix
                                                        </button>
                                                        <button
                                                            onClick={() => handleDismissIssue(issue)}
                                                            className="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium text-slate-500 hover:bg-white/5 transition-colors"
                                                        >
                                                            <X className="h-3 w-3" />
                                                            Dismiss
                                                        </button>
                                                    </>
                                                )}
                                                <button
                                                    onClick={() =>
                                                        setExpandedIssue(isExpanded ? null : issue.id)
                                                    }
                                                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium text-slate-400 hover:bg-white/5 transition-colors"
                                                >
                                                    <Eye className="h-3 w-3" />
                                                    {isExpanded ? (
                                                        <ChevronUp className="h-3 w-3" />
                                                    ) : (
                                                        <ChevronDown className="h-3 w-3" />
                                                    )}
                                                </button>
                                            </div>
                                        </div>

                                        {/* Expanded: code snippet placeholder */}
                                        {isExpanded && (
                                            <div className="rounded-md bg-[#0a0e1a] border border-border/30 p-3 mt-1">
                                                <p className="text-[10px] text-muted-foreground mb-1 font-mono">
                                                    {issue.file_path}
                                                    {issue.line_number && `:${issue.line_number}`}
                                                </p>
                                                <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
                                                    {issue.suggestion
                                                        ? `// Issue: ${issue.description}\n// Suggestion: ${issue.suggestion}`
                                                        : `// Issue: ${issue.description}`}
                                                </pre>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </div>

                {/* RIGHT: Fix Proposals (3 cols) */}
                <div className="col-span-12 lg:col-span-3 space-y-3">
                    <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                        <Wrench className="h-4 w-4 text-emerald-400" />
                        Fix Proposals
                        {proposedFixes.length > 0 && (
                            <Badge variant="secondary" className="text-[10px] ml-auto">
                                {proposedFixes.length}
                            </Badge>
                        )}
                    </h3>

                    <div className="space-y-2 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
                        {fixes.length === 0 && (
                            <Card className="border-border/40 bg-card/60">
                                <CardContent className="py-8 text-center">
                                    <Sparkles className="h-6 w-6 text-indigo-400/50 mx-auto mb-2" />
                                    <p className="text-xs text-muted-foreground">
                                        No fixes yet — click &quot;Fix&quot; on an issue
                                    </p>
                                </CardContent>
                            </Card>
                        )}

                        {fixes.map((fix) => (
                            <FixDiffViewer
                                key={fix.id}
                                fix={fix}
                                onApply={handleApplyFix}
                                onReject={handleRejectFix}
                            />
                        ))}
                    </div>
                </div>
            </div>

            {/* ── Bottom bar: Swarm Control ────────────────────────── */}
            <div className="sticky bottom-0 z-30 -mx-6 px-6 py-3 bg-[#0B1120]/90 backdrop-blur-md border-t border-border/30">
                <div className="flex items-center justify-between gap-4">
                    {/* Swarm progress */}
                    <div className="flex items-center gap-3 min-w-0">
                        {swarmBusy && runningTask && (
                            <>
                                <Loader2 className="h-4 w-4 text-indigo-400 animate-spin shrink-0" />
                                <span className="text-xs text-muted-foreground truncate">
                                    Agent {completedCount + 1}/{totalTasks} ·{" "}
                                    <span className="text-indigo-400 capitalize">
                                        {runningTask.agent_type.replace("_", " ")}
                                    </span>{" "}
                                    {runningTask.target_files[0]
                                        ? `analyzing ${runningTask.target_files[0]}`
                                        : runningTask.task_description.slice(0, 50)}
                                </span>
                            </>
                        )}
                        {!swarmBusy && proposedFixes.length > 0 && (
                            <span className="text-xs text-emerald-400">
                                {proposedFixes.length} fix{proposedFixes.length !== 1 ? "es" : ""}{" "}
                                ready to apply
                            </span>
                        )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                        <button
                            onClick={handleFixAll}
                            disabled={swarmBusy || !review?.issues.length}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-500 disabled:opacity-50 transition-all"
                        >
                            {swarmBusy ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                                <Play className="h-3.5 w-3.5" />
                            )}
                            Fix All Issues
                        </button>
                        <button
                            onClick={handleApplyAllApproved}
                            disabled={applyingAll || proposedFixes.length === 0}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-medium text-white shadow-lg shadow-emerald-500/20 hover:bg-emerald-500 disabled:opacity-50 transition-all"
                        >
                            {applyingAll ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                                <Send className="h-3.5 w-3.5" />
                            )}
                            Apply All → PR
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
