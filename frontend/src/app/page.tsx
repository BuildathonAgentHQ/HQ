"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import Link from "next/link";
import { useWebSocket } from "@/hooks/use-websocket";
import { API_BASE_URL, WS_URL } from "@/lib/constants";
import type { Task, Repository, PRReview, SwarmPlan } from "@/lib/types";

import { CommandInput } from "@/components/command-input";
import { ActivityStream } from "@/components/activity-stream";
import { HealthRadar } from "@/components/health-radar";
import { TaskCard } from "@/components/task-card";
import { Leaderboard } from "@/components/leaderboard";
import { SwarmMonitor } from "@/components/swarm-monitor";
import { RepoSelector } from "@/components/repo-selector";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Cpu,
    GitFork,
    Eye,
    Bot,
    ExternalLink,
    ArrowRight,
    RefreshCw,
} from "lucide-react";

// ── API helpers ────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json() as Promise<T>;
}

// ── Visual helpers ─────────────────────────────────────────────────────────

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

const RISK_BADGE: Record<string, string> = {
    low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    high: "bg-orange-500/10 text-orange-400 border-orange-500/20",
    critical: "bg-red-500/10 text-red-400 border-red-500/20",
};

const VERDICT_BADGE: Record<string, { emoji: string; label: string; color: string }> = {
    approve: { emoji: "✅", label: "Approve", color: "text-emerald-400" },
    request_changes: { emoji: "🔄", label: "Changes", color: "text-orange-400" },
    needs_discussion: { emoji: "💬", label: "Discuss", color: "text-amber-400" },
};

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

// ── Page Component ─────────────────────────────────────────────────────────

