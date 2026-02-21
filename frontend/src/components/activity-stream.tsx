"use client";

import { useState, useMemo } from "react";
import type { WebSocketEvent, TranslatedEvent, ApprovalRequest, DebateResult } from "@/lib/types";
import { EventType } from "@/lib/constants";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApprovalModal } from "@/components/approval-modal";
import { DecisionGate } from "@/components/decision-gate";
import { BudgetCard } from "@/components/budget-card";

import {
    Activity,
    Cpu,
    Zap,
    CheckCircle2,
    AlertCircle,
    Send,
    Clock,
    Trash2,
    Bot,
    GitFork,
    Eye,
    Shield,
    Wrench,
} from "lucide-react";

/* ── Category visual config ─────────────────────────────────────── */
const CATEGORY_CONFIG: Record<
    string,
    { color: string; dotColor: string; icon: React.ReactNode }
> = {
    setup: { color: "text-cyan-400", dotColor: "bg-cyan-400", icon: <Cpu className="h-3.5 w-3.5" /> },
    coding: { color: "text-indigo-400", dotColor: "bg-indigo-400", icon: <Zap className="h-3.5 w-3.5" /> },
    testing: { color: "text-emerald-400", dotColor: "bg-emerald-400", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
    debugging: { color: "text-amber-400", dotColor: "bg-amber-400", icon: <AlertCircle className="h-3.5 w-3.5" /> },
    deploying: { color: "text-purple-400", dotColor: "bg-purple-400", icon: <Send className="h-3.5 w-3.5" /> },
    waiting: { color: "text-slate-400", dotColor: "bg-slate-400", icon: <Clock className="h-3.5 w-3.5" /> },
    completed: { color: "text-emerald-400", dotColor: "bg-emerald-400", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
    // Swarm categories
    swarm: { color: "text-violet-400", dotColor: "bg-violet-400", icon: <Bot className="h-3.5 w-3.5" /> },
    repo: { color: "text-cyan-400", dotColor: "bg-cyan-400", icon: <GitFork className="h-3.5 w-3.5" /> },
    review: { color: "text-indigo-400", dotColor: "bg-indigo-400", icon: <Eye className="h-3.5 w-3.5" /> },
    fix: { color: "text-emerald-400", dotColor: "bg-emerald-400", icon: <Wrench className="h-3.5 w-3.5" /> },
};

const SEVERITY_DOT: Record<string, string> = {
    info: "bg-emerald-400",
    warning: "bg-amber-400",
    error: "bg-red-400",
};

const CATEGORY_BADGE_COLORS: Record<string, string> = {
    setup: "bg-cyan-500/10 text-cyan-400",
    coding: "bg-indigo-500/10 text-indigo-400",
    testing: "bg-emerald-500/10 text-emerald-400",
    debugging: "bg-amber-500/10 text-amber-400",
    deploying: "bg-purple-500/10 text-purple-400",
    waiting: "bg-slate-500/10 text-slate-400",
    completed: "bg-emerald-500/10 text-emerald-400",
    swarm: "bg-violet-500/10 text-violet-400",
    repo: "bg-cyan-500/10 text-cyan-400",
    review: "bg-indigo-500/10 text-indigo-400",
    fix: "bg-emerald-500/10 text-emerald-400",
};

/* ── Swarm event mapping ─────────────────────────────────────────── */

const SWARM_EVENT_MAP: Record<string, { category: string; icon: string; format: (p: Record<string, unknown>) => string }> = {
    repo_added: {
        category: "repo",
        icon: "📦",
        format: (p) => `Repository connected: ${p.repo_name ?? p.full_name ?? "repo"}`,
    },
    repo_analyzed: {
        category: "repo",
        icon: "🔍",
        format: (p) => `Analysis complete: ${p.repo_name ?? p.full_name ?? "repo"} — health ${p.health_score ?? "?"}`,
    },
    pr_reviewed: {
        category: "review",
        icon: "✅",
        format: (p) => `PR #${p.pr_number ?? "?"} reviewed — ${p.risk_level ?? "?"} risk, ${p.verdict ?? "?"}`,
    },
    swarm_started: {
        category: "swarm",
        icon: "🤖",
        format: (p) => `Swarm started: ${p.plan_summary ?? `${p.task_count ?? "?"} agents deploying`}`,
    },
    swarm_agent_started: {
        category: "swarm",
        icon: "🔄",
        format: (p) => `${String(p.agent_type ?? "agent").replace("_", " ")} started → ${p.target_file ?? p.task_description ?? ""}`,
    },
    swarm_agent_completed: {
        category: "swarm",
        icon: "✓",
        format: (p) => `${String(p.agent_type ?? "agent").replace("_", " ")} done${p.summary ? `: ${p.summary}` : ""}`,
    },
    swarm_completed: {
        category: "swarm",
        icon: "🏁",
        format: (p) => `Swarm completed — ${p.fixes_proposed ?? 0} fixes proposed`,
    },
    fix_proposed: {
        category: "fix",
        icon: "💡",
        format: (p) => `Proposed fix for ${p.file_path ?? "file"}: ${String(p.explanation ?? "").slice(0, 60)}`,
    },
    fix_applied: {
        category: "fix",
        icon: "🚀",
        format: (p) => `Fix applied → PR #${p.pr_number ?? p.pr_url ?? "created"}`,
    },
};

function isSwarmEvent(eventType: string): boolean {
    return eventType in SWARM_EVENT_MAP;
}

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return "just now";
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

const MAX_VISIBLE = 50;

interface ActivityStreamProps {
    events: WebSocketEvent[];
    sendMessage: (msg: unknown) => void;
}

export function ActivityStream({ events, sendMessage }: ActivityStreamProps) {
    const [cleared, setCleared] = useState(0);
    const [approvalReq, setApprovalReq] = useState<(ApprovalRequest & { task_id: string }) | null>(null);
    const [debateReq, setDebateReq] = useState<(DebateResult & { task_id: string }) | null>(null);

    const visibleEvents = useMemo(
        () => events.slice(0, events.length - cleared).slice(0, MAX_VISIBLE),
        [events, cleared]
    );

    // Check for approval/budget/debate events
    const specialEvents = useMemo(() => {
        const budget: WebSocketEvent[] = [];
        events.forEach((evt) => {
            if (evt.event_type === EventType.APPROVAL_REQUIRED && !approvalReq) {
                setApprovalReq({ ...(evt.payload as unknown as ApprovalRequest), task_id: evt.task_id });
            }
            if (evt.event_type === EventType.DEBATE && !debateReq) {
                setDebateReq({ ...(evt.payload as unknown as DebateResult), task_id: evt.task_id });
            }
            if (evt.event_type === EventType.BUDGET_EXCEEDED) {
                budget.push(evt);
            }
        });
        return { budget };
    }, [events, approvalReq, debateReq]);

    const handleClear = () => setCleared(events.length);

    /* ── Empty state ──────────────────────────────────────────────── */
    if (visibleEvents.length === 0) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Activity className="h-4 w-4 text-indigo-400" />
                        Live Activity
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="flex items-center gap-3">
                            <Skeleton className="h-3 w-3 rounded-full" />
                            <Skeleton className="h-4 flex-1" />
                        </div>
                    ))}
                    <p className="text-xs text-muted-foreground/60 text-center pt-2">
                        Waiting for agent activity…
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <>
            {/* ── Approval modal ──────────────────────────────────────── */}
            {approvalReq && (
                <ApprovalModal
                    approvalRequest={approvalReq}
                    onResolve={(option) => {
                        sendMessage({
                            type: "approval_response",
                            task_id: approvalReq.task_id,
                            option,
                        });
                        setApprovalReq(null);
                    }}
                />
            )}

            {/* ── Decision gate ───────────────────────────────────────── */}
            {debateReq && (
                <DecisionGate
                    debate={debateReq}
                    onResolve={(option) => {
                        sendMessage({
                            type: "debate_response",
                            task_id: debateReq.task_id,
                            option,
                        });
                        setDebateReq(null);
                    }}
                />
            )}

            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Activity className="h-4 w-4 text-indigo-400" />
                        Live Activity
                        <Badge variant="secondary" className="ml-auto text-[10px]">
                            {visibleEvents.length} events
                        </Badge>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-muted-foreground hover:text-white"
                            onClick={handleClear}
                        >
                            <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 max-h-[500px] overflow-y-auto">
                    {/* Budget inline cards */}
                    {specialEvents.budget.map((evt, i) => (
                        <BudgetCard
                            key={`budget-${i}`}
                            event={evt}
                            onAction={(action) =>
                                sendMessage({
                                    type: "approval_response",
                                    task_id: evt.task_id,
                                    option: action,
                                })
                            }
                        />
                    ))}

                    {/* Event timeline */}
                    {visibleEvents.map((evt, i) => {
                        const payload = evt.payload as unknown as (TranslatedEvent & Record<string, unknown>);

                        // ── Swarm / repo / review events ──────────────────
                        if (isSwarmEvent(evt.event_type)) {
                            const mapping = SWARM_EVENT_MAP[evt.event_type];
                            const config = CATEGORY_CONFIG[mapping.category] ?? CATEGORY_CONFIG.swarm;
                            const badgeColor = CATEGORY_BADGE_COLORS[mapping.category] ?? CATEGORY_BADGE_COLORS.swarm;
                            const message = mapping.format(payload ?? {});
                            const isSwarmCore = mapping.category === "swarm";

                            return (
                                <div
                                    key={`${evt.timestamp}-${i}`}
                                    className={`flex items-start gap-3 rounded-md px-3 py-2 transition-colors hover:bg-white/[0.02] animate-fade-in ${isSwarmCore ? "bg-violet-500/[0.03] border-l-2 border-violet-500/30" : ""
                                        }`}
                                    style={{ animationDelay: `${i * 30}ms` }}
                                >
                                    <span className="mt-1 text-sm shrink-0">{mapping.icon}</span>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm leading-relaxed">{message}</p>
                                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                                            <Badge
                                                variant="secondary"
                                                className={`text-[10px] px-1.5 py-0 ${badgeColor}`}
                                            >
                                                {mapping.category}
                                            </Badge>
                                            <span className="text-[10px] text-muted-foreground/40 ml-auto">
                                                {relativeTime(evt.timestamp)}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            );
                        }

                        // ── Standard agent events ─────────────────────────
                        const severity = payload?.severity || "info";
                        const category = payload?.category || "coding";
                        const config = CATEGORY_CONFIG[category] || CATEGORY_CONFIG.coding;

                        return (
                            <div
                                key={`${evt.timestamp}-${i}`}
                                className="flex items-start gap-3 rounded-md px-3 py-2 transition-colors hover:bg-white/[0.02] animate-fade-in"
                                style={{ animationDelay: `${i * 30}ms` }}
                            >
                                {/* Severity dot */}
                                <span
                                    className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${SEVERITY_DOT[severity] || SEVERITY_DOT.info
                                        }`}
                                />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm leading-relaxed">
                                        {payload?.status || "Processing…"}
                                    </p>
                                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                                        <Badge
                                            variant="secondary"
                                            className={`text-[10px] px-1.5 py-0 ${CATEGORY_BADGE_COLORS[category] || ""
                                                }`}
                                        >
                                            {category}
                                        </Badge>
                                        <span className="text-[10px] text-muted-foreground/60">
                                            {evt.task_id.slice(0, 8)}
                                        </span>
                                        <span className="text-[10px] text-muted-foreground/40 ml-auto">
                                            {relativeTime(evt.timestamp)}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </CardContent>
            </Card>
        </>
    );
}
