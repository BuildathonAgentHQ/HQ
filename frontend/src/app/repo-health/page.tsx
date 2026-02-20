import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HeartPulse, Activity } from "lucide-react";

export default function RepoHealthPage() {
    return (
        <div className="flex h-full flex-col gap-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                    <HeartPulse className="h-8 w-8 text-rose-400" />
                    Repo Health
                </h1>
                <p className="text-muted-foreground">
                    Long-term repository vitality indicators and structural integrity warnings.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                <Card className="bg-white/5 border-white/10 col-span-full md:col-span-2 lg:col-span-3 min-h-[400px] flex items-center justify-center">
                    <CardContent className="flex flex-col items-center gap-4 text-center p-12">
                        <Activity className="h-16 w-16 text-muted-foreground/30 mb-4" />
                        <CardTitle className="text-xl">Health Telemetry Pending</CardTitle>
                        <CardDescription className="max-w-md">
                            This dashboard aggregates cyclomatic complexity, dependency staleness,
                            and documentation drift to calculate an overarching health score for the codebase.
                        </CardDescription>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
