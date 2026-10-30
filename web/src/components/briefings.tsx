import { useState } from "react"
import { Check, Copy } from "lucide-react"

import { Source } from "@/components/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useBriefing, useBriefings } from "@/lib/api"
import { cn } from "@/lib/utils"

/** Drafts for each town's mayor and fire brigade: the list beside the one open draft. Nothing is sent from here. */
export function Briefings({ active }: { active: boolean }) {
  const { data, isLoading } = useBriefings(active)
  const [pick, setPick] = useState<number | null>(null)
  const [q, setQ] = useState("")
  if (!active) return <Source>Switch on a flood above: the tool drafts one briefing for the mayor and one for the fire brigade of every town to evacuate.</Source>
  if (isLoading || !data) return <Skeleton className="h-64 rounded-lg" />
  if (!data.length) return <Source>The drafts are being queued. They appear here within a few seconds.</Source>
  const rows = q ? data.filter((b) => `${b.recipient} ${b.town}`.toLowerCase().includes(q.toLowerCase())) : data
  const id = pick ?? data[0].id

  return (
    <div className="grid gap-3 md:grid-cols-[280px_minmax(0,1fr)]">
      <div className="flex max-h-96 flex-col rounded-lg border">
        <div className="border-b p-2">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${data.length} drafts`} aria-label="Search briefings" className="h-8" />
        </div>
        <ul className="min-h-0 flex-1 overflow-y-auto py-1">
          {rows.map((b) => (
            <li key={b.id}>
              <button
                onClick={() => setPick(b.id)}
                aria-current={b.id === id}
                className={cn("w-full px-3 py-1.5 text-left text-sm transition-colors hover:bg-muted/60", b.id === id && "bg-muted font-medium")}
              >
                <span className="block truncate">{b.recipient}</span>
              </button>
            </li>
          ))}
          {!rows.length && <li className="px-3 py-2 text-sm text-muted-foreground">No draft matches.</li>}
        </ul>
      </div>
      <Draft id={id} recipient={data.find((b) => b.id === id)?.recipient ?? ""} />
    </div>
  )
}

function Draft({ id, recipient }: { id: number; recipient: string }) {
  const { data } = useBriefing(id)
  const [copied, setCopied] = useState(false)
  const text = data?.text
  return (
    <article className="flex max-h-96 min-w-0 flex-col rounded-lg border">
      <header className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
        <Badge variant="outline">Draft · not sent</Badge>
        <span className="min-w-0 flex-1 truncate text-sm"><span className="text-muted-foreground">To </span>{recipient}</span>
        <Button
          size="sm"
          variant="outline"
          disabled={!text}
          onClick={() => text && navigator.clipboard.writeText(text).then(() => (setCopied(true), setTimeout(() => setCopied(false), 1600)))}
        >
          {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
        </Button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {text ? (
          <div className="max-w-[70ch] space-y-2 text-sm leading-relaxed whitespace-pre-wrap">{text.replace(/\*\*/g, "")}</div>
        ) : (
          <div className="space-y-2" aria-busy aria-label="Drafting">
            <Skeleton className="h-4 w-3/4" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" />
          </div>
        )}
      </div>
      <footer className="border-t px-4 py-2 text-xs text-muted-foreground">
        {data?.source === "template" ? "Template: no AI was available." : "Words by Claude, numbers by the tool. Check before sending."}
      </footer>
    </article>
  )
}
