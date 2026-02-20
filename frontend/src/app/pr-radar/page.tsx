import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GitPullRequest, AlertCircle } from "lucide-react";

export default function PRRadarPage() {
    return (
        <div className="flex h-full flex-col gap-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                    <GitPullRequest className="h-8 w-8 text-indigo-400" />
                    PR Radar
                </h1>
                <p className="text-muted-foreground">
                    Control plane view of active Pull Requests and their AI-assessed risk scores.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                <Card className="bg-white/5 border-white/10 col-span-full md:col-span-2 lg:col-span-3 min-h-[400px] flex items-center justify-center">
                    <CardContent className="flex flex-col items-center gap-4 text-center p-12">
                        <AlertCircle className="h-16 w-16 text-muted-foreground/30 mb-4" />
                        <CardTitle className="text-xl">Radar Matrix Pending</CardTitle>
                        <CardDescription className="max-w-md">
                            The PR Radar will visualize incoming Pull Requests on a risk vs. impact matrix,
                            highlighting high-churn files and missing test coverage before human review.
                        </CardDescription>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
