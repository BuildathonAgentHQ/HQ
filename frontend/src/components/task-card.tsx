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
    AlertTriangle,
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

function formatAgentType(agentType: string): string {
    return agentType
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
}

interface TaskCardProps {
    task: Task;
    events?: Array<{ status: string; timestamp: string }>;
    /** When provided, clicking the card calls this instead of toggling expand. */
    onSelect?: (task: Task) => void;
}

export function TaskCard({ task, events = [], onSelect }: TaskCardProps) {
    const [expanded, setExpanded] = useState(false);
    const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;
    const budgetRatio =
        task.budget_limit > 0 ? task.budget_used / task.budget_limit : 0;
    const budgetPct = Math.min(budgetRatio * 100, 100);

    const handleClick = () => {
        if (onSelect) onSelect(task);
        else setExpanded(!expanded);
    };

    return (
        <Card
            className="border-border/30 bg-white/[0.03] backdrop-blur cursor-pointer transition-all hover:bg-white/[0.05] hover:border-border/50 animate-fade-in"
            onClick={handleClick}
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
                            <Badge
                                variant="outline"
                                className="text-[10px] px-1.5 py-0 border-indigo-500/30 text-indigo-300"
                            >
                                {formatAgentType(task.agent_type)}
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

                {/* ── Failure reason ────────────────────────────────────── */}
                {task.status === "failed" && (() => {
                    // Search events backward for the most relevant error message
                    const failEvent = [...events].reverse().find(ev =>
                        /error|fail|crash|exception|abort/i.test(ev.status)
                    );
                    const reason = failEvent?.status ?? "Task failed (no details available)";
                    return (
                        <div className="flex items-start gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 mt-1">
                            <AlertTriangle className="h-3.5 w-3.5 text-red-400 mt-0.5 shrink-0" />
                            <p className="text-xs text-red-300 line-clamp-2">{reason}</p>
                        </div>
                    );
                })()}

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
                    <div className="pt-3 border-t border-border/20 space-y-3 animate-fade-in">
                        {/* Task description */}
                        <p className="text-xs text-muted-foreground/90">{task.task}</p>

                        {/* Metadata row */}
                        <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
                            {task.agent_type && (
                                <span>Type: <span className="text-slate-300">{task.agent_type}</span></span>
                            )}
                            {task.token_count != null && task.token_count > 0 && (
                                <span>Tokens: <span className="text-slate-300">{task.token_count.toLocaleString()}</span></span>
                            )}
                            {task.exit_code != null && (
                                <span>Exit: <span className={task.exit_code === 0 ? "text-emerald-400" : "text-red-400"}>{task.exit_code}</span></span>
                            )}
                            {task.strike_count != null && task.strike_count > 0 && (
                                <span>Strikes: <span className="text-amber-400">{task.strike_count}</span></span>
                            )}
                        </div>

                        {/* Event log */}
                        {events.length > 0 ? (
                            <div className="space-y-1">
                                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                                    Activity Log ({events.length} events)
                                </p>
                                <div className="max-h-48 overflow-y-auto space-y-0.5 pr-1">
                                    {events.map((ev, i) => (
                                        <div key={i} className="flex items-start gap-2 text-xs pl-2 border-l-2 border-indigo-500/20 py-0.5">
                                            <span className="text-[9px] text-muted-foreground/50 shrink-0 tabular-nums w-14">
                                                {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                                            </span>
                                            <span className="text-muted-foreground/80">{ev.status}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <p className="text-[10px] text-muted-foreground/60 italic">
                                No events logged yet. Events will appear here as the agent runs.
                            </p>
                        )}

                        {/* Export button */}
                        <div className="pt-1">
                            <button
                                className="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    const data = {
                                        task_id: task.id,
                                        task: task.task,
                                        engine: task.engine,
                                        agent_type: task.agent_type,
                                        status: task.status,
                                        budget_used: task.budget_used,
                                        budget_limit: task.budget_limit,
                                        token_count: task.token_count,
                                        created_at: task.created_at,
                                        updated_at: task.updated_at,
                                        events: events,
                                    };
                                    // Download as JSON for Databricks ingestion
                                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = `task_${task.id.slice(0, 8)}_export.json`;
                                    a.click();
                                    URL.revokeObjectURL(url);
                                }}
                            >
                                📤 Export for Databricks
                            </button>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
