"use client";

import { useEffect, useState } from "react";
import {
    GitPullRequest,
    AlertTriangle,
    CheckCircle2,
    ShieldAlert,
    Clock,
    Users,
    TestTube2,
    GitBranch
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface PRRiskFactors {
    diff_size: number;
    core_files_changed: boolean;
    missing_tests: boolean;
    churn_score: number;
    has_dependency_overlap: boolean;
}

interface PRRiskScore {
    pr_id: string;
    pr_number: number;
    title: string;
    author: string;
    risk_score: number;
    risk_level: "low" | "medium" | "high" | "critical";
    factors: PRRiskFactors;
    reviewers_suggested: string[];
}

export default function PRRadarPage() {
    const [prs, setPrs] = useState<PRRiskScore[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchPRs() {
            try {
                const res = await fetch("/api/control-plane/prs");
                if (res.ok) {
                    const data = await res.json();
                    setPrs(data);
                }
            } catch (e) {
                console.error("Failed to fetch PR scores:", e);
            } finally {
                setLoading(false);
            }
        }
        fetchPRs();
    }, []);

    const getRiskColor = (score: number) => {
        if (score < 25) return "text-green-500";
        if (score < 50) return "text-yellow-500";
        if (score < 75) return "text-orange-500";
        return "text-red-500";
    };

    const getRiskBg = (level: string) => {
        switch (level) {
            case "low": return "bg-green-500/10 text-green-500 border-green-500/20";
            case "medium": return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
            case "high": return "bg-orange-500/10 text-orange-500 border-orange-500/20";
            case "critical": return "bg-red-500/10 text-red-500 border-red-500/20";
            default: return "";
        }
    };

    const generateTests = async (prNumber: number) => {
        try {
            // Create a task targeting missing coverage
            await fetch("/api/tasks/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    task: `Write unit tests for untested files in PR #${prNumber}.`,
                    engine: "claude-code",
                    agent_type: "test_writer",
                    budget_limit: 2.0
                })
            });
            alert(`Test Writer Agent dispatched for PR #${prNumber}!`);
        } catch (e) {
            alert("Failed to dispatch agent");
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
            <div>
                <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                    <GitPullRequest className="h-8 w-8 text-indigo-500" />
                    PR Radar
                </h1>
                <p className="text-muted-foreground mt-2">
                    Real-time risk analysis of open pull requests.
                </p>
            </div>

            {loading ? (
                <div className="space-y-4">
                    {[1, 2, 3].map(i => (
                        <Card key={i} className="border-zinc-800 bg-zinc-900/50">
                            <CardContent className="p-6">
                                <Skeleton className="h-24 w-full" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            ) : prs.length === 0 ? (
                <Card className="border-zinc-800 bg-zinc-900/50">
                    <CardContent className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                        <CheckCircle2 className="h-12 w-12 text-green-500 mb-4" />
                        <p className="text-lg font-medium text-zinc-200">Inbox Zero</p>
                        <p>No open pull requests found.</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-4">
                    {prs.map(pr => (
                        <Card key={pr.pr_id} className="border-zinc-800 bg-zinc-900/50 overflow-hidden">
                            <div className="flex flex-col md:flex-row">
                                {/* Risk Score Panel */}
                                <div className={`p-6 flex flex-col items-center justify-center border-b md:border-b-0 md:border-r border-zinc-800 min-w-[150px] ${getRiskColor(pr.risk_score)} bg-black/20`}>
                                    <span className="text-5xl font-black tracking-tighter">{pr.risk_score}</span>
                                    <Badge variant="outline" className={`mt-2 uppercase tracking-wide font-bold ${getRiskBg(pr.risk_level)}`}>
                                        {pr.risk_level} Risk
                                    </Badge>
                                </div>

                                {/* Details Panel */}
                                <div className="p-6 flex-1 flex flex-col">
                                    <div className="flex justify-between items-start mb-4">
                                        <div>
                                            <h3 className="text-xl font-bold text-zinc-100 mb-1 flex items-center gap-2">
                                                <a href={`https://github.com/pull/${pr.pr_number}`} target="_blank" rel="noreferrer" className="hover:underline">
                                                    {pr.title}
                                                </a>
                                                <span className="text-zinc-500 text-sm font-normal">#{pr.pr_number}</span>
                                            </h3>
                                            <div className="flex items-center gap-4 text-sm text-zinc-400">
                                                <span className="flex items-center gap-1"><Users className="h-3 w-3" /> {pr.author}</span>
                                                <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> Recently updated</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex-1">
                                        <div className="flex flex-wrap gap-2 mb-4">
                                            {pr.factors.diff_size > 500 && (
                                                <Badge variant="secondary" className="bg-zinc-800 hover:bg-zinc-700">Large Diff ({pr.factors.diff_size})</Badge>
                                            )}
                                            {pr.factors.core_files_changed && (
                                                <Badge variant="secondary" className="bg-zinc-800 text-orange-400 border-orange-500/30">Core Files Touched</Badge>
                                            )}
                                            {pr.factors.missing_tests && (
                                                <Badge variant="secondary" className="bg-zinc-800 text-red-400 border-red-500/30">Missing Tests</Badge>
                                            )}
                                            {pr.factors.churn_score > 30 && (
                                                <Badge variant="secondary" className="bg-zinc-800">High Churn Area</Badge>
                                            )}
                                        </div>

                                        {pr.factors.has_dependency_overlap && (
                                            <div className="text-sm flex items-center gap-2 text-yellow-500 bg-yellow-500/10 p-2 rounded-md border border-yellow-500/20 mb-4 inline-flex">
                                                <GitBranch className="h-4 w-4" />
                                                <span>Warning: Dependency overlap with another PR</span>
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex items-center justify-between mt-auto pt-4 border-t border-zinc-800/50">
                                        <div className="flex items-center gap-2 text-sm text-zinc-400">
                                            <span>Suggested Reviewers:</span>
                                            <div className="flex gap-1">
                                                {pr.reviewers_suggested.length > 0 ? pr.reviewers_suggested.map((rev, i) => (
                                                    <Badge key={i} variant="outline" className="border-zinc-700 text-zinc-300">{rev}</Badge>
                                                )) : <span className="text-zinc-500 italic">None determined</span>}
                                            </div>
                                        </div>

                                        {pr.factors.missing_tests && (
                                            <Button
                                                size="sm"
                                                className="bg-indigo-600 hover:bg-indigo-700 text-white"
                                                onClick={() => generateTests(pr.pr_number)}
                                            >
                                                <TestTube2 className="h-4 w-4 mr-2" />
                                                Generate Tests
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
