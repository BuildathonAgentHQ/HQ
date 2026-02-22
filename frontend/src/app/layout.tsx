import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Toaster } from "@/components/ui/toaster";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
    title: "Agent HQ — Command Centre",
    description:
        "AI-powered command centre for orchestrating autonomous coding agents",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="dark">
            <head>
                <link
                    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body className="min-h-screen antialiased">
                <Providers>
                    <div className="flex min-h-screen">
                        {/* ── Fixed sidebar ─────────────────────────────────────── */}
                        <Sidebar />

                        {/* ── Main content ──────────────────────────────────────── */}
                        <main className="flex-1 ml-64 overflow-y-auto">
                            <div className="p-6 max-w-[1600px] mx-auto">{children}</div>
                        </main>
                    </div>
                    <Toaster />
                </Providers>
            </body>
        </html>
    );
}
