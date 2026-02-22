"use client";

import { useEffect, useState } from "react";
import {
    HeartPulse,
    Activity,
    Flame,
    Wrench,
    AlertOctagon,
    CheckCircle2,
    XCircle,
    Play
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { API_BASE_URL } from "@/lib/constants";

const ENGINES = [
    { value: "claude-code", label: "Claude Code" },
    { value: "cursor-cli", label: "Cursor CLI" },
    { value: "gemini-cli", label: "Gemini CLI" },
    { value: "codex", label: "Codex" },
] as const;

export default function RepoHealthPage() {
    const [healthData, setHealthData] = useState<any>(null);
    const [actionsData, setActionsData] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchAll() {
            try {
                const [healthRes, actionsRes] = await Promise.all([
                    fetch(`${API_BASE_URL}/control-plane/health`),
                    fetch(`${API_BASE_URL}/control-plane/actions`)
                ]);

                if (healthRes.ok) setHealthData(await healthRes.json());
                if (actionsRes.ok) setActionsData(await actionsRes.json());
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        }
        fetchAll();
    }, []);

    const [dispatching, setDispatching] = useState<string | null>(null);
    const [dispatchResult, setDispatchResult] = useState<Record<string, any>>({});
    const [selectedEngines, setSelectedEngines] = useState<Record<string, string>>({});

    const getEngine = (key: string) => selectedEngines[key] ?? "claude-code";

    const executeAction = async (action: any) => {
        const key = `${action.action_type}-${action.target}`;
        setDispatching(key);
        setDispatchResult((prev) => ({ ...prev, [key]: undefined }));

        try {
            const res = await fetch(`${API_BASE_URL}/swarm/dispatch`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action_type: action.action_type,
                    description: action.description,
                    target: action.target,
                    engine: "claude-code", // Always use Claude Code regardless of dropdown
                }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || "Dispatch failed");
            }

            const data = await res.json();
            setDispatchResult((prev) => ({ ...prev, [key]: data }));
        } catch (e: any) {
            setDispatchResult((prev) => ({
                ...prev,
                [key]: { status: "error", message: e.message },
            }));
        } finally {
            setDispatching(null);
        }
    };

    const renderCIStatus = (status: string) => {
        if (status === "passing") {
            return (
                <Badge className="bg-green-500/10 text-green-500 border-green-500/20 text-lg py-2 px-4 uppercase tracking-widest">
                    <CheckCircle2 className="h-5 w-5 mr-2" /> PASSING
                </Badge>
            );
        }
        if (status === "failing") {
            return (
                <Badge className="bg-red-500/10 text-red-500 border-red-500/20 text-lg py-2 px-4 uppercase tracking-widest">
                    <XCircle className="h-5 w-5 mr-2" /> FAILING
                </Badge>
            );
        }
        return (
            <Badge variant="outline" className="text-lg py-2 px-4 uppercase tracking-widest text-zinc-500 border-zinc-700">
                <Activity className="h-5 w-5 mr-2" /> UNKNOWN
            </Badge>
        );
    };

    if (loading) {
        return (
            <div className="space-y-6 animate-pulse">
                <div className="h-40 w-full bg-zinc-900/50 rounded-xl" />
                <div className="grid grid-cols-2 gap-6">
                    <div className="h-64 bg-zinc-900/50 rounded-xl" />
                    <div className="h-64 bg-zinc-900/50 rounded-xl" />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                        <HeartPulse className="h-8 w-8 text-rose-500" />
                        Repository Health
                    </h1>
                    <p className="text-muted-foreground mt-2 inline-flex items-center gap-2">
                        Continuous codebase telemetry. Current CI state: {renderCIStatus(healthData?.ci_status)}
                    </p>
                </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                {/* Next Best Actions (Recommendations) */}
                <Card className="col-span-2 border-zinc-800 bg-zinc-900/50">
                    <CardHeader className="border-b border-zinc-800 bg-black/20">
                        <CardTitle className="text-xl flex items-center gap-2 text-indigo-400">
                            <Play className="h-5 w-5" />
                            Automated Operations (Next Best Actions)
                        </CardTitle>
                        <CardDescription>
                            AI-generated recommendations sorted by priority and impact. Click execute to dispatch a specialized agent.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="divide-y divide-zinc-800/50">
                            {actionsData.length > 0 ? actionsData.map((action, i) => (
                                <div key={i} className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-6 hover:bg-zinc-800/30 transition-colors">
                                    <div className="space-y-2 mb-4 sm:mb-0">
                                        <div className="flex items-center gap-3">
                                            <Badge variant="outline" className={`uppercase font-bold tracking-wide
                        ${action.priority === "high" ? "border-red-500/40 text-red-400 bg-red-500/10" : ""}
                        ${action.priority === "medium" ? "border-yellow-500/40 text-yellow-400 bg-yellow-500/10" : ""}
                        ${action.priority === "low" ? "border-blue-500/40 text-blue-400 bg-blue-500/10" : ""}
                      `}>
                                                {action.priority}
                                            </Badge>
                                            <span className="font-mono text-xs text-zinc-500 bg-black/40 px-2 py-1 rounded">
                                                {action.action_type}
                                            </span>
                                        </div>
                                        <p className="text-zinc-200">{action.description}</p>
                                        <p className="text-sm text-zinc-500 font-mono">Target: {action.target}</p>
                                    </div>
                                    <div className="flex flex-col items-end gap-2">
                                        <span className="text-xs text-zinc-500 whitespace-nowrap">Est. Effort: {action.estimated_effort}</span>
                                        {(() => {
                                            const key = `${action.action_type}-${action.target}`;
                                            const result = dispatchResult[key];
                                            const isRunning = dispatching === key;

                                            if (result?.status === "dispatched") {
                                                return (
                                                    <span className="text-xs text-green-400 text-right max-w-[200px]">
                                                        {result.message}
                                                    </span>
                                                );
                                            }
                                            if (result?.status === "error") {
                                                return (
                                                    <span className="text-xs text-red-400 text-right max-w-[200px]">
                                                        {result.message}
                                                    </span>
                                                );
                                            }

                                            return (
                                                <div className="flex items-center gap-2">
                                                    <Select
                                                        value={getEngine(key)}
                                                        onValueChange={(v) =>
                                                            setSelectedEngines((prev) => ({ ...prev, [key]: v }))
                                                        }
                                                        disabled={isRunning}
                                                    >
                                                        <SelectTrigger className="w-[140px] h-8 bg-white/[0.04] border-white/10 text-xs">
                                                            <SelectValue />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {ENGINES.map((e) => (
                                                                <SelectItem key={e.value} value={e.value}>
                                                                    {e.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                    <Button
                                                        size="sm"
                                                        className="bg-indigo-600 hover:bg-indigo-700 text-white w-full sm:w-auto"
                                                        disabled={isRunning}
                                                        onClick={() => executeAction(action)}
                                                    >
                                                        {isRunning ? "Dispatching…" : "Dispatch Agent"}
                                                    </Button>
                                                </div>
                                            );
                                        })()}
                                    </div>
                                </div>
                            )) : (
                                <div className="p-8 text-center text-zinc-500 italic">No pending actions. The repository is perfectly maintained.</div>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Flaky Tests */}
                <Card className="border-zinc-800 bg-zinc-900/50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-yellow-500">
                            <AlertOctagon className="h-5 w-5" />
                            Flaky Tests
                        </CardTitle>
                        <CardDescription>Tests showing non-deterministic behavior in recent CI runs</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {healthData?.flaky_tests && healthData.flaky_tests.length > 0 ? (
                            <ul className="space-y-4">
                                {healthData.flaky_tests.map((test: string, i: number) => (
                                    <li key={i} className="flex justify-between items-center text-sm font-mono text-zinc-300 bg-black/20 p-3 rounded-md border border-zinc-800/50">
                                        <span className="truncate mr-4">{test}</span>
                                        <Button variant="ghost" size="sm" className="h-8 text-yellow-500 hover:text-yellow-400 hover:bg-yellow-500/10 shrink-0">
                                            Investigate
                                        </Button>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <div className="text-zinc-500 text-sm text-center py-4">No flaky tests detected recently.</div>
                        )}
                    </CardContent>
                </Card>

                {/* Tech Debt */}
                <Card className="border-zinc-800 bg-zinc-900/50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-red-400">
                            <Wrench className="h-5 w-5" />
                            Technical Debt
                        </CardTitle>
                        <CardDescription>High severity inline comments (FIXME, HACK, etc)</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {healthData?.tech_debt_items && healthData.tech_debt_items.length > 0 ? (
                            <ul className="space-y-4">
                                {healthData.tech_debt_items.map((item: any, i: number) => (
                                    <li key={i} className="text-sm p-3 rounded-md border border-zinc-800/50 bg-black/20 flex flex-col gap-2">
                                        <div className="flex justify-between items-start">
                                            <Badge variant="outline" className={`
                        ${item.severity === "high" ? "border-red-500/30 text-red-500 bg-red-500/10" : ""}
                        ${item.severity === "medium" ? "border-yellow-500/30 text-yellow-500 bg-yellow-500/10" : ""}
                        ${item.severity === "low" ? "border-blue-500/30 text-blue-500 bg-blue-500/10" : ""}
                      `}>
                                                {item.severity}
                                            </Badge>
                                            <span className="text-xs text-zinc-500">{item.age_days} days old</span>
                                        </div>
                                        <p className="text-zinc-300 font-mono text-xs mt-1">{item.description}</p>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <div className="text-zinc-500 text-sm text-center py-4">No critical technical debt comments found.</div>
                        )}
                    </CardContent>
                </Card>

                {/* Hot Files */}
                <Card className="col-span-2 border-zinc-800 bg-zinc-900/50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-orange-500">
                            <Flame className="h-5 w-5" />
                            Hot Files (30-Day Churn)
                        </CardTitle>
                        <CardDescription>Files seeing the highest velocity of change and potential stability risk</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs text-zinc-400 uppercase bg-black/20 border-b border-zinc-800">
                                    <tr>
                                        <th className="px-4 py-3 font-medium">File Path</th>
                                        <th className="px-4 py-3 font-medium text-center">Commits (30d)</th>
                                        <th className="px-4 py-3 font-medium text-right">Last Changed</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-800/50">
                                    {healthData?.hot_files && healthData.hot_files.length > 0 ? healthData.hot_files.map((file: any, i: number) => (
                                        <tr key={i} className="hover:bg-zinc-800/20 transition-colors">
                                            <td className="px-4 py-3 font-mono text-zinc-300">{file.path}</td>
                                            <td className="px-4 py-3 text-center">
                                                <div className="flex items-center justify-center gap-2">
                                                    <span className="text-orange-400 font-bold">{file.change_count_30d}</span>
                                                    {/* Mini visual bar */}
                                                    <div className="w-24 h-2 bg-zinc-800 rounded-full overflow-hidden">
                                                        <div className="h-full bg-orange-500" style={{ width: `${Math.min(100, (file.change_count_30d / 20) * 100)}%` }}></div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-4 py-3 text-right text-zinc-500">
                                                {new Date(file.last_changed).toLocaleDateString()}
                                            </td>
                                        </tr>
                                    )) : (
                                        <tr>
                                            <td colSpan={3} className="px-4 py-6 text-center text-zinc-500 italic">No significant file churn recently.</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>

            </div>
        </div>
    );
}
