"use client";

import { useCallback, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/constants";
import { useToast } from "@/hooks/use-toast";

import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Book, Upload, Trash2, FileText, Loader2 } from "lucide-react";

interface KBDocument {
    doc_id: string;
    filename: string;
    uploaded_at: string;
    chunk_count: number;
    size_bytes: number;
    status: string;
}

export function KnowledgeSidebar() {
    const [docs, setDocs] = useState<KBDocument[]>([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { toast } = useToast();

    const fetchDocs = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/api/knowledge/documents`);
            if (res.ok) {
                const data = await res.json();
                setDocs(data);
            }
        } catch {
            // API may not be running
        } finally {
            setLoading(false);
        }
    }, []);

    const handleUpload = async (files: FileList | null) => {
        if (!files || files.length === 0) return;
        setUploading(true);
        let successCount = 0;
        try {
            for (const file of Array.from(files)) {
                const formData = new FormData();
                formData.append("file", file);
                const res = await fetch(`${API_BASE_URL}/api/knowledge/upload`, {
                    method: "POST",
                    body: formData,
                });
                if (res.ok) {
                    successCount++;
                } else {
                    toast({
                        title: "Upload failed",
                        description: `Could not upload ${file.name}`,
                        variant: "destructive",
                    });
                }
            }
            if (successCount > 0) {
                toast({
                    title: "Upload complete",
                    description: `${successCount} file(s) uploaded successfully`,
                });
                await fetchDocs();
            }
        } catch (err) {
            toast({
                title: "Upload error",
                description: err instanceof Error ? err.message : "Network error during upload",
                variant: "destructive",
            });
        } finally {
            setUploading(false);
            // Reset file input so same file can be re-selected
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const handleDelete = async (docId: string) => {
        try {
            await fetch(`${API_BASE_URL}/api/knowledge/documents/${docId}`, {
                method: "DELETE",
            });
            setDocs((prev) => prev.filter((d) => d.doc_id !== docId));
            toast({ title: "Document removed" });
        } catch {
            toast({ title: "Delete failed", variant: "destructive" });
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        handleUpload(e.dataTransfer.files);
    };

    const handleClickUpload = () => {
        fileInputRef.current?.click();
    };

    return (
        <Sheet onOpenChange={(open) => open && fetchDocs()}>
            <SheetTrigger asChild>
                <Button
                    variant="ghost"
                    className="w-full justify-start gap-3 text-slate-400 hover:bg-white/5 hover:text-white px-3 py-2.5 text-sm font-medium"
                >
                    <Book className="h-4 w-4 shrink-0" />
                    Knowledge Base
                </Button>
            </SheetTrigger>

            <SheetContent className="w-[400px] bg-[#0f172a] border-border/40">
                <SheetHeader>
                    <SheetTitle className="text-white flex items-center gap-2">
                        <Book className="h-5 w-5 text-indigo-400" />
                        Knowledge Base
                    </SheetTitle>
                    <SheetDescription>
                        Upload PDF documents to enhance agent context.
                    </SheetDescription>
                </SheetHeader>

                <div className="mt-6 space-y-4">
                    {/* ── Drop zone ──────────────────────────────────────── */}
                    <div
                        onClick={handleClickUpload}
                        onDragOver={(e) => {
                            e.preventDefault();
                            setDragOver(true);
                        }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={handleDrop}
                        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors cursor-pointer ${dragOver
                                ? "border-indigo-400 bg-indigo-500/10"
                                : "border-border/40 bg-white/[0.02] hover:border-border/60"
                            }`}
                    >
                        {uploading ? (
                            <Loader2 className="h-8 w-8 text-indigo-400 animate-spin" />
                        ) : (
                            <>
                                <Upload className="h-8 w-8 text-muted-foreground/40 mb-2" />
                                <p className="text-sm text-muted-foreground">
                                    Drag &amp; drop PDFs here
                                </p>
                                <p className="text-xs text-muted-foreground/40 mt-1">
                                    or click to browse
                                </p>
                            </>
                        )}
                    </div>

                    {/* Hidden file input (controlled via ref) */}
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf"
                        multiple
                        className="hidden"
                        onChange={(e) => handleUpload(e.target.files)}
                    />

                    {/* ── Document list ──────────────────────────────────── */}
                    {loading ? (
                        <div className="space-y-2">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-14 w-full" />
                            ))}
                        </div>
                    ) : docs.length === 0 ? (
                        <p className="text-xs text-muted-foreground/40 text-center py-4">
                            No documents uploaded yet.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {docs.map((doc) => (
                                <div
                                    key={doc.doc_id}
                                    className="flex items-center gap-3 rounded-lg border border-border/30 bg-white/[0.02] px-3 py-2.5"
                                >
                                    <FileText className="h-4 w-4 text-indigo-400 shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">
                                            {doc.filename}
                                        </p>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            <span className="text-[10px] text-muted-foreground">
                                                {new Date(doc.uploaded_at).toLocaleDateString()}
                                            </span>
                                            <Badge
                                                variant="secondary"
                                                className="text-[10px] px-1 py-0"
                                            >
                                                {doc.chunk_count} chunks
                                            </Badge>
                                        </div>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDelete(doc.doc_id);
                                        }}
                                    >
                                        <Trash2 className="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </SheetContent>
        </Sheet>
    );
}
