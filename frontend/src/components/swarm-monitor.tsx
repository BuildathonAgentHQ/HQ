"use client";

import { useMemo } from "react";
import type { SwarmTask, SwarmPlan } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
    Eye,
    FlaskConical,
    Wrench,
    Lock,
    FileText,
    Zap,
    Loader2,
    CheckCircle2,
    XCircle,
    Clock,
    ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Agent visuals ──────────────────────────────────────────────────────────

const AGENT_CONFIG: Record<
    string,
    {
        icon: typeof Eye;
        label: string;
        color: string;
        bg: string;
    }
> = {
    reviewer: {
        icon: Eye,
        label: "Reviewer",
        color: "text-sky-400",
        bg: "bg-sky-500/10 border-sky-500/30",
    },
    test_writer: {
        icon: FlaskConical,
        label: "Test Writer",
        color: "text-violet-400",
        bg: "bg-violet-500/10 border-violet-500/30",
    },
    refactor: {
        icon: Wrench,
        label: "Refactor",
        color: "text-amber-400",
        bg: "bg-amber-500/10 border-amber-500/30",
    },
    security_auditor: {
        icon: Lock,
        label: "Security",
        color: "text-red-400",
        bg: "bg-red-500/10 border-red-500/30",
    },
    doc_writer: {
        icon: FileText,
        label: "Docs",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10 border-emerald-500/30",
    },
    fix_generator: {
        icon: Zap,
        label: "Fix Gen",
        color: "text-indigo-400",
        bg: "bg-indigo-500/10 border-indigo-500/30",
    },
    coordinator: {
        icon: Zap,
        label: "Coordinator",
        color: "text-cyan-400",
        bg: "bg-cyan-500/10 border-cyan-500/30",
    },
};

const STATUS_ICON: Record<string, { icon: typeof Clock; color: string }> = {
    pending: { icon: Clock, color: "text-slate-500" },
    running: { icon: Loader2, color: "text-indigo-400" },
    success: { icon: CheckCircle2, color: "text-emerald-400" },
    failed: { icon: XCircle, color: "text-red-400" },
};

function miniSummary(task: SwarmTask): string | null {
    if (task.status !== "success" || !task.result) return null;
    const r = task.result as Record<string, unknown>;

    // Reviewer / security auditor
    const issues = r.issues ?? r.vulnerabilities;
    if (Array.isArray(issues)) {
        return `Found ${issues.length} issue${issues.length !== 1 ? "s" : ""}`;
    }

    // Fix generator
    if (r.fixed_code) return `Generated fix for ${task.target_files[0]?.split("/").pop() ?? "file"}`;

    // Test writer
    if (r.test_code) return `Wrote tests → ${r.test_file_path ?? "tests"}`;

    // Refactor
    const changes = r.changes;
    if (Array.isArray(changes)) return `${changes.length} refactor${changes.length !== 1 ? "s" : ""}`;

    // Doc writer
    if (r.content) return `Generated ${r.doc_type ?? "docs"}`;

    return "Done";
}

// ── Dependency-level grouping ──────────────────────────────────────────────

function groupByLevel(tasks: SwarmTask[]): SwarmTask[][] {
    const taskMap = new Map(tasks.map((t) => [t.id, t]));
    const levels: SwarmTask[][] = [];
    const placed = new Set<string>();

    while (placed.size < tasks.length) {
        const level: SwarmTask[] = [];
        for (const t of tasks) {
            if (placed.has(t.id)) continue;
            const depsReady = t.depends_on.every((d) => placed.has(d));
            if (depsReady) level.push(t);
        }
        if (level.length === 0) {
            // remaining tasks have circular deps — dump them
            for (const t of tasks) if (!placed.has(t.id)) level.push(t);
        }
        for (const t of level) placed.add(t.id);
        levels.push(level);
    }
    return levels;
}

// ── Component ──────────────────────────────────────────────────────────────

interface SwarmMonitorProps {
    plan: SwarmPlan;
    className?: string;
}

