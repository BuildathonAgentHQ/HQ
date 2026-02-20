"use client";

import { useState } from "react";
import type { Task } from "@/lib/types";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Clock,
    Zap,
    CheckCircle2,
    XCircle,
    Pause,
    ChevronDown,
    ChevronUp,
} from "lucide-react";

const STATUS_CONFIG: Record<
    string,
    { color: string; bg: string; icon: React.ReactNode }
> = {
    pending: {
        color: "text-slate-400",
        bg: "bg-slate-500/10",
        icon: <Clock className="h-3.5 w-3.5" />,
    },
    running: {
        color: "text-blue-400",
        bg: "bg-blue-500/10",
        icon: <Zap className="h-3.5 w-3.5 animate-pulse" />,
    },
    success: {
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
        icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    },
    failed: {
        color: "text-red-400",
        bg: "bg-red-500/10",
        icon: <XCircle className="h-3.5 w-3.5" />,
    },
    suspended: {
        color: "text-amber-400",
        bg: "bg-amber-500/10",
        icon: <Pause className="h-3.5 w-3.5" />,
    },
};

function getElapsed(created: string): string {
    const diff = Date.now() - new Date(created).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ${mins % 60}m`;
}

function getBudgetColor(ratio: number): string {
    if (ratio < 0.6) return "bg-emerald-500";
    if (ratio < 0.85) return "bg-amber-500";
    return "bg-red-500";
}

interface TaskCardProps {
    task: Task;
    events?: Array<{ status: string; timestamp: string }>;
}

export function TaskCard({ task, events = [] }: TaskCardProps) {
    const [expanded, setExpanded] = useState(false);
    const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;
    const budgetRatio =
        task.budget_limit > 0 ? task.budget_used / task.budget_limit : 0;
    const budgetPct = Math.min(budgetRatio * 100, 100);

    return (
        <Card
            className="border-border/30 bg-white/[0.03] backdrop-blur cursor-pointer transition-all hover:bg-white/[0.05] hover:border-border/50 animate-fade-in"
            onClick={() => setExpanded(!expanded)}
        >
            <CardContent className="py-4 space-y-3">
                {/* ── Top row ──────────────────────────────────────────── */}
                <div className="flex items-start gap-3">
                    <span className={`mt-0.5 ${cfg.color}`}>{cfg.icon}</span>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium line-clamp-2">{task.task}</p>
                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                            <Badge
                                variant="secondary"
                                className={`text-[10px] px-1.5 py-0 ${cfg.bg} ${cfg.color}`}
                            >
                                {task.status}
                            </Badge>
                            <Badge
                                variant="outline"
                                className="text-[10px] px-1.5 py-0 border-border/40"
                            >
                                {task.engine}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {getElapsed(task.created_at)}
                            </span>
                        </div>
                    </div>
                    <span className="text-muted-foreground/50">
                        {expanded ? (
                            <ChevronUp className="h-4 w-4" />
                        ) : (
                            <ChevronDown className="h-4 w-4" />
                        )}
                    </span>
                </div>

                {/* ── Budget bar ───────────────────────────────────────── */}
                <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                        <span>Budget</span>
                        <span className="tabular-nums">
                            ${task.budget_used.toFixed(2)} / ${task.budget_limit.toFixed(2)}
                        </span>
                    </div>
                    <Progress
                        value={budgetPct}
                        className="h-1.5"
                        indicatorClassName={getBudgetColor(budgetRatio)}
                    />
                </div>

                {/* ── Expanded detail ──────────────────────────────────── */}
                {expanded && (
                    <div className="pt-2 border-t border-border/20 space-y-2 animate-fade-in">
                        <p className="text-xs text-muted-foreground">{task.task}</p>
                        {events.length > 0 && (
                            <div className="space-y-1">
                                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                                    Recent events
                                </p>
                                {events.slice(0, 5).map((ev, i) => (
                                    <p key={i} className="text-xs text-muted-foreground/80 pl-2 border-l border-border/30">
                                        {ev.status}
                                    </p>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
