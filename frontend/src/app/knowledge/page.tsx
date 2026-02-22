"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/constants";
import { useToast } from "@/hooks/use-toast";

import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Book,
    Upload,
    Trash2,
    FileText,
    Loader2,
    Send,
    Bot,
    User,
} from "lucide-react";
import { RepoSelector } from "@/components/repo-selector";

interface KBDocument {
    id: string;
    doc_id?: string;
    filename: string;
    uploaded_at?: string;
    upload_time?: string;
    chunk_count: number;
    size_bytes?: number;
    status?: string;
}

interface ChatMessage {
    role: "user" | "assistant";
    content: string;
}

export default function KnowledgePage() {
    const [docs, setDocs] = useState<KBDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [chatLoading, setChatLoading] = useState(false);
    const [repoId, setRepoId] = useState<string | null>(null);
    const chatEndRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { toast } = useToast();

    const fetchDocs = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/knowledge/documents`);
            if (res.ok) {
                const data = await res.json();
                setDocs(data);
            }
        } catch {
            toast({ title: "Failed to load documents", variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [toast]);

    const handleUpload = async (files: FileList | null) => {
        if (!files || files.length === 0) return;
        setUploading(true);
        let successCount = 0;
        try {
            for (const file of Array.from(files)) {
                if (!file.name.toLowerCase().endsWith(".pdf")) {
                    toast({
                        title: "Invalid file",
                        description: "Only PDF files are supported",
                        variant: "destructive",
                    });
                    continue;
                }
                const formData = new FormData();
                formData.append("file", file);
                const res = await fetch(`${API_BASE_URL}/knowledge/upload`, {
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
                description: err instanceof Error ? err.message : "Network error",
                variant: "destructive",
            });
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const handleDelete = async (docId: string) => {
        try {
            await fetch(`${API_BASE_URL}/knowledge/documents/${docId}`, {
                method: "DELETE",
            });
            setDocs((prev) => prev.filter((d) => (d.doc_id ?? d.id) !== docId));
            toast({ title: "Document removed" });
        } catch {
            toast({ title: "Delete failed", variant: "destructive" });
        }
    };

    const handleSend = async () => {
        const text = input.trim();
        if (!text || chatLoading) return;
        if (docs.length === 0 && !repoId) {
            toast({
                title: "No context",
                description: "Upload PDFs and/or connect a repository to ask questions",
                variant: "destructive",
            });
            return;
        }

        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: text }]);
        setChatLoading(true);

        try {
            const res = await fetch(`${API_BASE_URL}/knowledge/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    top_k: 8,
                    repo_id: repoId || undefined,
                }),
            });
            const data = await res.json();
            if (res.ok) {
                setMessages((prev) => [
                    ...prev,
                    { role: "assistant", content: data.response || "No response." },
                ]);
            } else {
                throw new Error(data.detail || "Chat failed");
            }
        } catch (err) {
            toast({
                title: "Chat failed",
                description: err instanceof Error ? err.message : "Could not get response",
                variant: "destructive",
            });
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: "Sorry, I couldn't process your question. Please try again.",
                },
            ]);
        } finally {
            setChatLoading(false);
        }
    };

    useEffect(() => {
        fetchDocs();
    }, [fetchDocs]);

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, chatLoading]);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <Book className="h-7 w-7 text-indigo-500" />
                    Knowledge Base
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Upload PDFs and chat with your documents. Includes context from open and closed PRs of the linked repo.
                </p>
                <div className="mt-3 flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">PR context from:</span>
                    <RepoSelector
                        selectedRepoId={repoId}
                        onRepoChange={(id) => setRepoId(id)}
                    />
                    {!repoId && (
                        <span className="text-xs text-muted-foreground/60">
                            Connect a repo on Repositories page
                        </span>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* ── Left: Upload + Documents ───────────────────────────── */}
                <div className="lg:col-span-1 space-y-4">
                    <Card className="border-border/40 bg-card/60 backdrop-blur">
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Upload className="h-4 w-4" />
                                Upload PDFs
                            </CardTitle>
                            <CardDescription>
                                Drag & drop or click to add documents
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div
                                onClick={() => fileInputRef.current?.click()}
                                onDragOver={(e) => {
                                    e.preventDefault();
                                    setDragOver(true);
                                }}
                                onDragLeave={() => setDragOver(false)}
                                onDrop={(e) => {
                                    e.preventDefault();
                                    setDragOver(false);
                                    handleUpload(e.dataTransfer.files);
                                }}
                                className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors cursor-pointer ${
                                    dragOver
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
                                            Drag & drop PDFs here
                                        </p>
                                        <p className="text-xs text-muted-foreground/40 mt-1">
                                            or click to browse
                                        </p>
                                    </>
                                )}
                            </div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf"
                                multiple
                                className="hidden"
                                onChange={(e) => handleUpload(e.target.files)}
                            />
                        </CardContent>
                    </Card>

                    <Card className="border-border/40 bg-card/60 backdrop-blur">
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <FileText className="h-4 w-4" />
                                Documents
                            </CardTitle>
                            <CardDescription>
                                {docs.length} file(s) indexed
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {loading ? (
                                <div className="space-y-2">
                                    {[1, 2, 3].map((i) => (
                                        <Skeleton key={i} className="h-12 w-full" />
                                    ))}
                                </div>
                            ) : docs.length === 0 ? (
                                <p className="text-sm text-muted-foreground/60 text-center py-4">
                                    No documents yet. Upload PDFs above.
                                </p>
                            ) : (
                                <div className="space-y-2 max-h-[240px] overflow-y-auto">
                                    {docs.map((doc) => {
                                        const docId = doc.doc_id ?? doc.id;
                                        return (
                                            <div
                                                key={docId}
                                                className="flex items-center gap-3 rounded-lg border border-border/30 bg-white/[0.02] px-3 py-2.5"
                                            >
                                                <FileText className="h-4 w-4 text-indigo-400 shrink-0" />
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-medium truncate">
                                                        {doc.filename}
                                                    </p>
                                                    <Badge
                                                        variant="secondary"
                                                        className="text-[10px] mt-0.5"
                                                    >
                                                        {doc.chunk_count} chunks
                                                    </Badge>
                                                </div>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400"
                                                    onClick={() => handleDelete(docId)}
                                                >
                                                    <Trash2 className="h-3.5 w-3.5" />
                                                </Button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* ── Right: Chat ────────────────────────────────────────── */}
                <div className="lg:col-span-2">
                    <Card className="border-border/40 bg-card/60 backdrop-blur h-[600px] flex flex-col">
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Bot className="h-4 w-4 text-indigo-400" />
                                Chat with your documents
                            </CardTitle>
                            <CardDescription>
                                Ask questions about the content of your uploaded PDFs
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="flex-1 flex flex-col min-h-0 p-0">
                            {/* Messages */}
                            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                {messages.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-center py-12">
                                        <Bot className="h-12 w-12 text-muted-foreground/30 mb-3" />
                                        <p className="text-sm text-muted-foreground">
                                            Ask about your PDFs or PRs from the linked repo
                                        </p>
                                        <p className="text-xs text-muted-foreground/60 mt-1">
                                            e.g. &quot;Summarize PR #57&quot; or &quot;What are the main points in the document?&quot;
                                        </p>
                                    </div>
                                ) : (
                                    <>
                                        {messages.map((msg, i) => (
                                            <div
                                                key={i}
                                                className={`flex gap-3 ${
                                                    msg.role === "user"
                                                        ? "justify-end"
                                                        : "justify-start"
                                                }`}
                                            >
                                                {msg.role === "assistant" && (
                                                    <div className="h-8 w-8 rounded-lg bg-indigo-500/20 flex items-center justify-center shrink-0">
                                                        <Bot className="h-4 w-4 text-indigo-400" />
                                                    </div>
                                                )}
                                                <div
                                                    className={`max-w-[85%] rounded-lg px-4 py-2.5 ${
                                                        msg.role === "user"
                                                            ? "bg-indigo-500/20 text-indigo-100"
                                                            : "bg-white/[0.04] text-slate-200 border border-border/20"
                                                    }`}
                                                >
                                                    <p className="text-sm whitespace-pre-wrap">
                                                        {msg.content}
                                                    </p>
                                                </div>
                                                {msg.role === "user" && (
                                                    <div className="h-8 w-8 rounded-lg bg-slate-600/50 flex items-center justify-center shrink-0">
                                                        <User className="h-4 w-4 text-slate-400" />
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                        {chatLoading && (
                                            <div className="flex gap-3 justify-start">
                                                <div className="h-8 w-8 rounded-lg bg-indigo-500/20 flex items-center justify-center shrink-0">
                                                    <Loader2 className="h-4 w-4 text-indigo-400 animate-spin" />
                                                </div>
                                                <div className="rounded-lg px-4 py-2.5 bg-white/[0.04] border border-border/20">
                                                    <p className="text-sm text-muted-foreground">
                                                        Thinking...
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                        <div ref={chatEndRef} />
                                    </>
                                )}
                            </div>

                            {/* Input */}
                            <div className="p-4 border-t border-border/30">
                                <div className="flex gap-2">
                                    <Textarea
                                        placeholder="Ask about your PDFs or PRs from the linked repo..."
                                        value={input}
                                        onChange={(e) => setInput(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" && !e.shiftKey) {
                                                e.preventDefault();
                                                handleSend();
                                            }
                                        }}
                                        className="min-h-[44px] max-h-32 resize-none bg-white/[0.02] border-border/40"
                                        rows={2}
                                        disabled={chatLoading || (docs.length === 0 && !repoId)}
                                    />
                                    <Button
                                        onClick={handleSend}
                                        disabled={chatLoading || !input.trim() || (docs.length === 0 && !repoId)}
                                        className="shrink-0 h-[44px] px-4 bg-indigo-600 hover:bg-indigo-500"
                                    >
                                        {chatLoading ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <Send className="h-4 w-4" />
                                        )}
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
