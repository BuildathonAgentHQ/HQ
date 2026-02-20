import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, FileWarning } from "lucide-react";

export default function CoveragePage() {
    return (
        <div className="flex h-full flex-col gap-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                    <Shield className="h-8 w-8 text-emerald-400" />
                    Coverage Map
                </h1>
                <p className="text-muted-foreground">
                    Directory-level breakdown of test validation and edge-case protection.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                <Card className="bg-white/5 border-white/10 col-span-full md:col-span-2 lg:col-span-3 min-h-[400px] flex items-center justify-center">
                    <CardContent className="flex flex-col items-center gap-4 text-center p-12">
                        <FileWarning className="h-16 w-16 text-muted-foreground/30 mb-4" />
                        <CardTitle className="text-xl">Coverage Map Pending</CardTitle>
                        <CardDescription className="max-w-md">
                            The Coverage Map provides a visual treemap of your repository,
                            highlighting modules with low test coverage so you can autonomously
                            dispatch the test-writer agent.
                        </CardDescription>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
