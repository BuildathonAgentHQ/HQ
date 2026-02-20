"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE_URL } from "@/lib/constants";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
    DollarSign,
    TrendingUp,
    Calculator,
    Flame,
    Clock,
    FileText,
} from "lucide-react";

import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

interface FinOpsData {
    today_spend: number;
    monthly_spend: number;
    avg_cost_per_task: number;
    projected_burn: number;
    daily_spend: { date: string; amount: number }[];
    top_tasks: {
        task_id: string;
        description: string;
        cost: number;
        duration_seconds: number;
    }[];
}

function StatCard({
    icon: Icon,
    label,
    value,
    color,
}: {
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    value: string;
    color: string;
}) {
    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardContent className="py-4 flex items-center gap-4">
                <div
                    className={`flex h-10 w-10 items-center justify-center rounded-lg ${color} bg-opacity-10`}
                >
                    <Icon className={`h-5 w-5 ${color}`} />
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="text-xl font-bold tabular-nums">{value}</p>
                </div>
            </CardContent>
        </Card>
    );
}

export default function FinOpsPage() {
    const [data, setData] = useState<FinOpsData | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/metrics/finops`);
            if (res.ok) {
                setData(await res.json());
            }
        } catch {
            // use fallback
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Fallback mock data for display when API unavailable
    const display = data ?? {
        today_spend: 0,
        monthly_spend: 0,
        avg_cost_per_task: 0,
        projected_burn: 0,
        daily_spend: [],
        top_tasks: [],
    };

    return (
        <div className="space-y-6">
            {/* ── Header ──────────────────────────────────────────── */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <DollarSign className="h-7 w-7 text-amber-400" />
                    FinOps Dashboard
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Comprehensive breakdown of LLM token spend across agents and tasks
                </p>
            </div>

            {/* ── Stat cards ─────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {loading ? (
                    Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full" />
                    ))
                ) : (
                    <>
                        <StatCard
                            icon={DollarSign}
                            label="Today's Spend"
                            value={`$${display.today_spend.toFixed(2)}`}
                            color="text-emerald-400"
                        />
                        <StatCard
                            icon={TrendingUp}
                            label="30-Day Spend"
                            value={`$${display.monthly_spend.toFixed(2)}`}
                            color="text-blue-400"
                        />
                        <StatCard
                            icon={Calculator}
                            label="Avg Cost / Task"
                            value={`$${display.avg_cost_per_task.toFixed(2)}`}
                            color="text-violet-400"
                        />
                        <StatCard
                            icon={Flame}
                            label="Projected Monthly Burn"
                            value={`$${display.projected_burn.toFixed(2)}`}
                            color="text-amber-400"
                        />
                    </>
                )}
            </div>

            {/* ── Spend chart ────────────────────────────────────── */}
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <TrendingUp className="h-4 w-4 text-blue-400" />
                        Daily Spend — Last 30 Days
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <Skeleton className="h-[300px] w-full" />
                    ) : display.daily_spend.length === 0 ? (
                        <div className="flex items-center justify-center h-[300px]">
                            <p className="text-sm text-muted-foreground/60">
                                No spend data available yet
                            </p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={display.daily_spend}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                <XAxis
                                    dataKey="date"
                                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                                />
                                <YAxis
                                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                                    tickFormatter={(v) => `$${v}`}
                                />
                                <Tooltip
                                    contentStyle={{
                                        background: "#1e293b",
                                        border: "1px solid #334155",
                                        borderRadius: 8,
                                        color: "#e2e8f0",
                                        fontSize: 12,
                                    }}
                                    formatter={(val: number) => [`$${val.toFixed(2)}`, "Spend"]}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="amount"
                                    stroke="#6366f1"
                                    strokeWidth={2}
                                    dot={{ fill: "#6366f1", r: 3 }}
                                    activeDot={{ r: 5, fill: "#818cf8" }}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    )}
                </CardContent>
            </Card>

            {/* ── Top expensive tasks ────────────────────────────── */}
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="h-4 w-4 text-amber-400" />
                        Top 5 Most Expensive Tasks
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="space-y-2">
                            {Array.from({ length: 5 }).map((_, i) => (
                                <Skeleton key={i} className="h-12 w-full" />
                            ))}
                        </div>
                    ) : display.top_tasks.length === 0 ? (
                        <p className="text-sm text-muted-foreground/60 text-center py-6">
                            No tasks completed yet
                        </p>
                    ) : (
                        <div className="space-y-1">
                            {/* Header */}
                            <div className="grid grid-cols-4 text-[11px] text-muted-foreground font-medium px-3 pb-2">
                                <span>Task ID</span>
                                <span>Description</span>
                                <span className="text-right">Cost</span>
                                <span className="text-right">Duration</span>
                            </div>
                            <Separator className="opacity-20" />
                            {display.top_tasks.map((t) => (
                                <div
                                    key={t.task_id}
                                    className="grid grid-cols-4 items-center px-3 py-2.5 text-sm hover:bg-white/[0.03] transition-colors rounded-lg"
                                >
                                    <code className="text-xs text-muted-foreground font-mono">
                                        {t.task_id.slice(0, 8)}
                                    </code>
                                    <span className="truncate text-xs">{t.description}</span>
                                    <span className="text-right tabular-nums font-medium">
                                        ${t.cost.toFixed(2)}
                                    </span>
                                    <span className="text-right tabular-nums text-muted-foreground flex items-center justify-end gap-1">
                                        <Clock className="h-3 w-3" />
                                        {Math.round(t.duration_seconds)}s
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
