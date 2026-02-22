import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Check, X, Code2 } from "lucide-react";

export interface TestPreviewState {
    status: "idle" | "generating" | "reviewing" | "applying";
    prNumber: number | null;
    taskId: string | null;
    code: string | null;
    liveStatus?: string;
}

interface TestPreviewModalProps {
    preview: TestPreviewState;
    onDismiss: () => void;
    onApprove: (taskId: string) => void;
}

export function TestPreviewModal({ preview, onDismiss, onApprove }: TestPreviewModalProps) {
    const isGenerating = preview.status === "generating";
    const isApplying = preview.status === "applying";
    const isOpen = preview.status !== "idle";

    // Try to extract just the code blocks from the raw output for a cleaner preview
    const cleanCode = preview.code
        ? preview.code.split("```").filter((_, i) => i % 2 !== 0).join("\n\n") || preview.code
        : "";

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && !isApplying && onDismiss()}>
            <DialogContent className="sm:max-w-2xl bg-card border-border/40 shadow-2xl">
                <DialogHeader className="pb-4 border-b border-border/20">
                    <DialogTitle className="flex items-center gap-2 text-lg">
                        <Code2 className="h-5 w-5 text-indigo-400" />
                        Test Generation {preview.prNumber ? `(PR #${preview.prNumber})` : ""}
                    </DialogTitle>
                    <DialogDescription className="text-xs">
                        {isGenerating ? "Agent is writing tests..." : "Review the generated tests before committing."}
                    </DialogDescription>
                </DialogHeader>

                <div className="py-4">
                    {isGenerating ? (
                        <div className="flex flex-col items-center justify-center py-12 space-y-4">
                            <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
                            <div className="text-sm text-muted-foreground flex items-center gap-2">
                                <span className="animate-pulse">{preview.liveStatus || "Analyzing untested files and writing tests..."}</span>
                            </div>
                        </div>
                    ) : (
                        <div className="h-[400px] w-full rounded-md border border-border/30 bg-black/40 p-4 overflow-y-auto">
                            <pre className="text-xs font-mono text-emerald-400/90 whitespace-pre-wrap break-words">
                                {cleanCode || "No code output found."}
                            </pre>
                        </div>
                    )}
                </div>

                <DialogFooter className="pt-4 border-t border-border/20">
                    <Button
                        variant="ghost"
                        onClick={onDismiss}
                        disabled={isGenerating || isApplying}
                        className="text-muted-foreground hover:text-white"
                    >
                        <X className="h-4 w-4 mr-2" />
                        {isGenerating ? "Cancel" : "Dismiss"}
                    </Button>
                    {!isGenerating && (
                        <Button
                            onClick={() => preview.taskId && onApprove(preview.taskId)}
                            disabled={isApplying || !preview.code}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                        >
                            {isApplying ? (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                                <Check className="h-4 w-4 mr-2" />
                            )}
                            Approve & Create PR
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
