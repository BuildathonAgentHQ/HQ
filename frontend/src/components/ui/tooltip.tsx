"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface TooltipProps {
    content: React.ReactNode
    children: React.ReactNode
    className?: string
}

export function Tooltip({ content, children, className }: TooltipProps) {
    return (
        <span className={cn("group relative inline-flex", className)}>
            {children}
            <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 rounded-md bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md border border-border/40 opacity-0 transition-opacity group-hover:opacity-100 whitespace-normal max-w-xs text-center">
                {content}
            </span>
        </span>
    )
}