export default function DashboardPage() {
    const { events, isConnected, sendMessage } = useWebSocket(WS_URL);
    const [tasks, setTasks] = useState<Task[] | null>(null);
    const [repos, setRepos] = useState<Repository[] | null>(null);
    const [reviews, setReviews] = useState<PRReview[] | null>(null);
    const [swarms, setSwarms] = useState<SwarmPlan[] | null>(null);
    const [refreshingTasks, setRefreshingTasks] = useState(false);
    const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);

    const refreshTasks = useCallback(async () => {
        setRefreshingTasks(true);
        try {
            const data = await apiFetch<Task[]>("/tasks/");
            setTasks(data);
        } catch {
            setTasks([]);
        } finally {
            setRefreshingTasks(false);
        }
    }, []);

    const refreshAll = useCallback(() => {
        refreshTasks();
        apiFetch<PRReview[]>("/control-plane/reviews/recent").then(setReviews).catch(() => setReviews([]));
        apiFetch<SwarmPlan[]>("/swarm/plans/active").then(setSwarms).catch(() => setSwarms([]));
    }, [refreshTasks]);

    useEffect(() => {
        apiFetch<Repository[]>("/repos").then(setRepos).catch(() => setRepos([]));
        refreshAll();
        const id = setInterval(refreshAll, 10_000);
        return () => clearInterval(id);
    }, [refreshAll]);

    const [dashTab, setDashTab] = useState<"activity" | "tasks">("activity");

    // Group events by task_id for TaskCards
    const eventsByTask = useMemo(() => {
        const map: Record<string, Array<{ status: string; timestamp: string }>> = {};
        for (const evt of events) {
            if (!evt.task_id) continue;
            const payload = evt.payload as Record<string, unknown> | undefined;
            const status = String(payload?.status ?? payload?.message ?? evt.event_type ?? "");
            const timestamp = String(evt.timestamp ?? new Date().toISOString());
            if (!map[evt.task_id]) map[evt.task_id] = [];
            map[evt.task_id].push({ status, timestamp });
        }
        return map;
    }, [events]);

    return (
        <div className="space-y-6">
            {/* ── Header ──────────────────────────────────────────── */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
                        <RepoSelector
                            selectedRepoId={selectedRepoId}
                            onRepoChange={(id) => setSelectedRepoId(id)}
                        />
                    </div>
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

            {/* ── Command Input ──────────────────────────────────── */}
            <CommandInput />

            {/* ── Connected Repositories ──────────────────────────── */}
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <GitFork className="h-4 w-4 text-cyan-400" />
                        Connected Repositories
                        {repos && (
                            <Badge variant="secondary" className="ml-auto text-[10px]">
                                {repos.length}
                            </Badge>
                        )}
                        <Link
                            href="/repos"
                            className="text-xs text-muted-foreground hover:text-white transition-colors flex items-center gap-1"
                        >
                            View all <ArrowRight className="h-3 w-3" />
                        </Link>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {repos === null ? (
                        <div className="flex gap-3 overflow-x-auto pb-1">
                            {[1, 2, 3].map((i) => (
                                <Skeleton key={i} className="h-20 w-56 shrink-0 rounded-lg" />
                            ))}
                        </div>
                    ) : repos.length === 0 ? (
                        <p className="text-xs text-muted-foreground/60 text-center py-4">
                            No repositories connected.{" "}
                            <Link href="/repos" className="text-indigo-400 hover:underline">
                                Connect one →
                            </Link>
                        </p>
                    ) : (
                        <div className="flex gap-3 overflow-x-auto pb-1">
                            {repos.slice(0, 6).map((repo) => (
                                <Link
                                    key={repo.id}
                                    href={`/repos/${repo.id}/prs`}
                                    className="shrink-0 rounded-lg border border-border/30 bg-card/40 px-4 py-3 min-w-[200px] hover:border-indigo-500/30 transition-all"
                                >
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm font-medium text-white truncate min-w-0 mr-2 flex-1">
                                            {repo.full_name}
                                        </span>
                                        <Badge variant="outline" className={`text-[10px] font-bold shrink-0 ${healthColor(repo.health_score)}`}>
                                            {repo.health_score ?? "—"}
                                        </Badge>
                                    </div>
                                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                                        <span>{repo.tech_stack.slice(0, 2).join(", ") || "—"}</span>
                                        <span className="ml-auto">{timeAgo(repo.last_analyzed)}</span>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ── Recent Reviews + Active Swarms ──────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Recent Reviews */}
                <Card className="border-border/40 bg-card/60 backdrop-blur">
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Eye className="h-4 w-4 text-indigo-400" />
                            Recent Reviews
                            {reviews && reviews.length > 0 && (
                                <Badge variant="secondary" className="ml-auto text-[10px]">
                                    {reviews.length}
                                </Badge>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 max-h-[300px] overflow-y-auto">
                        {reviews === null ? (
                            [1, 2].map((i) => <Skeleton key={i} className="h-16 w-full" />)
                        ) : reviews.length === 0 ? (
                            <p className="text-xs text-muted-foreground/60 text-center py-6">
                                No reviews yet
                            </p>
                        ) : (
                            reviews.slice(0, 5).map((r) => {
                                const verd = VERDICT_BADGE[r.verdict];
                                return (
                                    <div
                                        key={r.id}
                                        className="flex items-center gap-3 rounded-md px-3 py-2.5 bg-card/40 border border-border/20 hover:border-indigo-500/20 transition-all"
                                    >
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-white truncate">
                                                PR #{r.pr_number}: {r.pr_title}
                                            </p>
                                            <p className="text-[10px] text-muted-foreground truncate">
                                                {r.summary.slice(0, 80)}…
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-1.5 shrink-0">
                                            <Badge variant="outline" className={`text-[10px] ${RISK_BADGE[r.risk_level]}`}>
                                                {r.risk_level}
                                            </Badge>
                                            <span className={`text-xs ${verd?.color ?? ""}`}>
                                                {verd?.emoji}
                                            </span>
                                        </div>
                                    </div>
                                );
                            })
                        )}
                    </CardContent>
                </Card>

                {/* Active Swarms */}
                <Card className="border-border/40 bg-card/60 backdrop-blur">
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Bot className="h-4 w-4 text-violet-400" />
                            Active Swarm
                            {swarms && swarms.filter((s) => s.status === "executing").length > 0 && (
                                <Badge className="ml-auto text-[10px] bg-violet-500/15 text-violet-400 animate-pulse">
                                    {swarms.filter((s) => s.status === "executing").length} running
                                </Badge>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 max-h-[300px] overflow-y-auto">
                        {swarms === null ? (
                            <Skeleton className="h-24 w-full" />
                        ) : swarms.length === 0 ? (
                            <p className="text-xs text-muted-foreground/60 text-center py-6">
                                No active swarms
                            </p>
                        ) : (
                            swarms.slice(0, 3).map((plan) => (
                                <SwarmMonitor key={plan.id} plan={plan} />
                            ))
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* ── Activity + Tasks (tabbed) + Health Radar ─────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <Card className="border-border/40 bg-card/60 backdrop-blur">
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center gap-0 text-base">
                                <div className="flex gap-1 rounded-lg bg-white/[0.04] p-0.5">
                                    <button
                                        onClick={() => setDashTab("activity")}
                                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${dashTab === "activity"
                                                ? "bg-indigo-500/20 text-indigo-300 shadow-sm"
                                                : "text-muted-foreground hover:text-white"
                                            }`}
                                    >
                                        Live Activity
                                    </button>
                                    <button
                                        onClick={() => setDashTab("tasks")}
                                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${dashTab === "tasks"
                                                ? "bg-indigo-500/20 text-indigo-300 shadow-sm"
                                                : "text-muted-foreground hover:text-white"
                                            }`}
                                    >
                                        Active Tasks
                                        {tasks && (
                                            <span className="ml-1.5 text-[10px] opacity-60">{tasks.length}</span>
                                        )}
                                    </button>
                                </div>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {dashTab === "activity" ? (
                                <ActivityStream events={events} sendMessage={sendMessage} />
                            ) : (
                                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                                    {!tasks ? (
                                        Array.from({ length: 3 }).map((_, i) => (
                                            <Skeleton key={i} className="h-24 w-full" />
                                        ))
                                    ) : tasks.length === 0 ? (
                                        <p className="text-sm text-muted-foreground/60 text-center py-6">
                                            No tasks yet. Deploy your first agent above.
                                        </p>
                                    ) : (
                                        tasks.map((t) => <TaskCard key={t.id} task={t} events={eventsByTask[t.id] ?? []} />)
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
                <div>
                    <HealthRadar />
                </div>
            </div>

            {/* ── Leaderboard ──────────────────────────────── */}
            <Leaderboard />


        </div>
    );
}
