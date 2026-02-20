"use client";

import { useEffect, useState } from "react";
import { Shield, TrendingUp, TrendingDown, Minus, TestTube2, AlertCircle } from "lucide-react";
import { Treemap, Tooltip, ResponsiveContainer } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function CoveragePage() {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchData() {
            try {
                const res = await fetch("/api/control-plane/coverage");
                if (res.ok) {
                    setData(await res.json());
                }
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, []);

    const generateTests = async (file_path: string) => {
        try {
            await fetch("/api/tasks/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    task: `Write unit tests for untested functions in ${file_path}.`,
                    engine: "claude-code",
                    agent_type: "test_writer",
                    budget_limit: 2.5
                })
            });
            alert(`Test Writer Agent dispatched for ${file_path}!`);
        } catch (e) {
            alert("Failed to dispatch agent");
        }
    };

    // Convert dict to recharts treemap format
    const getTreemapData = () => {
        if (!data?.module_coverage) return [];

        return [
            {
                name: "Modules",
                children: Object.entries(data.module_coverage).map(([name, pct]) => ({
                    name,
                    size: 100, // using a fixed size for the treemap purely to visualize the percent color block
                    pct: pct as number,
                    fill: (pct as number) > 80 ? "#22c55e" : (pct as number) > 50 ? "#eab308" : "#ef4444"
                }))
            }
        ];
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-32 w-full bg-zinc-900/50 rounded-xl animate-pulse" />
                <div className="h-96 w-full bg-zinc-900/50 rounded-xl animate-pulse" />
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
            <div>
                <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                    <Shield className="h-8 w-8 text-emerald-500" />
                    Coverage Map
                </h1>
                <p className="text-muted-foreground mt-2">
                    Repository-wide test coverage analytics and unvalidated code paths.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-4">
                {/* Main Stat */}
                <Card className="col-span-4 md:col-span-1 border-zinc-800 bg-zinc-900/50 flex flex-col items-center justify-center p-6">
                    <CardHeader className="text-center p-0 mb-2">
                        <CardTitle className="text-lg font-medium text-zinc-400">Total Coverage</CardTitle>
                    </CardHeader>
                    <CardContent className="p-0 text-center">
                        <div className={`text-6xl font-black mb-2 ${data?.total_coverage_pct > 80 ? 'text-green-500' : data?.total_coverage_pct > 50 ? 'text-yellow-500' : 'text-red-500'}`}>
                            {data?.total_coverage_pct}%
                        </div>
                        <div className="flex items-center justify-center gap-2 text-zinc-400">
                            {data?.trend === "improving" ? (
                                <><TrendingUp className="h-4 w-4 text-green-500" /> <span className="text-green-500">Improving</span></>
                            ) : data?.trend === "declining" ? (
                                <><TrendingDown className="h-4 w-4 text-red-500" /> <span className="text-red-500">Declining</span></>
                            ) : (
                                <><Minus className="h-4 w-4" /> <span>Stable</span></>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Treemap */}
                <Card className="col-span-4 md:col-span-3 border-zinc-800 bg-zinc-900/50">
                    <CardHeader>
                        <CardTitle>Module Map</CardTitle>
                        <CardDescription>Visual distribution of test density.</CardDescription>
                    </CardHeader>
                    <CardContent className="h-[250px] w-full">
                        {Object.keys(data?.module_coverage || {}).length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <Treemap
                                    data={getTreemapData()}
                                    dataKey="size"
                                    aspectRatio={4 / 3}
                                    stroke="#18181b"
                                    fill="#8884d8"
                                >
                                    <Tooltip
                                        content={({ payload }) => {
                                            if (payload && payload.length) {
                                                const cell = payload[0].payload;
                                                return (
                                                    <div className="bg-zinc-900 border border-zinc-800 p-2 rounded shadow-xl">
                                                        <p className="font-bold text-zinc-100">{cell.name}</p>
                                                        <p className="text-zinc-400">Coverage: {cell.pct}%</p>
                                                    </div>
                                                );
                                            }
                                            return null;
                                        }}
                                    />
                                </Treemap>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full w-full flex items-center justify-center text-zinc-500">
                                No module data available to render.
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            <Card className="border-zinc-800 bg-zinc-900/50">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-orange-400">
                        <AlertCircle className="h-5 w-5" />
                        Untested Diffs
                    </CardTitle>
                    <CardDescription>
                        Recent changes without corresponding test coverage.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs text-zinc-400 uppercase bg-black/20 border-b border-zinc-800">
                                <tr>
                                    <th className="px-4 py-3 font-medium">File Path</th>
                                    <th className="px-4 py-3 font-medium text-center">Uncovered Lines</th>
                                    <th className="px-4 py-3 font-medium">Risk Level</th>
                                    <th className="px-4 py-3 font-medium text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-800/50">
                                {data?.untested_diffs?.length > 0 ? data.untested_diffs.map((diff: any, i: number) => (
                                    <tr key={i} className="hover:bg-zinc-800/20 transition-colors">
                                        <td className="px-4 py-3 font-mono text-zinc-300">
                                            {diff.file_path}
                                        </td>
                                        <td className="px-4 py-3 text-center text-zinc-400">
                                            {diff.lines_uncovered}
                                        </td>
                                        <td className="px-4 py-3">
                                            <Badge variant="outline" className={`
                        ${diff.risk.includes("critical") ? "border-red-500/30 text-red-500 bg-red-500/10" : ""}
                        ${diff.risk.includes("high") ? "border-orange-500/30 text-orange-500 bg-orange-500/10" : ""}
                        ${diff.risk.includes("medium") ? "border-yellow-500/30 text-yellow-500 bg-yellow-500/10" : ""}
                      `}>
                                                {diff.risk}
                                            </Badge>
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="hover:bg-indigo-500/20 hover:text-indigo-400 text-indigo-500"
                                                onClick={() => generateTests(diff.file_path)}
                                            >
                                                <TestTube2 className="h-4 w-4 mr-2" />
                                                Generate
                                            </Button>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr>
                                        <td colSpan={4} className="px-4 py-8 text-center text-zinc-500 italic">
                                            All recent code is fully tested. Great job!
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
