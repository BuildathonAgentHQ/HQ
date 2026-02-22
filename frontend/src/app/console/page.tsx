"use client";

<<<<<<< Updated upstream
import { useEffect, useState, useMemo } from "react";
import { getTasks } from "@/hooks/use-api";
import { useWebSocket } from "@/hooks/use-websocket";
import { WS_URL } from "@/lib/constants";
import type { Task } from "@/lib/types";

import { TaskCard } from "@/components/task-card";
import { TaskDetailSheet } from "@/components/task-detail-sheet";
import { Skeleton } from "@/components/ui/skeleton";
=======
import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { getTasks, injectPrompt, cancelTask, suspendTask, resumeTask } from "@/hooks/use-api";
import { useWebSocket } from "@/hooks/use-websocket";
import { WS_URL } from "@/lib/constants";
import type { Task, WebSocketEvent, TranslatedEvent } from "@/lib/types";

>>>>>>> Stashed changes
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import {
    Terminal,
    Zap,
    Clock,
    CheckCircle2,
    XCircle,
    Pause,
    Send,
    Play,
    Square,
    PauseCircle,
    Bot,
    ChevronRight,
    MessageSquare,
    Cpu,
} from "lucide-react";

const STATUS_CONFIG: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
    pending: { color: "text-slate-400", bg: "bg-slate-500/10", icon: <Clock className="h-3.5 w-3.5" />, label: "Pending" },
    running: { color: "text-blue-400", bg: "bg-blue-500/10", icon: <Zap className="h-3.5 w-3.5 animate-pulse" />, label: "Running" },
    success: { color: "text-emerald-400", bg: "bg-emerald-500/10", icon: <CheckCircle2 className="h-3.5 w-3.5" />, label: "Success" },
    failed: { color: "text-red-400", bg: "bg-red-500/10", icon: <XCircle className="h-3.5 w-3.5" />, label: "Failed" },
    suspended: { color: "text-amber-400", bg: "bg-amber-500/10", icon: <Pause className="h-3.5 w-3.5" />, label: "Suspended" },
};

const ENGINE_LABELS: Record<string, string> = {
    "claude-code": "Claude Code",
    "cursor-cli": "Cursor CLI",
    "gemini-cli": "Gemini CLI",
    "codex": "Codex",
};

const AGENT_LABELS: Record<string, string> = {
    general: "General",
    test_writer: "Test Writer",
    refactor: "Refactor",
    doc: "Doc Writer",
    reviewer: "Reviewer",
    release_notes: "Release Notes",
};

interface ChatMessage {
    id: string;
    type: "user" | "agent" | "system";
    content: string;
    timestamp: string;
    category?: string;
    severity?: string;
}

function getElapsed(created: string): string {
    const diff = Date.now() - new Date(created).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ${mins % 60}m`;
}

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 5) return "just now";
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ago`;
}

type StatusFilter = "all" | "running" | "pending" | "success" | "failed" | "suspended";

type StatusFilter = "all" | "running" | "pending" | "success" | "failed" | "suspended";

