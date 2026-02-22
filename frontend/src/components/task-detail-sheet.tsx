"use client";

import { useState } from "react";
import type { Task, WebSocketEvent } from "@/lib/types";
import { injectPrompt } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";

import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Bot,
    Send,
    Zap,
    Clock,
    CheckCircle2,
    XCircle,
    Pause,
} from "lucide-react";

const STATUS_CONFIG: Record<
    string,
    { color: string; icon: React.ReactNode }
> = {
    pending: { color: "text-slate-400", icon: <Clock className="h-4 w-4" /> },
    running: { color: "text-blue-400", icon: <Zap className="h-4 w-4 animate-pulse" /> },
    success: { color: "text-emerald-400", icon: <CheckCircle2 className="h-4 w-4" /> },
    failed: { color: "text-red-400", icon: <XCircle className="h-4 w-4" /> },
    suspended: { color: "text-amber-400", icon: <Pause className="h-4 w-4" /> },
};

function formatAgentType(agentType: string): string {
    return agentType
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
}

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return "just now";
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ago`;
}

interface TaskDetailSheetProps {
    task: Task | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    events: WebSocketEvent[];
}

export function TaskDetailSheet({
    task,
    open,
    onOpenChange,
    events,
}: TaskDetailSheetProps) {
    const [chatInput, setChatInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const { toast } = useToast();

    const taskEvents = task
        ? events.filter((e) => e.task_id === task.id)
        : [];

    const canChat = task?.status === "running";

    const handleSend = async () => {
        if (!task || !chatInput.trim() || !canChat || isSending) return;
        setIsSending(true);
        try {
            await injectPrompt(task.id, chatInput.trim());
            setChatInput("");
            toast({
                title: "Message sent",
                description: "Your message was injected into the agent.",
            });
        } catch (err) {
            toast({
                title: "Failed to send",
                description: err instanceof Error ? err.message : "Could not inject message.",
                variant: "destructive",
            });
        } finally {
            setIsSending(false);
        }
    };

    if (!task) return null;

    const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent
                side="right"
                className="w-full sm:max-w-lg flex flex-col p-0"
            >
                <SheetHeader className="px-6 pt-6 pb-4 border-b border-border/30">
                    <SheetTitle className="text-left flex items-center gap-2">
                        <span className={cfg.color}>{cfg.icon}</span>
                        Task: {task.task.slice(0, 50)}
                        {task.task.length > 50 && "…"}
                    </SheetTitle>
                    <div className="flex flex-wrap gap-2 mt-2">
                        <Badge variant="secondary" className={cfg.color}>
                            {task.status}
                        </Badge>
                        <Badge variant="outline" className="border-indigo-500/40">
                            <Bot className="h-3 w-3 mr-1" />
                            {task.engine} / {formatAgentType(task.agent_type)}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                            ${task.budget_used.toFixed(2)} / ${task.budget_limit.toFixed(2)}
                        </span>
                    </div>
                </SheetHeader>

                {/* Agent assignment */}
                <div className="px-6 py-3 bg-indigo-500/5 border-b border-border/20">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                        Agent performing this task
                    </p>
                    <p className="text-sm font-medium text-indigo-300">
                        {task.engine} — {formatAgentType(task.agent_type)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                        {task.task}
                    </p>
                </div>

                {/* Events stream */}
                <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2 min-h-0">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                        Activity ({taskEvents.length})
                    </p>
                    {taskEvents.length === 0 ? (
                        <p className="text-xs text-muted-foreground/60">
                            No events yet for this task.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {[...taskEvents].reverse().map((evt, i) => {
                                const payload = evt.payload as Record<string, unknown>;
                                const status = payload?.status ?? evt.event_type;
                                return (
                                    <div
                                        key={`${evt.timestamp}-${i}`}
                                        className="text-xs rounded-md px-3 py-2 bg-white/[0.02] border-l-2 border-indigo-500/30"
                                    >
                                        <p className="text-muted-foreground">
                                            {String(status)}
                                        </p>
                                        <span className="text-[10px] text-muted-foreground/60">
                                            {relativeTime(evt.timestamp)}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Chat input */}
                <div className="px-6 py-4 border-t border-border/30">
                    {canChat ? (
                        <div className="flex gap-2">
                            <Input
                                placeholder="Send a message to the agent…"
                                value={chatInput}
                                onChange={(e) => setChatInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSend();
                                    }
                                }}
                                className="flex-1 bg-white/[0.04] border-white/10"
                            />
                            <Button
                                size="icon"
                                onClick={handleSend}
                                disabled={!chatInput.trim() || isSending}
                                className="shrink-0"
                            >
                                <Send className="h-4 w-4" />
                            </Button>
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground/70">
                            Chat is only available for running tasks. This task is{" "}
                            <span className="font-medium">{task.status}</span>.
                        </p>
                    )}
                </div>
            </SheetContent>
        </Sheet>
    );
}
