"use client";

import { useEffect, useState } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import { getTasks } from "@/hooks/use-api";
import { WS_URL } from "@/lib/constants";
import type { Task } from "@/lib/types";

import { CommandInput } from "@/components/command-input";
import { ActivityStream } from "@/components/activity-stream";
import { HealthRadar } from "@/components/health-radar";
import { TaskCard } from "@/components/task-card";
import { Leaderboard } from "@/components/leaderboard";
import { TimelineSlider } from "@/components/timeline-slider";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Cpu } from "lucide-react";

export default function DashboardPage() {
    const { events, isConnected, sendMessage } = useWebSocket(WS_URL);
    const [tasks, setTasks] = useState<Task[] | null>(null);

    useEffect(() => {
        getTasks()
            .then(setTasks)
            .catch(() => { });
    }, []);

    return (
        <div className="space-y-6">
            {/* ── Header ──────────────────────────────────────────── */}
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

            {/* ── Command Input ──────────────────────────────────── */}
            <CommandInput />

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
