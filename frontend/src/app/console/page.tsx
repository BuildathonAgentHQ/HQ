"use client";

import { useEffect, useState } from "react";
import { getTasks } from "@/hooks/use-api";
import type { Task } from "@/lib/types";

import { TaskCard } from "@/components/task-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Terminal } from "lucide-react";

export default function ConsolePage() {
    const [tasks, setTasks] = useState<Task[] | null>(null);

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

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <Terminal className="h-7 w-7 text-indigo-400" />
                    Agent Console
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    All running and completed tasks
                </p>
            </div>

            {/* Status filter */}
            <div className="flex gap-2">
                {["all", "running", "pending", "success", "failed", "suspended"].map(
                    (s) => (
                        <Badge
                            key={s}
                            variant="secondary"
                            className="capitalize cursor-pointer hover:bg-white/10 transition-colors"
                        >
                            {s}
                        </Badge>
                    )
                )}
            </div>

            {/* Task grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {!tasks ? (
                    Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-32 w-full rounded-lg" />
                    ))
                ) : tasks.length === 0 ? (
                    <div className="col-span-full flex items-center justify-center h-64">
                        <p className="text-sm text-muted-foreground/60">
                            No tasks yet. Deploy agents from the Dashboard.
                        </p>
                    </div>
                ) : (
                    tasks.map((t) => <TaskCard key={t.id} task={t} />)
                )}
            </div>
        </div>
    );
}
