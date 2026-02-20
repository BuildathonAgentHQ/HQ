"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE_URL } from "@/lib/constants";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GitCommit, RotateCcw } from "lucide-react";

interface TimelineCommit {
    hash: string;
    message: string;
    timestamp: string;
    author: string;
}

// Maps backend response fields to our interface
function normalizeCommit(c: Record<string, string>): TimelineCommit {
    return {
        hash: c.sha || c.hash || "",
        message: c.message || "",
        timestamp: c.date || c.timestamp || "",
        author: c.author || "",
    };
}

export function TimelineSlider() {
    const [commits, setCommits] = useState<TimelineCommit[] | null>(null);
    const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchCommits = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/timeline`);
            if (res.ok) {
                const raw = await res.json();
                const data = Array.isArray(raw) ? raw.map(normalizeCommit) : [];
                setCommits(data);
                if (data.length > 0) setSelectedIdx(data.length - 1);
            }
        } catch {
            // show placeholder
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchCommits();
    }, [fetchCommits]);

    const handleSliderChange = async (idx: number) => {
        if (!commits) return;
        setSelectedIdx(idx);

        if (idx < commits.length - 1) {
            try {
                await fetch(`${API_BASE_URL}/api/timeline/checkout`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ commit_hash: commits[idx].hash }),
                });
            } catch {
                // ignore
            }
        }
    };

    const handleReset = async () => {
        if (!commits) return;
        setSelectedIdx(commits.length - 1);
        try {
            await fetch(`${API_BASE_URL}/api/timeline/checkout`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ commit_hash: "HEAD" }),
            });
        } catch {
            // ignore
        }
    };

    /* ── Loading / Placeholder ────────────────────────────────── */
    if (loading) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardContent className="py-4">
                    <Skeleton className="h-10 w-full" />
                </CardContent>
            </Card>
        );
    }

    if (!commits || commits.length === 0) {
        return (
            <Card className="border-border/40 bg-card/60 backdrop-blur">
                <CardContent className="py-4 text-center">
                    <p className="text-sm text-muted-foreground/60">
                        Timeline coming soon — no commits yet
                    </p>
                </CardContent>
            </Card>
        );
    }

    const current = selectedIdx !== null ? commits[selectedIdx] : null;
    const isLatest = selectedIdx === commits.length - 1;

    return (
        <Card className="border-border/40 bg-card/60 backdrop-blur">
            <CardHeader className="py-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                    <GitCommit className="h-4 w-4 text-indigo-400" />
                    Agent Timeline
                    {!isLatest && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="ml-auto h-6 gap-1 text-xs text-muted-foreground hover:text-white"
                            onClick={handleReset}
                        >
                            <RotateCcw className="h-3 w-3" />
                            Reset to Latest
                        </Button>
                    )}
                </CardTitle>
            </CardHeader>
            <CardContent className="pb-4 space-y-3">
                {/* ── Slider track ─────────────────────────────────────── */}
                <div className="relative">
                    {/* Dot markers */}
                    <div className="flex items-center justify-between px-1 mb-1">
                        {commits.map((c, i) => (
                            <div key={c.hash} className="group relative flex flex-col items-center">
                                <span
                                    className={`h-2.5 w-2.5 rounded-full transition-all cursor-pointer ${i === selectedIdx
                                        ? "bg-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.6)] scale-125"
                                        : "bg-slate-600 hover:bg-slate-400"
                                        }`}
                                    onClick={() => handleSliderChange(i)}
                                />
                                {/* Tooltip */}
                                <span className="absolute bottom-full mb-2 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity bg-popover border border-border/40 rounded-md px-2 py-1 text-[10px] text-popover-foreground shadow-md whitespace-nowrap max-w-[200px] truncate z-50">
                                    {c.message}
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Range input */}
                    <input
                        type="range"
                        min={0}
                        max={commits.length - 1}
                        value={selectedIdx ?? commits.length - 1}
                        onChange={(e) => handleSliderChange(parseInt(e.target.value))}
                        className="w-full h-1 appearance-none bg-slate-700 rounded-full cursor-pointer accent-indigo-500
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-400
              [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(99,102,241,0.6)]
              [&::-webkit-slider-thumb]:cursor-grab [&::-webkit-slider-thumb]:active:cursor-grabbing"
                    />
                </div>

                {/* ── Current commit info ──────────────────────────────── */}
                {current && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <code className="bg-white/[0.04] px-1.5 py-0.5 rounded text-[10px] font-mono">
                            {current.hash.slice(0, 7)}
                        </code>
                        <span className="truncate flex-1">{current.message}</span>
                        <span className="text-muted-foreground/40 shrink-0">
                            {new Date(current.timestamp).toLocaleDateString()}
                        </span>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
