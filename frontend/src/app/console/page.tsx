import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Terminal } from "lucide-react";

export default function ConsolePage() {
    return (
        <div className="flex h-[calc(100vh-2rem)] flex-col gap-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                    <Terminal className="h-8 w-8 text-indigo-400" />
                    Agent Console
                </h1>
                <p className="text-muted-foreground">
                    Deep dive into active agent sub-processes and execute manual overrides.
                </p>
            </div>

            <Card className="flex-1 bg-white/5 border-white/10 flex items-center justify-center">
                <CardContent className="flex flex-col items-center gap-4 text-center p-12">
                    <Terminal className="h-16 w-16 text-muted-foreground/30 mb-4" />
                    <CardTitle className="text-xl">Interactive Console Coming Soon</CardTitle>
                    <CardDescription className="max-w-md">
                        This view will house the interactive pseudo-terminal allowing you to
                        directly interface with the active agent, inject Janitor Protocol fixes,
                        and monitor raw standard output.
                    </CardDescription>
                </CardContent>
            </Card>
        </div>
    );
}
