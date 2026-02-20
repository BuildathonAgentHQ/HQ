"use client";

import { useState, useRef, useEffect } from "react";
import type { ApprovalRequest } from "@/lib/types";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle, ShieldAlert } from "lucide-react";

interface ApprovalModalProps {
    approvalRequest: ApprovalRequest;
    onResolve: (option: string) => void;
}

export function ApprovalModal({ approvalRequest, onResolve }: ApprovalModalProps) {
    const [open, setOpen] = useState(true);
    const [holdProgress, setHoldProgress] = useState(0);
    const holdTimer = useRef<ReturnType<typeof setInterval> | null>(null);
    const rejectRef = useRef<HTMLButtonElement>(null);

    // Auto-focus reject button (safe default)
    useEffect(() => {
        setTimeout(() => rejectRef.current?.focus(), 100);
    }, []);

    const handleApproveStart = () => {
        holdTimer.current = setInterval(() => {
            setHoldProgress((prev) => {
                if (prev >= 100) {
                    if (holdTimer.current) clearInterval(holdTimer.current);
                    holdTimer.current = null;
                    onResolve("approve");
                    setOpen(false);
                    return 0;
                }
                return prev + 100 / 30; // 3 seconds total (30 intervals at 100ms)
            });
        }, 100);
    };

    const handleApproveEnd = () => {
        if (holdTimer.current) {
            clearInterval(holdTimer.current);
            holdTimer.current = null;
        }
        setHoldProgress(0);
    };

    const handleReject = () => {
        onResolve("reject");
        setOpen(false);
    };

    return (
        <Dialog open={open} onOpenChange={(v) => !v && handleReject()}>
            <DialogContent className="sm:max-w-lg border-red-500/50 bg-[#0f172a] shadow-2xl shadow-red-500/10">
                <div className="absolute inset-0 rounded-lg border-2 border-red-500/20 pointer-events-none" />

                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-xl text-red-400">
                        <ShieldAlert className="h-6 w-6" />
                        <span>⚠️ High-Risk Action Detected</span>
                    </DialogTitle>
                    <DialogDescription className="text-sm text-muted-foreground pt-2">
                        {approvalRequest.description}
                    </DialogDescription>
                </DialogHeader>

                {/* ── Command display ──────────────────────────────────── */}
                {approvalRequest.command && (
                    <div className="rounded-md bg-slate-800/50 border border-slate-700/50 px-4 py-3 font-mono text-xs text-slate-300 break-all">
                        {approvalRequest.command}
                    </div>
                )}

                <DialogFooter className="flex gap-3 sm:justify-between mt-4">
                    <Button
                        ref={rejectRef}
                        variant="outline"
                        onClick={handleReject}
                        className="flex-1 border-slate-600 hover:bg-slate-800 text-slate-300"
                    >
                        Reject — Cancel &amp; Try Alternative
                    </Button>

                    <div className="relative flex-1">
                        <Button
                            variant="destructive"
                            className="w-full bg-red-600/80 hover:bg-red-600 text-white relative overflow-hidden"
                            onMouseDown={handleApproveStart}
                            onMouseUp={handleApproveEnd}
                            onMouseLeave={handleApproveEnd}
                            onTouchStart={handleApproveStart}
                            onTouchEnd={handleApproveEnd}
                        >
                            <span className="relative z-10 flex items-center gap-2">
                                <AlertTriangle className="h-4 w-4" />
                                {holdProgress > 0
                                    ? `Hold… ${Math.round((3 * (100 - holdProgress)) / 100)}s`
                                    : "Approve — Hold 3s to Confirm"}
                            </span>
                            {holdProgress > 0 && (
                                <span
                                    className="absolute inset-0 bg-red-500 transition-all duration-100"
                                    style={{ width: `${holdProgress}%` }}
                                />
                            )}
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
