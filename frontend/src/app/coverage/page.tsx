"use client";

import { useEffect, useState } from "react";
import {
    Shield,
    TrendingUp,
    TrendingDown,
    Minus,
    TestTube2,
    AlertCircle,
    CheckCircle2,
    XCircle,
    GitPullRequest,
    FileCode,
    Loader2,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/constants";

interface PRFeature {
    pr_number: number;
    title: string;
    author: string;
    total_files: number;
    source_files: number;
    test_files: number;
    has_tests: boolean;
    coverage_status: "covered" | "partial" | "uncovered";
}

interface UntestedDiff {
    file_path: string;
    lines_uncovered: number;
    risk: string;
    pr_number?: number;
    pr_title?: string;
}

interface CoverageData {
    total_coverage_pct: number;
    module_coverage: Record<string, number>;
    untested_diffs: UntestedDiff[];
    trend: string;
    pr_features: PRFeature[];
    total_prs: number;
    prs_with_tests: number;
}

export default function CoveragePage() {
    const [data, setData] = useState<CoverageData | null>(null);
    const [loading, setLoading] = useState(true);
    const [dispatching, setDispatching] = useState<string | null>(null);
    const [dispatchResult, setDispatchResult] = useState<Record<string, any>>({});

    useEffect(() => {
        async function fetchData() {
            try {
                const res = await fetch(`${API_BASE_URL}/control-plane/coverage`);
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

    const generateTests = async (diff: UntestedDiff) => {
        const key = diff.file_path;
        setDispatching(key);
        setDispatchResult((prev) => ({ ...prev, [key]: undefined }));
        try {
            const res = await fetch(`${API_BASE_URL}/swarm/dispatch`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action_type: "add_tests",
                    description: `Write unit tests for ${diff.file_path} (${diff.lines_uncovered} untested lines from PR #${diff.pr_number}: ${diff.pr_title}).`,
                    target: diff.file_path,
                }),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || "Dispatch failed");
            }
            const result = await res.json();
            setDispatchResult((prev) => ({ ...prev, [key]: result }));
        } catch (e: any) {
            setDispatchResult((prev) => ({
                ...prev,
                [key]: { status: "error", message: e.message },
            }));
        } finally {
            setDispatching(null);
        }
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-32 w-full bg-zinc-900/50 rounded-xl animate-pulse" />
                <div className="h-96 w-full bg-zinc-900/50 rounded-xl animate-pulse" />
            </div>
        );
    }

    const testedFeatures = data?.prs_with_tests ?? 0;
    const totalFeatures = data?.total_prs ?? 0;
    const untestedFeatures = totalFeatures - testedFeatures;

    return (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
            <div>
                <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                    <Shield className="h-8 w-8 text-emerald-500" />
                    Coverage Map
                </h1>
                <p className="text-muted-foreground mt-2">
                    Feature-level test coverage across all PRs (open &amp; closed).
                </p>
            </div>

            {/* Top stat */}
            <Card className="border-zinc-800 bg-zinc-900/50 flex flex-col items-center justify-center p-6">
                <CardHeader className="text-center p-0 mb-2">
                    <CardTitle className="text-lg font-medium text-zinc-400">
                        Feature Coverage
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0 text-center">
                    <div
                        className={`text-5xl font-black mb-1 ${
                            (data?.total_coverage_pct ?? 0) > 70
                                ? "text-green-500"
                                : (data?.total_coverage_pct ?? 0) > 40
                                ? "text-yellow-500"
                                : "text-red-500"
                        }`}
                    >
                        {testedFeatures}/{totalFeatures}
                    </div>
                    <p className="text-sm text-zinc-500 mb-2">Features with test coverage</p>
                    <div className="flex items-center justify-center gap-2 text-zinc-400">
                        {data?.trend === "improving" ? (
                            <>
                                <TrendingUp className="h-4 w-4 text-green-500" />
                                <span className="text-green-500">Improving</span>
                            </>
                        ) : data?.trend === "declining" ? (
                            <>
                                <TrendingDown className="h-4 w-4 text-red-500" />
                                <span className="text-red-500">Declining</span>
                            </>
                        ) : (
                            <>
                                <Minus className="h-4 w-4" />
                                <span>Stable</span>
                            </>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* PR feature breakdown */}
            <Card className="border-zinc-800 bg-zinc-900/50">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-indigo-400">
                        <GitPullRequest className="h-5 w-5" />
                        PR Feature Breakdown
                    </CardTitle>
                    <CardDescription>
                        {testedFeatures} of {totalFeatures} features across all PRs (open &amp; closed) have test coverage.{" "}
                        {untestedFeatures > 0 && (
                            <span className="text-red-400 font-medium">
                                {untestedFeatures} feature{untestedFeatures > 1 ? "s" : ""} without any tests.
                            </span>
                        )}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-3">
                        {data?.pr_features?.map((pr) => (
                            <div
                                key={pr.pr_number}
                                className="flex items-center justify-between p-4 rounded-lg border border-zinc-800/50 bg-black/20 hover:bg-zinc-800/20 transition-colors"
                            >
                                <div className="flex items-center gap-4 min-w-0">
                                    {pr.coverage_status === "covered" ? (
                                        <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                                    ) : pr.coverage_status === "partial" ? (
                                        <AlertCircle className="h-5 w-5 text-yellow-500 shrink-0" />
                                    ) : (
                                        <XCircle className="h-5 w-5 text-red-500 shrink-0" />
                                    )}
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium text-zinc-200 truncate">
                                            #{pr.pr_number} {pr.title}
                                        </p>
                                        <p className="text-xs text-zinc-500">
                                            by {pr.author} · {pr.source_files} source file
                                            {pr.source_files !== 1 ? "s" : ""} · {pr.test_files} test file
                                            {pr.test_files !== 1 ? "s" : ""}
                                        </p>
                                    </div>
                                </div>
                                <Badge
                                    variant="outline"
                                    className={`shrink-0 ml-4 ${
                                        pr.coverage_status === "covered"
                                            ? "border-green-500/30 text-green-500 bg-green-500/10"
                                            : pr.coverage_status === "partial"
                                            ? "border-yellow-500/30 text-yellow-500 bg-yellow-500/10"
                                            : "border-red-500/30 text-red-500 bg-red-500/10"
                                    }`}
                                >
                                    {pr.coverage_status === "covered"
                                        ? "Tests included"
                                        : pr.coverage_status === "partial"
                                        ? "Partial tests"
                                        : "No tests"}
                                </Badge>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Untested files */}
            <Card className="border-zinc-800 bg-zinc-900/50">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-orange-400">
                        <FileCode className="h-5 w-5" />
                        Untested Source Files
                    </CardTitle>
                    <CardDescription>
                        Source files from PRs that have zero test coverage. Dispatch an agent to auto-generate tests and create a PR.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs text-zinc-400 uppercase bg-black/20 border-b border-zinc-800">
                                <tr>
                                    <th className="px-4 py-3 font-medium">File Path</th>
                                    <th className="px-4 py-3 font-medium">From PR</th>
                                    <th className="px-4 py-3 font-medium text-center">
                                        Uncovered Lines
                                    </th>
                                    <th className="px-4 py-3 font-medium">Risk Level</th>
                                    <th className="px-4 py-3 font-medium text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-800/50">
                                {data?.untested_diffs && data.untested_diffs.length > 0 ? (
                                    data.untested_diffs.map((diff, i) => {
                                        const key = diff.file_path;
                                        const result = dispatchResult[key];
                                        const isRunning = dispatching === key;

                                        return (
                                            <tr
                                                key={i}
                                                className="hover:bg-zinc-800/20 transition-colors"
                                            >
                                                <td className="px-4 py-3 font-mono text-zinc-300">
                                                    {diff.file_path}
                                                </td>
                                                <td className="px-4 py-3 text-zinc-400 text-xs">
                                                    <span className="text-indigo-400">
                                                        #{diff.pr_number}
                                                    </span>{" "}
                                                    {diff.pr_title}
                                                </td>
                                                <td className="px-4 py-3 text-center text-zinc-400">
                                                    {diff.lines_uncovered}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <Badge
                                                        variant="outline"
                                                        className={`
                                                            ${diff.risk.includes("critical") ? "border-red-500/30 text-red-500 bg-red-500/10" : ""}
                                                            ${diff.risk.includes("high") ? "border-orange-500/30 text-orange-500 bg-orange-500/10" : ""}
                                                            ${diff.risk.includes("medium") ? "border-yellow-500/30 text-yellow-500 bg-yellow-500/10" : ""}
                                                        `}
                                                    >
                                                        {diff.risk}
                                                    </Badge>
                                                </td>
                                                <td className="px-4 py-3 text-right">
                                                    {result?.status === "dispatched" ? (
                                                        <span className="text-xs text-green-400">
                                                            Agent dispatched — PR incoming
                                                        </span>
                                                    ) : result?.status === "error" ? (
                                                        <span className="text-xs text-red-400">
                                                            {result.message}
                                                        </span>
                                                    ) : (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="hover:bg-indigo-500/20 hover:text-indigo-400 text-indigo-500"
                                                            disabled={isRunning}
                                                            onClick={() =>
                                                                generateTests(diff)
                                                            }
                                                        >
                                                            {isRunning ? (
                                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                            ) : (
                                                                <TestTube2 className="h-4 w-4 mr-2" />
                                                            )}
                                                            {isRunning
                                                                ? "Dispatching…"
                                                                : "Generate Tests"}
                                                        </Button>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })
                                ) : (
                                    <tr>
                                        <td
                                            colSpan={5}
                                            className="px-4 py-8 text-center text-zinc-500 italic"
                                        >
                                            All PRs have test coverage. Great job!
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