export default function ConsolePage() {
    const [tasks, setTasks] = useState<Task[] | null>(null);
<<<<<<< Updated upstream
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [selectedTask, setSelectedTask] = useState<Task | null>(null);
    const [sheetOpen, setSheetOpen] = useState(false);
    const { events, isConnected } = useWebSocket(WS_URL);

    const filteredTasks = useMemo(() => {
        if (!tasks) return null;
        if (statusFilter === "all") return tasks;
        return tasks.filter((t) => t.status === statusFilter);
    }, [tasks, statusFilter]);
=======
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [filter, setFilter] = useState<StatusFilter>("all");
    const [chatInput, setChatInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [chatMessages, setChatMessages] = useState<Record<string, ChatMessage[]>>({});
    const chatEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const { toast } = useToast();
    const { events } = useWebSocket(WS_URL);
>>>>>>> Stashed changes

    useEffect(() => {
        const fetchTasks = () => getTasks().then(setTasks).catch(() => {});
        fetchTasks();
        const id = setInterval(fetchTasks, 5_000);
        return () => clearInterval(id);
    }, []);

<<<<<<< Updated upstream
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
=======
    useEffect(() => {
        if (events.length === 0) return;
        const latest = events[0];
        if (!latest?.task_id) return;

        const payload = latest.payload as unknown as (TranslatedEvent & Record<string, unknown>);
        let content = "";
        let category = "";
        let severity = "info";

        if (latest.event_type === "status_update" && payload?.status) {
            content = String(payload.status);
            category = String(payload.category || "coding");
            severity = String(payload.severity || "info");
        } else if (latest.event_type === "error") {
            content = String(payload?.status || payload?.message || "Error occurred");
            severity = "error";
            category = "debugging";
        } else if (latest.event_type === "task_lifecycle") {
            const status = payload?.status;
            content = `Task ${status}`;
            category = "system";
        } else if (latest.event_type === "guardrail") {
            const passed = payload?.passed;
            content = passed ? "Guardrail check passed" : `Guardrail failed: ${payload?.error_msg || "check failed"}`;
            severity = passed ? "info" : "warning";
            category = "guardrail";
        } else {
            content = String(payload?.status || payload?.message || latest.event_type.replace(/_/g, " "));
            category = String(payload?.category || latest.event_type);
        }

        if (!content) return;

        const msg: ChatMessage = {
            id: `${latest.timestamp}-${Math.random().toString(36).slice(2, 6)}`,
            type: "agent",
            content,
            timestamp: latest.timestamp,
            category,
            severity,
        };

        setChatMessages((prev) => {
            const existing = prev[latest.task_id] || [];
            if (existing.length > 0 && existing[existing.length - 1].content === content) return prev;
            return { ...prev, [latest.task_id]: [...existing, msg].slice(-200) };
        });
    }, [events]);

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chatMessages, selectedTaskId]);

    useEffect(() => {
        if (selectedTaskId || !tasks?.length) return;
        const running = tasks.find((t) => t.status === "running");
        setSelectedTaskId(running ? running.id : tasks[0].id);
    }, [tasks, selectedTaskId]);

    const filteredTasks = useMemo(() => {
        if (!tasks) return null;
        if (filter === "all") return tasks;
        return tasks.filter((t) => t.status === filter);
    }, [tasks, filter]);

    const selectedTask = useMemo(
        () => tasks?.find((t) => t.id === selectedTaskId) ?? null,
        [tasks, selectedTaskId]
    );

    const selectedMessages = useMemo(
        () => (selectedTaskId ? chatMessages[selectedTaskId] || [] : []),
        [chatMessages, selectedTaskId]
    );

    const statusCounts = useMemo(() => {
        if (!tasks) return {};
        const counts: Record<string, number> = {};
        tasks.forEach((t) => { counts[t.status] = (counts[t.status] || 0) + 1; });
        return counts;
    }, [tasks]);

    const handleSend = useCallback(async () => {
        if (!chatInput.trim() || !selectedTaskId || isSending) return;
        const msg = chatInput.trim();
        setChatInput("");
        setIsSending(true);

        const userMsg: ChatMessage = {
            id: `user-${Date.now()}`,
            type: "user",
            content: msg,
            timestamp: new Date().toISOString(),
        };
        setChatMessages((prev) => ({
            ...prev,
            [selectedTaskId]: [...(prev[selectedTaskId] || []), userMsg],
        }));

        try {
            await injectPrompt(selectedTaskId, msg);
        } catch (err) {
            const errMsg: ChatMessage = {
                id: `err-${Date.now()}`,
                type: "system",
                content: err instanceof Error ? err.message : "Failed to send message",
                timestamp: new Date().toISOString(),
                severity: "error",
            };
            setChatMessages((prev) => ({
                ...prev,
                [selectedTaskId]: [...(prev[selectedTaskId] || []), errMsg],
            }));
        } finally {
            setIsSending(false);
            inputRef.current?.focus();
        }
    }, [chatInput, selectedTaskId, isSending]);

    const handleAction = useCallback(
        async (action: "cancel" | "suspend" | "resume", taskId: string) => {
            try {
                if (action === "cancel") await cancelTask(taskId);
                else if (action === "suspend") await suspendTask(taskId);
                else if (action === "resume") await resumeTask(taskId);

                toast({ title: `Task ${action}${action === "resume" ? "d" : action === "cancel" ? "led" : "ed"}` });

                const sysMsg: ChatMessage = {
                    id: `sys-${Date.now()}`,
                    type: "system",
                    content: `Task ${action}${action === "resume" ? "d" : action === "cancel" ? "led" : "ed"} by user`,
                    timestamp: new Date().toISOString(),
                };
                setChatMessages((prev) => ({
                    ...prev,
                    [taskId]: [...(prev[taskId] || []), sysMsg],
                }));

                const refreshed = await getTasks();
                setTasks(refreshed);
            } catch (err) {
                toast({
                    title: "Action failed",
                    description: err instanceof Error ? err.message : "Unknown error",
                    variant: "destructive",
                });
            }
        },
        [toast]
    );

    const activeCount = tasks?.filter((t) => t.status === "running" || t.status === "pending").length ?? 0;

    return (
        <div className="h-[calc(100vh-48px)] flex flex-col gap-4">
            <div className="flex items-center justify-between shrink-0">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                        <Terminal className="h-7 w-7 text-indigo-400" />
                        Agent Console
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Chat with and manage all active agents
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {activeCount > 0 && (
                        <Badge className="bg-blue-500/15 text-blue-400 border-blue-500/30 animate-pulse">
                            <Zap className="h-3 w-3 mr-1" />
                            {activeCount} active
                        </Badge>
                    )}
                    <Badge variant="secondary" className="text-xs">
                        {tasks?.length ?? 0} total
                    </Badge>
                </div>
            </div>

            <div className="flex gap-2 shrink-0">
                {(["all", "running", "pending", "success", "failed", "suspended"] as StatusFilter[]).map((s) => {
                    const isActive = filter === s;
                    const count = s === "all" ? tasks?.length ?? 0 : statusCounts[s] ?? 0;
                    return (
                        <button
                            key={s}
                            onClick={() => setFilter(s)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                                isActive
                                    ? "bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/30"
                                    : "bg-white/[0.03] text-muted-foreground hover:bg-white/[0.06] hover:text-white"
                            }`}
                        >
                            <span className="capitalize">{s}</span>
                            {count > 0 && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${isActive ? "bg-indigo-500/30" : "bg-white/10"}`}>
                                    {count}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            <div className="flex-1 grid grid-cols-12 gap-4 min-h-0">
                {/* Left: Agent list — which agent is performing which task */}
                <div className="col-span-4 flex flex-col min-h-0 rounded-xl border border-border/30 bg-white/[0.02] overflow-hidden">
                    <div className="px-4 py-3 border-b border-border/20 shrink-0">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                            <Bot className="h-3.5 w-3.5" />
                            Agents & Tasks
                        </p>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {!filteredTasks ? (
                            <div className="p-3 space-y-2">
                                {Array.from({ length: 5 }).map((_, i) => (
                                    <Skeleton key={i} className="h-24 w-full rounded-lg" />
                                ))}
                            </div>
                        ) : filteredTasks.length === 0 ? (
                            <div className="flex items-center justify-center h-full">
                                <p className="text-sm text-muted-foreground/60 px-4 text-center">
                                    {filter === "all"
                                        ? "No agents yet. Deploy from the Dashboard."
                                        : `No ${filter} agents`}
                                </p>
                            </div>
                        ) : (
                            <div className="p-2 space-y-1">
                                {filteredTasks.map((task) => {
                                    const cfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;
                                    const isSelected = task.id === selectedTaskId;
                                    const budgetRatio = task.budget_limit > 0 ? task.budget_used / task.budget_limit : 0;

                                    return (
                                        <button
                                            key={task.id}
                                            onClick={() => setSelectedTaskId(task.id)}
                                            className={`w-full text-left rounded-lg p-3 transition-all ${
                                                isSelected
                                                    ? "bg-indigo-500/10 ring-1 ring-indigo-500/30 shadow-lg shadow-indigo-500/5"
                                                    : "hover:bg-white/[0.04]"
                                            }`}
                                        >
                                            <div className="flex items-start gap-2.5">
                                                <span className={`mt-0.5 ${cfg.color}`}>{cfg.icon}</span>
                                                <div className="flex-1 min-w-0">
                                                    {/* Agent identity: engine + agent_type */}
                                                    <div className="flex items-center gap-1.5 flex-wrap mb-1">
                                                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-indigo-500/30 text-indigo-300">
                                                            {ENGINE_LABELS[task.engine] || task.engine}
                                                        </Badge>
                                                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-white/5">
                                                            {AGENT_LABELS[task.agent_type] || task.agent_type}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-sm font-medium line-clamp-2 leading-snug text-white">
                                                        {task.task}
                                                    </p>
                                                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                                                        <Badge variant="secondary" className={`text-[10px] px-1.5 py-0 ${cfg.bg} ${cfg.color}`}>
                                                            {cfg.label}
                                                        </Badge>
                                                        <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                                                            <Clock className="h-2.5 w-2.5" />
                                                            {getElapsed(task.created_at)}
                                                        </span>
                                                    </div>
                                                    <div className="mt-2">
                                                        <Progress
                                                            value={Math.min(budgetRatio * 100, 100)}
                                                            className="h-1"
                                                            indicatorClassName={
                                                                budgetRatio < 0.6 ? "bg-emerald-500" : budgetRatio < 0.85 ? "bg-amber-500" : "bg-red-500"
                                                            }
                                                        />
                                                        <div className="flex justify-between mt-0.5 text-[9px] text-muted-foreground/50">
                                                            <span>${task.budget_used.toFixed(2)}</span>
                                                            <span>${task.budget_limit.toFixed(2)}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                {isSelected && <ChevronRight className="h-4 w-4 text-indigo-400 mt-1 shrink-0" />}
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Chat & interaction panel */}
                <div className="col-span-8 flex flex-col min-h-0 rounded-xl border border-border/30 bg-white/[0.02] overflow-hidden">
                    {!selectedTask ? (
                        <div className="flex-1 flex items-center justify-center">
                            <div className="text-center space-y-3">
                                <MessageSquare className="h-12 w-12 text-muted-foreground/20 mx-auto" />
                                <p className="text-sm text-muted-foreground/60">Select an agent to start chatting</p>
                            </div>
                        </div>
                    ) : (
                        <>
                            <div className="px-4 py-3 border-b border-border/20 shrink-0">
                                <div className="flex items-center justify-between">
                                    <div className="min-w-0">
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <div className={`p-1.5 rounded-lg ${STATUS_CONFIG[selectedTask.status]?.bg ?? "bg-slate-500/10"}`}>
                                                <Cpu className={`h-4 w-4 ${STATUS_CONFIG[selectedTask.status]?.color ?? "text-slate-400"}`} />
                                            </div>
                                            <Badge variant="outline" className="text-[10px] border-indigo-500/30 text-indigo-300">
                                                {ENGINE_LABELS[selectedTask.engine] || selectedTask.engine}
                                            </Badge>
                                            <Badge variant="secondary" className="text-[10px] bg-white/5">
                                                {AGENT_LABELS[selectedTask.agent_type] || selectedTask.agent_type}
                                            </Badge>
                                        </div>
                                        <p className="text-sm font-medium truncate max-w-[500px]">{selectedTask.task}</p>
                                        <p className="text-[10px] text-muted-foreground mt-0.5">
                                            Task ID: {selectedTask.id.slice(0, 8)} · {getElapsed(selectedTask.created_at)}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        {selectedTask.status === "running" && (
                                            <>
                                                <Button size="sm" variant="ghost" className="h-8 px-2.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
                                                    onClick={() => handleAction("suspend", selectedTask.id)} title="Suspend">
                                                    <PauseCircle className="h-3.5 w-3.5 mr-1" /><span className="text-xs">Suspend</span>
                                                </Button>
                                                <Button size="sm" variant="ghost" className="h-8 px-2.5 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                                    onClick={() => handleAction("cancel", selectedTask.id)} title="Stop">
                                                    <Square className="h-3.5 w-3.5 mr-1" /><span className="text-xs">Stop</span>
                                                </Button>
                                            </>
                                        )}
                                        {selectedTask.status === "suspended" && (
                                            <>
                                                <Button size="sm" variant="ghost" className="h-8 px-2.5 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                                                    onClick={() => handleAction("resume", selectedTask.id)} title="Resume">
                                                    <Play className="h-3.5 w-3.5 mr-1" /><span className="text-xs">Resume</span>
                                                </Button>
                                                <Button size="sm" variant="ghost" className="h-8 px-2.5 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                                    onClick={() => handleAction("cancel", selectedTask.id)} title="Stop">
                                                    <Square className="h-3.5 w-3.5 mr-1" /><span className="text-xs">Stop</span>
                                                </Button>
                                            </>
                                        )}
                                        <Badge variant="secondary" className={`text-[10px] ${STATUS_CONFIG[selectedTask.status]?.bg ?? ""} ${STATUS_CONFIG[selectedTask.status]?.color ?? ""}`}>
                                            {STATUS_CONFIG[selectedTask.status]?.icon}
                                            <span className="ml-1">{STATUS_CONFIG[selectedTask.status]?.label ?? selectedTask.status}</span>
                                        </Badge>
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
                                {selectedMessages.length === 0 ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center space-y-2">
                                            <Terminal className="h-8 w-8 text-muted-foreground/20 mx-auto" />
                                            <p className="text-xs text-muted-foreground/50">
                                                {selectedTask.status === "running"
                                                    ? "Waiting for agent output..."
                                                    : selectedTask.status === "pending"
                                                    ? "Agent hasn't started yet"
                                                    : "No messages recorded"}
                                            </p>
                                        </div>
                                    </div>
                                ) : (
                                    selectedMessages.map((msg) => (
                                        <div key={msg.id} className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"}`}>
                                            <div
                                                className={`max-w-[85%] rounded-lg px-3 py-2 ${
                                                    msg.type === "user"
                                                        ? "bg-indigo-600/20 border border-indigo-500/20 text-indigo-100"
                                                        : msg.type === "system"
                                                        ? "bg-white/[0.03] border border-border/20 text-muted-foreground"
                                                        : msg.severity === "error"
                                                        ? "bg-red-500/[0.07] border border-red-500/15"
                                                        : msg.severity === "warning"
                                                        ? "bg-amber-500/[0.07] border border-amber-500/15"
                                                        : "bg-white/[0.03] border border-border/20"
                                                }`}
                                            >
                                                {msg.type !== "user" && msg.category && (
                                                    <span className={`text-[9px] uppercase tracking-wider font-medium ${
                                                        msg.severity === "error" ? "text-red-400/70" : msg.severity === "warning" ? "text-amber-400/70" : "text-muted-foreground/50"
                                                    }`}>{msg.category}</span>
                                                )}
                                                <p className="text-sm leading-relaxed">{msg.content}</p>
                                                <p className="text-[9px] text-muted-foreground/40 mt-1">{relativeTime(msg.timestamp)}</p>
                                            </div>
                                        </div>
                                    ))
                                )}
                                <div ref={chatEndRef} />
                            </div>

                            <div className="px-4 py-3 border-t border-border/20 shrink-0">
                                {selectedTask.status === "running" || selectedTask.status === "suspended" ? (
                                    <div className="flex items-center gap-2">
                                        <input
                                            ref={inputRef}
                                            value={chatInput}
                                            onChange={(e) => setChatInput(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
                                            }}
                                            placeholder={selectedTask.status === "suspended" ? "Resume agent to send messages..." : "Send a message to this agent..."}
                                            disabled={selectedTask.status === "suspended" || isSending}
                                            className="flex-1 bg-white/[0.04] border border-border/30 rounded-lg px-4 py-2.5 text-sm placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-indigo-500/40 focus:border-indigo-500/40 disabled:opacity-50 transition-all"
                                        />
                                        <Button
                                            onClick={handleSend}
                                            disabled={!chatInput.trim() || selectedTask.status === "suspended" || isSending}
                                            className="h-10 px-4 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-lg shadow-indigo-500/20 disabled:opacity-30 disabled:shadow-none"
                                        >
                                            <Send className="h-4 w-4" />
                                        </Button>
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center py-2 text-xs text-muted-foreground/50">
                                        {selectedTask.status === "success" && (
                                            <span className="flex items-center gap-1.5"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500/60" />Agent completed successfully</span>
                                        )}
                                        {selectedTask.status === "failed" && (
                                            <span className="flex items-center gap-1.5"><XCircle className="h-3.5 w-3.5 text-red-500/60" />Agent failed — check logs above</span>
                                        )}
                                        {selectedTask.status === "pending" && (
                                            <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5 text-slate-500/60" />Agent pending — waiting to start</span>
                                        )}
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
>>>>>>> Stashed changes
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
