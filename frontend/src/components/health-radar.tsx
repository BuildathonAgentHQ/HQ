"use client";

import { useEffect, useState, useCallback } from "react";
import { getRadarMetrics } from "@/hooks/use-api";
import type { TelemetryMetrics } from "@/lib/types";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { Activity, Info } from "lucide-react";

import {
    RadarChart,
    PolarGrid,
    PolarAngleAxis,
    PolarRadiusAxis,
    Radar,
    ResponsiveContainer,
    Tooltip as RechartsTooltip,
} from "recharts";

const REFRESH_MS = 30_000;

const INFO_TEXT =
    "Security: bandit/security scan pass rates • Stability: task completion success rates • Quality: lint check pass rates • Speed: inverse of average completion time";

export function HealthRadar() {
    const [metrics, setMetrics] = useState<TelemetryMetrics | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchMetrics = useCallback(async () => {
        try {
            const data = await getRadarMetrics();
            setMetrics(data);
        } catch {
            // keep previous data on error
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchMetrics();
        const id = setInterval(fetchMetrics, REFRESH_MS);
        return () => clearInterval(id);
    }, [fetchMetrics]);

    /* ── Loading skeleton ────────────────────────────────────────── */
    if (loading && !metrics) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Activity className="h-4 w-4 text-cyan-400" />
                        Health Radar
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <Skeleton className="h-[280px] w-full rounded-lg" />
                </CardContent>
            </Card>
        );
    }

    /* ── No data placeholder ─────────────────────────────────────── */
    if (!metrics) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Activity className="h-4 w-4 text-cyan-400" />
                        Health Radar
                    </CardTitle>
                </CardHeader>
                <CardContent className="flex items-center justify-center h-[280px]">
                    <p className="text-sm text-muted-foreground/60 text-center">
                        Complete your first task to generate performance metrics
                    </p>
                </CardContent>
            </Card>
        );
    }

    const data = [
        { metric: "Security", value: metrics.security, fullMark: 100 },
        { metric: "Stability", value: metrics.stability, fullMark: 100 },
        { metric: "Quality", value: metrics.quality, fullMark: 100 },
        { metric: "Speed", value: metrics.speed, fullMark: 100 },
    ];

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Activity className="h-4 w-4 text-cyan-400" />
                    Health Radar
                    <Tooltip content={INFO_TEXT}>
                        <Info className="h-3.5 w-3.5 text-muted-foreground/40 cursor-help ml-1" />
                    </Tooltip>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                    <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
                        <PolarGrid
                            stroke="rgba(255,255,255,0.08)"
                            gridType="polygon"
                        />
                        <PolarAngleAxis
                            dataKey="metric"
                            tick={({ payload, x, y, textAnchor }: { payload: { value: string }; x: number; y: number; textAnchor: string }) => {
                                const item = data.find((d) => d.metric === payload.value);
                                const anchor = textAnchor as "start" | "middle" | "end";
                                return (
                                    <g>
                                        <text
                                            x={x}
                                            y={y}
                                            textAnchor={anchor}
                                            fill="#94a3b8"
                                            fontSize={12}
                                            fontWeight={500}
                                        >
                                            {payload.value}
                                        </text>
                                        <text
                                            x={x}
                                            y={y + 14}
                                            textAnchor={anchor}
                                            fill="#06b6d4"
                                            fontSize={10}
                                            fontWeight={600}
                                        >
                                            {item?.value ?? 0}
                                        </text>
                                    </g>
                                );
                            }}
                        />
                        <PolarRadiusAxis
                            angle={90}
                            domain={[0, 100]}
                            tickCount={5}
                            tick={{ fill: "#475569", fontSize: 9 }}
                            axisLine={false}
                        />
                        <RechartsTooltip
                            contentStyle={{
                                background: "#1e293b",
                                border: "1px solid #334155",
                                borderRadius: 8,
                                color: "#e2e8f0",
                                fontSize: 12,
                            }}
                        />
                        <Radar
                            dataKey="value"
                            stroke="#06b6d4"
                            fill="#06b6d4"
                            fillOpacity={0.2}
                            strokeWidth={2}
                            dot={{ r: 3, fill: "#06b6d4" }}
                        />
                    </RadarChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}
