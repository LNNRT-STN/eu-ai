import type { ReactNode } from "react"
import { AlertTriangle, Info } from "lucide-react"

import { cn } from "@/lib/utils"

/** The one sentence a screen opens with, then its next step. Tone carries colour; the words carry the meaning. */
export function Verdict({ tone, head, children, className }: { tone: "act" | "calm"; head: ReactNode; children?: ReactNode; className?: string }) {
  const Icon = tone === "act" ? AlertTriangle : Info
  return (
    <section
      className={cn(
        "flex gap-3 rounded-xl border px-4 py-3.5 sm:px-5",
        tone === "act" ? "border-evacuate/20 bg-evacuate/[0.035]" : "bg-muted/40",
        className
      )}
    >
      <Icon className={cn("mt-0.5 size-5 shrink-0", tone === "act" ? "text-evacuate" : "text-muted-foreground")} aria-hidden />
      <div className="min-w-0 space-y-1">
        <h2 className="text-base font-semibold leading-snug text-balance tabular sm:text-lg">{head}</h2>
        {children && <div className="max-w-[75ch] text-sm leading-relaxed text-muted-foreground">{children}</div>}
      </div>
    </section>
  )
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h3 className="text-sm font-semibold">{children}</h3>
      {aside && <div className="text-xs text-muted-foreground">{aside}</div>}
    </div>
  )
}

export function Dot({ color, className }: { color: string; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 shrink-0 rounded-full", className)} style={{ background: color }} />
}

/** Status word with its colour dot: colour never carries meaning alone. */
export function StatusTag({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <Dot color={color} />
      {children}
    </span>
  )
}

export function Source({ children }: { children: ReactNode }) {
  return <p className="text-xs leading-relaxed text-muted-foreground">{children}</p>
}
