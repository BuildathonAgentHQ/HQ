"use client";

import { useState } from "react";
import { createTask } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";
import type { TaskCreate } from "@/lib/types";
import { DEFAULT_BUDGET_LIMIT } from "@/lib/constants";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Rocket } from "lucide-react";

const ENGINES = [
    { value: "claude-code", label: "Claude Code" },
    { value: "cursor-cli", label: "Cursor CLI" },
] as const;

const AGENT_TYPES = [
    { value: "general", label: "General" },
    { value: "test_writer", label: "TestWriter" },
    { value: "refactor", label: "Refactor" },
    { value: "doc", label: "Doc Writer" },
    { value: "reviewer", label: "Code Reviewer" },
    { value: "release_notes", label: "Release Notes" },
] as const;

export function CommandInput() {
    const [task, setTask] = useState("");
    const [engine, setEngine] = useState<TaskCreate["engine"]>("claude-code");
    const [agentType, setAgentType] =
        useState<TaskCreate["agent_type"]>("general");
    const [budget, setBudget] = useState(DEFAULT_BUDGET_LIMIT);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const { toast } = useToast();

    const canSubmit = task.trim().length > 0 && !isSubmitting;

    const handleSubmit = async () => {
        if (!canSubmit) return;
        setIsSubmitting(true);
        try {
            const payload: TaskCreate = {
                task: task.trim(),
                engine,
                agent_type: agentType,
                budget_limit: budget,
                context_sources: [],
            };
            const created = await createTask(payload);
            toast({
                title: "Agent deployed",
                description: `Task ID: ${created.id}`,
            });
            setTask("");
        } catch (err) {
            toast({
                title: "Deployment failed",
                description:
                    err instanceof Error ? err.message : "Could not deploy agent.",
                variant: "destructive",
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Card className="border-border/40 bg-gradient-to-br from-[#0f172a]/90 to-[#1e1b4b]/60 backdrop-blur-xl shadow-2xl shadow-indigo-500/5">
            <CardContent className="pt-6 space-y-4">
                {/* ── Text area ───────────────────────────────────────────── */}
                <Textarea
                    rows={4}
                    placeholder="Describe what you want the agent to build..."
                    value={task}
                    onChange={(e) => setTask(e.target.value)}
                    className="resize-none bg-white/[0.04] border-white/10 text-sm placeholder:text-muted-foreground/60 focus:border-indigo-500/50 transition-colors"
                />

                {/* ── Controls row ────────────────────────────────────────── */}
                <div className="flex flex-wrap items-center gap-3">
                    {/* Engine selector */}
                    <Select
                        value={engine}
                        onValueChange={(v) => setEngine(v as TaskCreate["engine"])}
                    >
                        <SelectTrigger className="w-[150px] bg-white/[0.04] border-white/10 text-sm">
                            <SelectValue placeholder="Engine" />
                        </SelectTrigger>
                        <SelectContent>
                            {ENGINES.map((e) => (
                                <SelectItem key={e.value} value={e.value}>
                                    {e.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Agent type selector */}
                    <Select
                        value={agentType}
                        onValueChange={(v) => setAgentType(v as TaskCreate["agent_type"])}
                    >
                        <SelectTrigger className="w-[160px] bg-white/[0.04] border-white/10 text-sm">
                            <SelectValue placeholder="Agent Type" />
                        </SelectTrigger>
                        <SelectContent>
                            {AGENT_TYPES.map((a) => (
                                <SelectItem key={a.value} value={a.value}>
                                    {a.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Budget input */}
                    <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">Budget $</span>
                        <Input
                            type="number"
                            step="0.50"
                            min="0.50"
                            value={budget}
                            onChange={(e) => setBudget(parseFloat(e.target.value) || 0)}
                            className="w-[80px] bg-white/[0.04] border-white/10 text-sm tabular-nums"
                        />
                    </div>

                    {/* Deploy button — pushed to the right */}
                    <Button
                        onClick={handleSubmit}
                        disabled={!canSubmit}
                        className="ml-auto gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40 disabled:opacity-40 disabled:shadow-none px-6"
                    >
                        <Rocket className="h-4 w-4" />
                        {isSubmitting ? "Deploying…" : "Deploy Agent"}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
