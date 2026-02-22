"use client";

import { useEffect, useState, useMemo } from "react";
import { getTasks } from "@/hooks/use-api";
import { useWebSocket } from "@/hooks/use-websocket";
import { WS_URL } from "@/lib/constants";
import type { Task } from "@/lib/types";

import { TaskCard } from "@/components/task-card";
import { TaskDetailSheet } from "@/components/task-detail-sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Terminal } from "lucide-react";

type StatusFilter = "all" | "running" | "pending" | "success" | "failed" | "suspended";

export default function ConsolePage() {
    const [tasks, setTasks] = useState<Task[] | null>(null);
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [selectedTask, setSelectedTask] = useState<Task | null>(null);
    const [sheetOpen, setSheetOpen] = useState(false);
    const { events, isConnected } = useWebSocket(WS_URL);

    const filteredTasks = useMemo(() => {
        if (!tasks) return null;
        if (statusFilter === "all") return tasks;
        return tasks.filter((t) => t.status === statusFilter);
    }, [tasks, statusFilter]);

    useEffect(() => {
        getTasks()
            .then(setTasks)
            .catch(() => { });
        const id = setInterval(() => {
            getTasks()
                .then(setTasks)
                .catch(() => { });
        }, 10_000);
        return () => clearInterval(id);
    }, []);

    const handleSelectTask = (task: Task) => {
        setSelectedTask(task);
        setSheetOpen(true);
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <Terminal className="h-7 w-7 text-indigo-400" />
                    Agent Console
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    All running and completed tasks — click a task to view details and chat
                </p>
            </div>

            {/* Status filter */}
            <div className="flex gap-2 flex-wrap">
                {(["all", "running", "pending", "success", "failed", "suspended"] as const).map(
                    (s) => (
                        <Badge
                            key={s}
                            variant="secondary"
                            className={`capitalize cursor-pointer hover:bg-white/10 transition-colors ${
                                statusFilter === s ? "ring-1 ring-indigo-500/50 bg-indigo-500/10" : ""
                            }`}
                            onClick={() => setStatusFilter(s)}
                        >
                            {s}
                        </Badge>
                    )
                )}
                <span className="text-xs text-muted-foreground self-center ml-2">
                    {isConnected ? (
                        <span className="text-emerald-500">● Live</span>
                    ) : (
                        <span className="text-amber-500">○ Connecting…</span>
                    )}
                </span>
            </div>

            {/* Task grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {!filteredTasks ? (
                    Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-32 w-full rounded-lg" />
                    ))
                ) : filteredTasks.length === 0 ? (
                    <div className="col-span-full flex items-center justify-center h-64">
                        <p className="text-sm text-muted-foreground/60">
                            {statusFilter === "all"
                                ? "No tasks yet. Deploy agents from the Dashboard."
                                : `No ${statusFilter} tasks.`}
                        </p>
                    </div>
                ) : (
                    filteredTasks.map((t) => (
                        <TaskCard
                            key={t.id}
                            task={t}
                            onSelect={handleSelectTask}
                        />
                    ))
                )}
            </div>

            {/* Task detail sheet with chat */}
            <TaskDetailSheet
                task={selectedTask}
                open={sheetOpen}
                onOpenChange={setSheetOpen}
                events={events}
            />
        </div>
    );
}
