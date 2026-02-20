"use client";

import { useState } from "react";
import type { DebateResult, DebateOption } from "@/lib/types";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { HelpCircle, User } from "lucide-react";

interface DecisionGateProps {
    debate: DebateResult;
    onResolve: (option: string) => void;
}

export function DecisionGate({ debate, onResolve }: DecisionGateProps) {
    const [open, setOpen] = useState(true);
    const [selected, setSelected] = useState<string | null>(null);

    const handleSelect = (option: DebateOption) => {
        setSelected(option.label);
        setTimeout(() => {
            onResolve(option.label);
            setOpen(false);
        }, 300);
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent className="sm:max-w-xl bg-[#0f172a] border-blue-500/30 shadow-2xl shadow-blue-500/5">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-xl text-blue-400">
                        <HelpCircle className="h-6 w-6" />
                        <span>🤔 Agents Disagree — Your Decision Required</span>
                    </DialogTitle>
                    <DialogDescription className="text-sm text-muted-foreground pt-2">
                        {debate.summary}
                    </DialogDescription>
                </DialogHeader>

                {/* ── Option cards ─────────────────────────────────────── */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                    {debate.options.map((opt, i) => (
                        <Card
                            key={opt.label}
                            onClick={() => handleSelect(opt)}
                            className={cn(
                                "cursor-pointer border-2 transition-all hover:border-blue-400/60 hover:bg-blue-500/5",
                                selected === opt.label
                                    ? "border-blue-400 bg-blue-500/10 scale-[1.02]"
                                    : "border-border/40 bg-white/[0.02]"
                            )}
                        >
                            <CardContent className="py-4 space-y-3">
                                <div className="flex items-center justify-between">
                                    <Badge
                                        variant="secondary"
                                        className="bg-blue-500/10 text-blue-400 text-xs"
                                    >
                                        Option {String.fromCharCode(65 + i)}
                                    </Badge>
                                </div>
                                <p className="text-sm font-medium">{opt.label}</p>
                                <p className="text-xs text-muted-foreground">
                                    {opt.description}
                                </p>
                                <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/60">
                                    <User className="h-3 w-3" />
                                    Recommended by: {opt.recommended_by}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </DialogContent>
        </Dialog>
    );
}
