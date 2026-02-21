"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useWebSocket } from "@/hooks/use-websocket";
import { API_BASE_URL, WS_URL } from "@/lib/constants";
import type { Task, Repository, PRReview, SwarmPlan } from "@/lib/types";

import { CommandInput } from "@/components/command-input";
import { ActivityStream } from "@/components/activity-stream";
import { HealthRadar } from "@/components/health-radar";
import { TaskCard } from "@/components/task-card";
import { Leaderboard } from "@/components/leaderboard";
import { TimelineSlider } from "@/components/timeline-slider";
import { SwarmMonitor } from "@/components/swarm-monitor";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
<<<<<<< HEAD
import { Cpu, Github, ExternalLink } from "lucide-react";
import { API_BASE_URL } from "@/lib/constants";
=======
import {
    Cpu,
    GitFork,
    Eye,
    Bot,
    ExternalLink,
    ArrowRight,
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
>>>>>>> c29f998 (Latest Update)

export default function DashboardPage() {
    const { events, isConnected, sendMessage } = useWebSocket(WS_URL);
    const [tasks, setTasks] = useState<Task[] | null>(null);
<<<<<<< HEAD
    const [repo, setRepo] = useState<{ repo_name: string; repo_url: string; repo_owner: string } | null>(null);

    useEffect(() => {
        getTasks()
            .then(setTasks)
            .catch(() => { });
        fetch(`${API_BASE_URL}/config/repo`)
            .then((r) => r.ok ? r.json() : null)
            .then((data) => data && data.repo_name && setRepo(data))
            .catch(() => {});
=======
    const [repos, setRepos] = useState<Repository[] | null>(null);
    const [reviews, setReviews] = useState<PRReview[] | null>(null);
    const [swarms, setSwarms] = useState<SwarmPlan[] | null>(null);

    useEffect(() => {
        apiFetch<Task[]>("/tasks/").then(setTasks).catch(() => setTasks([]));
        apiFetch<Repository[]>("/repos").then(setRepos).catch(() => setRepos([]));
        apiFetch<PRReview[]>("/control-plane/reviews/recent").then(setReviews).catch(() => setReviews([]));
        apiFetch<SwarmPlan[]>("/swarm/plans/active").then(setSwarms).catch(() => setSwarms([]));
>>>>>>> c29f998 (Latest Update)
    }, []);

    return (
        <div className="space-y-6">
            {/* ── Header ──────────────────────────────────────────── */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
                        {repo && (
                            <a
                                href={repo.repo_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1.5 rounded-full bg-white/5 border border-border/40 px-3 py-1 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors group"
                            >
                                <Github className="h-3.5 w-3.5" />
                                <span>{repo.repo_owner}/{repo.repo_name}</span>
                                <ExternalLink className="h-3 w-3 text-slate-500 group-hover:text-white" />
                            </a>
                        )}
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
                                        <span className="text-sm font-medium text-white truncate">
                                            {repo.full_name}
                                        </span>
                                        <span className={`text-xs font-bold ${healthColor(repo.health_score)}`}>
                                            {repo.health_score ?? "—"}
                                        </span>
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
                            Active Swarms
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

            {/* ── Main grid: Activity + Radar ────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <ActivityStream events={events} sendMessage={sendMessage} />
                </div>
                <div>
                    <HealthRadar />
                </div>
            </div>

            {/* ── Task cards + Leaderboard ───────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Active Tasks */}
                <Card className="border-border/40 bg-card/60 backdrop-blur">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Cpu className="h-4 w-4 text-violet-400" />
                            Active Tasks
                            {tasks && (
                                <Badge variant="secondary" className="ml-auto text-[10px]">
                                    {tasks.length}
                                </Badge>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
                        {!tasks ? (
                            Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-24 w-full" />
                            ))
                        ) : tasks.length === 0 ? (
                            <p className="text-sm text-muted-foreground/60 text-center py-6">
                                No tasks yet. Deploy your first agent above.
                            </p>
                        ) : (
                            tasks.map((t) => <TaskCard key={t.id} task={t} />)
                        )}
                    </CardContent>
                </Card>

                {/* Leaderboard */}
                <Leaderboard />
            </div>

            {/* ── Timeline ───────────────────────────────────────── */}
            <TimelineSlider />
        </div>
    );
}
