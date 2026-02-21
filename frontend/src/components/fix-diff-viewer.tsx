"use client";

import type { FixProposal } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, FileCode } from "lucide-react";
import { cn } from "@/lib/utils";

// ── Line-level diff computation ────────────────────────────────────────────

interface DiffLine {
    type: "removed" | "added" | "context";
    lineNum: number | null;
    content: string;
}

function computeDiff(original: string, fixed: string): DiffLine[] {
    const origLines = original ? original.split("\n") : [];
    const fixedLines = fixed ? fixed.split("\n") : [];
    const lines: DiffLine[] = [];

    // Simple diff: show all original as removed, all fixed as added
    // For small targeted fixes this is clear enough
    for (let i = 0; i < origLines.length; i++) {
        lines.push({ type: "removed", lineNum: i + 1, content: origLines[i] });
    }
    for (let i = 0; i < fixedLines.length; i++) {
        lines.push({ type: "added", lineNum: i + 1, content: fixedLines[i] });
    }
    return lines;
}

// ── Component ──────────────────────────────────────────────────────────────

interface FixDiffViewerProps {
    fix: FixProposal;
    onApply?: (fix: FixProposal) => void;
    onReject?: (fix: FixProposal) => void;
    className?: string;
    /** Hide action buttons (read-only mode) */
    readOnly?: boolean;
}

export function FixDiffViewer({
    fix,
    onApply,
    onReject,
    className,
    readOnly = false,
}: FixDiffViewerProps) {
    const diff = computeDiff(fix.original_code, fix.fixed_code);
    const isApplied = fix.status === "applied";
    const isRejected = fix.status === "rejected";
    const showActions = !readOnly && fix.status === "proposed";

    return (
        <div
            className={cn(
                "rounded-xl border overflow-hidden transition-all",
                isApplied
                    ? "border-emerald-500/30"
                    : isRejected
                        ? "border-red-500/20 opacity-50"
                        : "border-border/40",
                className
            )}
        >
            {/* ── File header ──────────────────────────────────────── */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-[#0a0e1a] border-b border-border/30">
                <div className="flex items-center gap-2 min-w-0">
                    <FileCode className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                    <span className="text-xs font-mono text-indigo-400 truncate">
                        {fix.file_path}
                    </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <Badge
                        variant="outline"
                        className="text-[10px] border-indigo-500/20 text-indigo-400"
                    >
                        {fix.agent_type.replace("_", " ")}
                    </Badge>
                    {isApplied && (
                        <Badge
                            variant="outline"
                            className="text-[10px] border-emerald-500/20 text-emerald-400"
                        >
                            ✅ Applied
                        </Badge>
                    )}
                </div>
            </div>

            {/* ── Explanation ───────────────────────────────────────── */}
            <div className="px-4 py-2.5 bg-[#0c1120] border-b border-border/20">
                <p className="text-xs text-muted-foreground leading-relaxed">
                    💡 {fix.explanation}
                </p>
            </div>

            {/* ── Diff view ────────────────────────────────────────── */}
            <div className="overflow-x-auto max-h-80">
                <table className="w-full border-collapse font-mono text-[12px] leading-[1.6]">
                    <tbody>
                        {diff.map((line, i) => (
                            <tr
                                key={i}
                                className={cn(
                                    line.type === "removed" && "bg-red-500/[0.06]",
                                    line.type === "added" && "bg-emerald-500/[0.06]"
                                )}
                            >
                                {/* Line number */}
                                <td className="w-[42px] px-2 text-right select-none shrink-0 text-muted-foreground/30 border-r border-border/10">
                                    {line.lineNum}
                                </td>
                                {/* Sign */}
                                <td
                                    className={cn(
                                        "w-[18px] px-1 select-none text-center",
                                        line.type === "removed" && "text-red-500/60",
                                        line.type === "added" && "text-emerald-500/60"
                                    )}
                                >
                                    {line.type === "removed" ? "−" : line.type === "added" ? "+" : " "}
                                </td>
                                {/* Code */}
                                <td className="px-3 whitespace-pre-wrap">
                                    <span
                                        className={cn(
                                            line.type === "removed" && "text-red-300/80",
                                            line.type === "added" && "text-emerald-300/80",
                                            line.type === "context" && "text-slate-400"
                                        )}
                                    >
                                        {line.content || " "}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* ── Test code (if present) ───────────────────────────── */}
            {fix.test_code && (
                <div className="border-t border-border/20">
                    <div className="px-4 py-1.5 bg-violet-500/[0.04] border-b border-border/10">
                        <span className="text-[10px] font-semibold text-violet-400 uppercase tracking-wider">
                            🧪 Associated Test
                        </span>
                    </div>
                    <div className="overflow-x-auto max-h-40">
                        <pre className="px-4 py-2 font-mono text-[11px] text-violet-300/70 whitespace-pre-wrap leading-relaxed">
                            {fix.test_code}
                        </pre>
                    </div>
                </div>
            )}

            {/* ── Actions ──────────────────────────────────────────── */}
            {showActions && (
                <div className="flex items-center gap-2 px-4 py-3 bg-[#0a0e1a] border-t border-border/30">
                    <button
                        onClick={() => onApply?.(fix)}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600/20 py-2 text-xs font-medium text-emerald-400 hover:bg-emerald-600/30 transition-colors"
                    >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Apply Fix
                    </button>
                    <button
                        onClick={() => onReject?.(fix)}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-red-600/10 py-2 text-xs font-medium text-red-400/80 hover:bg-red-600/20 transition-colors"
                    >
                        <XCircle className="h-3.5 w-3.5" />
                        Reject
                    </button>
                </div>
            )}
        </div>
    );
}
