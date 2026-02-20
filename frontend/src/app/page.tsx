"use client";

import { useEffect, useState } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import {
    getTasks,
    getRadarMetrics,
    getLeaderboard,
    createTask,
} from "@/hooks/use-api";
import { WS_URL } from "@/lib/constants";
import type {
    Task,
    TaskCreate,
    TelemetryMetrics,
    AgentLeaderboardEntry,
    WebSocketEvent,
    TranslatedEvent,
} from "@/lib/types";

// ── shadcn/ui ──────────────────────────────────────────────────────────────
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

// ── Recharts ───────────────────────────────────────────────────────────────
import {
    RadarChart,
    PolarGrid,
    PolarAngleAxis,
    PolarRadiusAxis,
    Radar,
    ResponsiveContainer,
    Tooltip,
} from "recharts";

// ── Lucide icons ───────────────────────────────────────────────────────────
import {
    Send,
    Activity,
    Cpu,
    Trophy,
    Zap,
    AlertCircle,
    CheckCircle2,
    Clock,
    XCircle,
    Pause,
} from "lucide-react";

// ═══════════════════════════════════════════════════════════════════════════════
//  CommandInput — task submission form
// ═══════════════════════════════════════════════════════════════════════════════

function CommandInput({
    onSubmit,
}: {
    onSubmit: (data: TaskCreate) => void;
}) {
    const [task, setTask] = useState("");
    const [engine, setEngine] = useState<"claude-code" | "cursor-cli">(
        "claude-code"
    );

    const handleSubmit = () => {
        if (!task.trim()) return;
        onSubmit({ task, engine, agent_type: "general", budget_limit: 2.0, context_sources: [] });
        setTask("");
    };

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardContent className="pt-6">
                <div className="flex gap-3">
                    <Input
                        placeholder="Describe the task for the agent…"
                        value={task}
                        onChange={(e) => setTask(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                        className="flex-1 bg-background/50 border-border/40 text-foreground placeholder:text-muted-foreground"
                    />
                    <Select
                        value={engine}
                        onValueChange={(v) => setEngine(v as "claude-code" | "cursor-cli")}
                    >
                        <SelectTrigger className="w-[160px] bg-background/50 border-border/40">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="claude-code">Claude Code</SelectItem>
                            <SelectItem value="cursor-cli">Cursor CLI</SelectItem>
                        </SelectContent>
                    </Select>
                    <Button
                        onClick={handleSubmit}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2"
                    >
                        <Send className="h-4 w-4" />
                        Deploy
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ActivityStream — live event feed
// ═══════════════════════════════════════════════════════════════════════════════

const CATEGORY_CONFIG: Record<
    string,
    { color: string; icon: React.ReactNode }
> = {
    setup: { color: "text-cyan-400", icon: <Cpu className="h-3.5 w-3.5" /> },
    coding: { color: "text-indigo-400", icon: <Zap className="h-3.5 w-3.5" /> },
    testing: { color: "text-emerald-400", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
    debugging: { color: "text-amber-400", icon: <AlertCircle className="h-3.5 w-3.5" /> },
    deploying: { color: "text-purple-400", icon: <Send className="h-3.5 w-3.5" /> },
    waiting: { color: "text-slate-400", icon: <Clock className="h-3.5 w-3.5" /> },
    completed: { color: "text-emerald-400", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
};

function ActivityStream({ events }: { events: WebSocketEvent[] }) {
    // Extract translated events from WebSocketEvent payloads
    const translatedEvents = events
        .filter((e) => e.event_type === "status_update" && e.payload?.status)
        .slice(0, 15);

    if (translatedEvents.length === 0) {
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
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Activity className="h-4 w-4 text-indigo-400" />
                    Live Activity
                    <Badge variant="secondary" className="ml-auto text-[10px]">
                        {translatedEvents.length} events
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5 max-h-[400px] overflow-y-auto">
                {translatedEvents.map((evt, i) => {
                    const payload = evt.payload as unknown as TranslatedEvent;
                    const category = payload.category || "coding";
                    const config = CATEGORY_CONFIG[category] || CATEGORY_CONFIG.coding;
                    return (
                        <div
                            key={`${evt.timestamp}-${i}`}
                            className="flex items-start gap-3 rounded-md px-3 py-2 transition-colors hover:bg-white/[0.02] animate-fade-in"
                        >
                            <span className={`mt-0.5 ${config.color}`}>{config.icon}</span>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm leading-relaxed">{payload.status}</p>
                                <div className="flex items-center gap-2 mt-0.5">
                                    <Badge
                                        variant={
                                            payload.severity === "error"
                                                ? "destructive"
                                                : "secondary"
                                        }
                                        className="text-[10px] px-1.5 py-0"
                                    >
                                        {category}
                                    </Badge>
                                    {payload.is_error && (
                                        <span className="text-[10px] text-red-400">● Error</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </CardContent>
        </Card>
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  HealthRadar — recharts radar chart
// ═══════════════════════════════════════════════════════════════════════════════

function HealthRadar({ metrics }: { metrics: TelemetryMetrics | null }) {
    if (!metrics) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Activity className="h-4 w-4 text-cyan-400" />
                        Health Radar
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <Skeleton className="h-[250px] w-full rounded-lg" />
                </CardContent>
            </Card>
        );
    }

    const data = [
        { metric: "Security", value: metrics.security },
        { metric: "Stability", value: metrics.stability },
        { metric: "Quality", value: metrics.quality },
        { metric: "Speed", value: metrics.speed },
    ];

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Activity className="h-4 w-4 text-cyan-400" />
                    Health Radar
                </CardTitle>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                    <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
                        <PolarGrid stroke="hsl(217 33% 17%)" />
                        <PolarAngleAxis
                            dataKey="metric"
                            tick={{ fill: "#94a3b8", fontSize: 12 }}
                        />
                        <PolarRadiusAxis
                            angle={90}
                            domain={[0, 100]}
                            tick={{ fill: "#475569", fontSize: 10 }}
                            axisLine={false}
                        />
                        <Tooltip
                            contentStyle={{
                                background: "#1e293b",
                                border: "1px solid #334155",
                                borderRadius: 8,
                                color: "#e2e8f0",
                                fontSize: 12,
                            }}
                        />
                        <Radar
                            dataKey="value"
                            stroke="#6366f1"
                            fill="#6366f1"
                            fillOpacity={0.25}
                            strokeWidth={2}
                        />
                    </RadarChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  LeaderboardTable — engine rankings
// ═══════════════════════════════════════════════════════════════════════════════

const STATUS_ICON: Record<string, React.ReactNode> = {
    pending: <Clock className="h-3 w-3 text-slate-400" />,
    running: <Zap className="h-3 w-3 text-indigo-400" />,
    success: <CheckCircle2 className="h-3 w-3 text-emerald-400" />,
    failed: <XCircle className="h-3 w-3 text-red-400" />,
    suspended: <Pause className="h-3 w-3 text-amber-400" />,
};

function LeaderboardTable({
    entries,
}: {
    entries: AgentLeaderboardEntry[] | null;
}) {
    if (!entries) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Trophy className="h-4 w-4 text-amber-400" />
                        Agent Leaderboard
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-12 w-full" />
                    ))}
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Trophy className="h-4 w-4 text-amber-400" />
                    Agent Leaderboard
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {/* Header row */}
                    <div className="grid grid-cols-5 text-[11px] text-muted-foreground font-medium px-3 pb-1">
                        <span>Engine</span>
                        <span className="text-right">Tasks</span>
                        <span className="text-right">Success</span>
                        <span className="text-right">Avg Time</span>
                        <span className="text-right">Avg Cost</span>
                    </div>
                    <Separator className="opacity-20" />
                    {entries.map((entry, i) => (
                        <div
                            key={entry.engine}
                            className="grid grid-cols-5 items-center rounded-lg px-3 py-2.5 text-sm hover:bg-white/[0.03] transition-colors"
                        >
                            <span className="flex items-center gap-2 font-medium">
                                <span className="text-xs text-muted-foreground">{i + 1}.</span>
                                {entry.engine}
                            </span>
                            <span className="text-right tabular-nums">
                                {entry.tasks_completed}
                            </span>
                            <span className="text-right tabular-nums">
                                <Badge
                                    variant="secondary"
                                    className={
                                        entry.success_rate >= 0.9
                                            ? "bg-emerald-500/10 text-emerald-400"
                                            : entry.success_rate >= 0.8
                                                ? "bg-amber-500/10 text-amber-400"
                                                : "bg-red-500/10 text-red-400"
                                    }
                                >
                                    {(entry.success_rate * 100).toFixed(0)}%
                                </Badge>
                            </span>
                            <span className="text-right tabular-nums text-muted-foreground">
                                {Math.round(entry.avg_duration_seconds)}s
                            </span>
                            <span className="text-right tabular-nums text-muted-foreground">
                                ${entry.avg_cost_dollars.toFixed(2)}
                            </span>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  TaskList — compact task cards
// ═══════════════════════════════════════════════════════════════════════════════

function TaskList({ tasks }: { tasks: Task[] | null }) {
    if (!tasks) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Cpu className="h-4 w-4 text-violet-400" />
                        Active Tasks
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-16 w-full" />
                    ))}
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Cpu className="h-4 w-4 text-violet-400" />
                    Active Tasks
                    <Badge variant="secondary" className="ml-auto text-[10px]">
                        {tasks.length}
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 max-h-[350px] overflow-y-auto">
                {tasks.map((task) => (
                    <div
                        key={task.id}
                        className="flex items-start gap-3 rounded-lg border border-border/30 px-4 py-3 hover:bg-white/[0.02] transition-colors"
                    >
                        <span className="mt-1">{STATUS_ICON[task.status]}</span>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{task.task}</p>
                            <div className="flex items-center gap-3 mt-1">
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                    {task.engine}
                                </Badge>
                                <span className="text-[10px] text-muted-foreground">
                                    ${task.budget_used.toFixed(2)} / ${task.budget_limit.toFixed(2)}
                                </span>
                            </div>
                        </div>
                        <Badge
                            variant="secondary"
                            className={
                                task.status === "success"
                                    ? "bg-emerald-500/10 text-emerald-400"
                                    : task.status === "failed"
                                        ? "bg-red-500/10 text-red-400"
                                        : task.status === "running"
                                            ? "bg-indigo-500/10 text-indigo-400"
                                            : task.status === "suspended"
                                                ? "bg-amber-500/10 text-amber-400"
                                                : "bg-slate-500/10 text-slate-400"
                            }
                        >
                            {task.status}
                        </Badge>
                    </div>
                ))}
            </CardContent>
        </Card>
    );
}

// ═══════════════════════════════════════════════════════════════════════════════
//  Dashboard Page
// ═══════════════════════════════════════════════════════════════════════════════

export default function DashboardPage() {
    const { events, isConnected, sendMessage } = useWebSocket(WS_URL);

    const [tasks, setTasks] = useState<Task[] | null>(null);
    const [radar, setRadar] = useState<TelemetryMetrics | null>(null);
    const [leaderboard, setLeaderboard] = useState<AgentLeaderboardEntry[] | null>(null);

    // Fetch initial data
    useEffect(() => {
        getTasks().then(setTasks).catch(() => { });
        getRadarMetrics().then(setRadar).catch(() => { });
        getLeaderboard().then(setLeaderboard).catch(() => { });
    }, []);

    const handleCreateTask = async (data: TaskCreate) => {
        try {
            const task = await createTask(data);
            setTasks((prev) => (prev ? [task, ...prev] : [task]));
        } catch {
            // TODO: show toast
        }
    };

    return (
        <div className="space-y-6">
            {/* ── Header stats ─────────────────────────────────────── */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
                    <p className="text-sm text-muted-foreground">
                        Monitor and deploy autonomous coding agents
                    </p>
                </div>
                <div className="flex items-center gap-2 text-sm">
                    <span
                        className={`inline-block h-2 w-2 rounded-full ${isConnected
                            ? "bg-emerald-500 shadow-[0_0_6px_theme(colors.emerald.500)]"
                            : "bg-red-500 shadow-[0_0_6px_theme(colors.red.500)]"
                            }`}
                    />
                    <span className="text-muted-foreground">
                        {isConnected ? "Live" : "Connecting…"}
                    </span>
                </div>
            </div>

            {/* ── Command Input ────────────────────────────────────── */}
            <CommandInput onSubmit={handleCreateTask} />

            {/* ── Main grid ────────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left: Activity Stream */}
                <div className="lg:col-span-2">
                    <ActivityStream events={events} />
                </div>
                {/* Right: Health Radar */}
                <div>
                    <HealthRadar metrics={radar} />
                </div>
            </div>

            {/* ── Bottom grid ──────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <TaskList tasks={tasks} />
                <LeaderboardTable entries={leaderboard} />
            </div>
        </div>
    );
}
