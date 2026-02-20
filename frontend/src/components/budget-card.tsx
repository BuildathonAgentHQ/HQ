"use client";

import type { WebSocketEvent } from "@/lib/types";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { DollarSign, Plus, XCircle } from "lucide-react";

interface BudgetPayload {
    current_cost?: number;
    budget_limit?: number;
}

interface BudgetCardProps {
    event: WebSocketEvent;
    onAction: (action: string) => void;
}

export function BudgetCard({ event, onAction }: BudgetCardProps) {
    const payload = event.payload as unknown as BudgetPayload;
    const cost = payload?.current_cost ?? 0;
    const limit = payload?.budget_limit ?? 0;
    const overage = Math.max(cost - limit, 0);
    const pct = limit > 0 ? Math.min((cost / limit) * 100, 120) : 100;

    return (
        <Card className="border-red-500/30 bg-red-500/5 animate-fade-in my-2">
            <CardContent className="py-4 space-y-3">
                <div className="flex items-center gap-2">
                    <DollarSign className="h-5 w-5 text-red-400" />
                    <span className="font-semibold text-red-400">
                        💰 Budget Exceeded
                    </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                        <p className="text-[10px] text-muted-foreground uppercase">
                            Current
                        </p>
                        <p className="font-mono font-medium">${cost.toFixed(2)}</p>
                    </div>
                    <div>
                        <p className="text-[10px] text-muted-foreground uppercase">Limit</p>
                        <p className="font-mono font-medium">${limit.toFixed(2)}</p>
                    </div>
                    <div>
                        <p className="text-[10px] text-muted-foreground uppercase">
                            Overage
                        </p>
                        <p className="font-mono font-medium text-red-400">
                            +${overage.toFixed(2)}
                        </p>
                    </div>
                </div>

                <Progress
                    value={Math.min(pct, 100)}
                    className="h-2"
                    indicatorClassName="bg-red-500"
                />

                <div className="flex gap-2 pt-1">
                    <Button
                        size="sm"
                        className="gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white flex-1"
                        onClick={() => onAction("add_budget")}
                    >
                        <Plus className="h-3.5 w-3.5" />
                        Add $2.00 and Continue
                    </Button>
                    <Button
                        size="sm"
                        variant="destructive"
                        className="gap-1.5 flex-1"
                        onClick={() => onAction("terminate")}
                    >
                        <XCircle className="h-3.5 w-3.5" />
                        Terminate Task
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
