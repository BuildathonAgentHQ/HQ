"use client";

import { useEffect, useState, useCallback } from "react";
import { getLeaderboard } from "@/hooks/use-api";
import type { AgentLeaderboardEntry } from "@/lib/types";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Trophy, ArrowUpDown } from "lucide-react";

const REFRESH_MS = 60_000;

type SortKey = keyof AgentLeaderboardEntry;

export function Leaderboard() {
    const [entries, setEntries] = useState<AgentLeaderboardEntry[] | null>(null);
    const [sortKey, setSortKey] = useState<SortKey>("success_rate");
    const [sortAsc, setSortAsc] = useState(false);

    const fetchData = useCallback(async () => {
        try {
            const data = await getLeaderboard();
            setEntries(data);
        } catch {
            // keep previous
        }
    }, []);

    useEffect(() => {
        fetchData();
        const id = setInterval(fetchData, REFRESH_MS);
        return () => clearInterval(id);
    }, [fetchData]);

    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortAsc(!sortAsc);
        } else {
            setSortKey(key);
            setSortAsc(false);
        }
    };

    const sorted = entries
        ? [...entries].sort((a, b) => {
            const av = a[sortKey] as number;
            const bv = b[sortKey] as number;
            return sortAsc ? av - bv : bv - av;
        })
        : null;

    if (!sorted) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Trophy className="h-4 w-4 text-amber-400" />
                        Agent Leaderboard
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-12 w-full" />
                    ))}
                </CardContent>
            </Card>
        );
    }

    const cols: { key: SortKey; label: string; align: string }[] = [
        { key: "engine", label: "Engine", align: "text-left" },
        { key: "tasks_completed", label: "Tasks", align: "text-right" },
        { key: "success_rate", label: "Success Rate", align: "text-right" },
        { key: "avg_duration_seconds", label: "Avg Duration", align: "text-right" },
        { key: "avg_cost_dollars", label: "Avg Cost", align: "text-right" },
        { key: "total_tokens", label: "Total Tokens", align: "text-right" },
    ];

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Trophy className="h-4 w-4 text-amber-400" />
                    Agent Leaderboard
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="overflow-x-auto">
                    {/* Header */}
                    <div className="grid grid-cols-7 text-[11px] text-muted-foreground font-medium px-3 pb-2">
                        <span>Rank</span>
                        {cols.map((c) => (
                            <span
                                key={c.key}
                                className={`${c.align} cursor-pointer hover:text-white transition-colors flex items-center gap-1 ${c.align === "text-right" ? "justify-end" : ""
                                    }`}
                                onClick={() => handleSort(c.key)}
                            >
                                {c.label}
                                {sortKey === c.key && (
                                    <ArrowUpDown className="h-3 w-3 text-indigo-400" />
                                )}
                            </span>
                        ))}
                    </div>
                    <Separator className="opacity-20" />

                    {/* Rows */}
                    {sorted.map((entry, i) => {
                        const rate = entry.success_rate * 100;
                        const rateColor =
                            rate >= 90
                                ? "bg-emerald-500/10 text-emerald-400"
                                : rate >= 70
                                    ? "bg-amber-500/10 text-amber-400"
                                    : "bg-red-500/10 text-red-400";

                        return (
                            <div
                                key={entry.engine}
                                className="grid grid-cols-7 items-center rounded-lg px-3 py-2.5 text-sm hover:bg-white/[0.03] transition-colors"
                            >
                                <span className="text-xs text-muted-foreground font-medium">
                                    #{i + 1}
                                </span>
                                <span className="font-medium">{entry.engine}</span>
                                <span className="text-right tabular-nums">
                                    {entry.tasks_completed}
                                </span>
                                <span className="text-right">
                                    <Badge variant="secondary" className={`text-[10px] ${rateColor}`}>
                                        {rate.toFixed(0)}%
                                    </Badge>
                                </span>
                                <span className="text-right tabular-nums text-muted-foreground">
                                    {Math.round(entry.avg_duration_seconds)}s
                                </span>
                                <span className="text-right tabular-nums text-muted-foreground">
                                    ${entry.avg_cost_dollars.toFixed(2)}
                                </span>
                                <span className="text-right tabular-nums text-muted-foreground">
                                    {entry.total_tokens.toLocaleString()}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
}