export function SwarmMonitor({ plan, className }: SwarmMonitorProps) {
    const levels = useMemo(() => groupByLevel(plan.tasks), [plan.tasks]);

    if (plan.tasks.length === 0) return null;

    return (
        <div className={cn("w-full", className)}>
            {/* Header */}
            <div className="flex flex-col gap-1 mb-4">
                <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Swarm Pipeline
                    </h4>
                    <Badge
                        variant="outline"
                        className={cn(
                            "text-[10px]",
                            plan.status === "executing"
                                ? "border-indigo-500/30 text-indigo-400"
                                : plan.status === "completed"
                                    ? "border-emerald-500/30 text-emerald-400"
                                    : plan.status === "failed"
                                        ? "border-red-500/30 text-red-400"
                                        : "border-slate-500/30 text-slate-400"
                        )}
                    >
                        {plan.status}
                    </Badge>
                </div>

                {/* Association Subtitle */}
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {plan.pr_number ? (
                        <span className="font-medium text-emerald-400">PR #{plan.pr_number}</span>
                    ) : (
                        <span className="font-medium text-indigo-400">Repo Audit</span>
                    )}
                    <span className="text-slate-600">•</span>
                    <span className="truncate">{plan.plan_summary}</span>
                </div>
            </div>

            {/* Pipeline */}
            <div className="flex items-start gap-2 overflow-x-auto pb-2 scrollbar-thin">
                {levels.map((level, li) => (
                    <div key={li} className="flex items-start gap-2">
                        {/* Level column */}
                        <div className="flex flex-col gap-2 min-w-[160px]">
                            {level.map((task) => (
                                <TaskNode key={task.id} task={task} />
                            ))}
                        </div>

                        {/* Arrow between levels */}
                        {li < levels.length - 1 && (
                            <div className="flex items-center self-center px-1 shrink-0">
                                <ArrowRight className="h-4 w-4 text-slate-600" />
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Summary line */}
            {plan.status === "completed" && (
                <p className="text-xs text-muted-foreground mt-2">
                    ✅ Completed — {plan.total_fixes_proposed} fix
                    {plan.total_fixes_proposed !== 1 ? "es" : ""} proposed
                </p>
            )}
        </div>
    );
}

// ── Individual task node ───────────────────────────────────────────────────

function TaskNode({ task }: { task: SwarmTask }) {
    const agent = AGENT_CONFIG[task.agent_type] ?? AGENT_CONFIG.fix_generator;
    const statusCfg = STATUS_ICON[task.status] ?? STATUS_ICON.pending;
    const StatusIcon = statusCfg.icon;
    const AgentIcon = agent.icon;
    const summary = miniSummary(task);

    const isRunning = task.status === "running";

    return (
        <div
            className={cn(
                "relative rounded-lg border p-3 transition-all",
                agent.bg,
                isRunning && "animate-pulse-border",
                task.status === "failed" && "border-red-500/40 bg-red-500/5"
            )}
        >
            {/* Header row: icon + name + status */}
            <div className="flex items-center gap-2 mb-1.5">
                <AgentIcon className={cn("h-3.5 w-3.5 shrink-0", agent.color)} />
                <span className={cn("text-xs font-medium", agent.color)}>{agent.label}</span>
                <StatusIcon
                    className={cn(
                        "h-3.5 w-3.5 ml-auto shrink-0",
                        statusCfg.color,
                        isRunning && "animate-spin"
                    )}
                />
            </div>

            {/* Target files */}
            {task.target_files.length > 0 && (
                <div className="space-y-0.5 mb-1">
                    {task.target_files.slice(0, 2).map((f) => (
                        <p key={f} className="text-[10px] text-muted-foreground font-mono truncate">
                            {f}
                        </p>
                    ))}
                    {task.target_files.length > 2 && (
                        <p className="text-[10px] text-muted-foreground/60">
                            +{task.target_files.length - 2} more
                        </p>
                    )}
                </div>
            )}

            {/* Task description (truncated) */}
            {!summary && task.status === "running" && (
                <p className="text-[10px] text-muted-foreground/80 truncate">
                    {task.task_description.slice(0, 60)}…
                </p>
            )}

            {/* Completion summary */}
            {summary && (
                <p className="text-[10px] text-emerald-400/90 font-medium">{summary}</p>
            )}

            {/* Token/cost */}
            {task.tokens_used > 0 && (
                <p className="text-[9px] text-muted-foreground/40 mt-1">
                    {(task.tokens_used / 1000).toFixed(1)}k tok · ${task.cost.toFixed(3)}
                </p>
            )}
        </div>
    );
}
