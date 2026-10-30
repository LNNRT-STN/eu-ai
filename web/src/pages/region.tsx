import { useMemo, useState } from "react"
import { ArrowLeft, ArrowRight, ChevronDown, Search } from "lucide-react"
import { Link, useSearchParams } from "react-router-dom"

import { Briefings } from "@/components/briefings"
import { Dot, SectionTitle, Source, StatusTag, Verdict } from "@/components/page"
import { boundsOf, FloodMap, Legend, type Bounds } from "@/components/flood-map"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { type Region as RegionData, type RegionTown, useFlood, useRegion } from "@/lib/api"
import { fmt, plural, STATUS } from "@/lib/flood"
import { cn } from "@/lib/utils"

const PAGE = 40

export function Region() {
  const { data, isError, error } = useRegion()
  const flood = useFlood(data?.scenario.variant)
  const [params, setParams] = useSearchParams()
  const sel = params.get("town")
  const select = (key: string | null) => setParams(key ? { town: key } : {}, { replace: false })

  const all = useMemo(() => (data ? regionBounds(data.towns) : null), [data])
  const town = data?.towns.find((t) => t.key === sel) ?? null
  const focus = useMemo(() => {
    if (town) return { id: town.key, bounds: boundsOf([[town.lon, town.lat]], 0, 0.12), maxZoom: 12.5 }
    return { id: "region", bounds: all ?? ([[4.6, 49.9], [7.4, 51.5]] as Bounds) }
  }, [town, all])

  if (isError) return <Verdict tone="calm" head="The data server is not answering.">{error.message}. Start it with <code>uvicorn api.main:app</code> and reload.</Verdict>
  if (!data) return <RegionSkeleton />

  const p = data.scenario.plan
  const rp = p ?? 100
  return (
    <div className="space-y-5">
      <Verdict tone={p ? "act" : "calm"} head={data.verdict.head}>
        {data.verdict.detail && <p>{data.verdict.detail}</p>}
        <Compare data={data} />
      </Verdict>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px] xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-2">
          <FloodMap
            label={`Map of the ${rp}-year flood zone and the towns in it`}
            className="h-[52vh] min-h-[360px] lg:h-[calc(100svh-15rem)] lg:min-h-[520px]"
            focus={focus}
            zone={flood.data}
            towns={data.towns
              .filter((t) => t.people > 0 || t.status !== "none")
              .map((t) => ({ ...t, note: `${STATUS[t.status].word} · about ${fmt(t.people)} people in the ${rp}-year zone` }))}
            selectedTown={sel}
            onTown={select}
          />
          <Legend
            items={[
              ...(p ? [{ color: "var(--evacuate)", label: "Evacuate" }, { color: "var(--watch)", label: "Watch: only the 500-year flood reaches it" }] : [{ color: "var(--normal)", label: "Town, size = people in the zone" }]),
              { color: "var(--water)", label: `${rp}-year flood zone (EFAS model)`, shape: "area" as const },
            ]}
          />
        </div>
        <aside className="min-w-0 rounded-xl border bg-card lg:h-[calc(100svh-15rem)] lg:min-h-[520px]">
          {town ? <TownPanel town={town} rp={rp} plan={p} onBack={() => select(null)} /> : <TownList towns={data.towns} plan={p} onPick={select} />}
        </aside>
      </div>

      <Accordion type="multiple" className="rounded-xl border bg-card px-4">
        <AccordionItem value="brief">
          <AccordionTrigger>
            <span>
              Briefings to send <span className="font-normal text-muted-foreground">· drafted for the mayor and fire brigade of every town to evacuate</span>
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <Briefings active={!!p} />
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="feed">
          <AccordionTrigger>
            <span>
              Reported by residents <span className="font-normal text-muted-foreground">· {data.feed.length ? `${data.feed.length} latest` : "none yet"}</span>
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <Feed feed={data.feed} />
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="how" className="border-b-0">
          <AccordionTrigger>How this is computed</AccordionTrigger>
          <AccordionContent>
            <ul className="max-w-[75ch] list-disc space-y-1.5 pl-4 text-sm leading-relaxed text-muted-foreground">
              <li><b className="font-medium text-foreground">Flood zones:</b> EFAS flood hazard maps (JRC), water deeper than 10 cm, every river at that return period at once. A planning map, not a forecast. No dikes in the model: towns behind the Meuse dikes (Liège, Venlo) are an upper bound.</li>
              <li><b className="font-medium text-foreground">Status:</b> a town with at least 10 residents in the planned zone evacuates; one reached only by the 500-year flood is on watch.</li>
              <li><b className="font-medium text-foreground">People:</b> GHS-POP 2020 spread over GHS-OBAT homes by floor volume. An order of magnitude, not a census.</li>
              <li><b className="font-medium text-foreground">Homes to clear:</b> homes in the zone with no news or asking for help, from residents' and crews' check-ins.</li>
              <li><b className="font-medium text-foreground">Briefings:</b> Claude writes the words, every figure comes from the tool. Nothing is sent from here.</li>
            </ul>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}

function regionBounds(towns: RegionTown[]): Bounds {
  const pts = towns.filter((t) => t.people > 0).map((t) => [t.lon, t.lat] as [number, number])
  return boundsOf(pts.length ? pts : towns.map((t) => [t.lon, t.lat]), 0.04)
}

function Compare({ data }: { data: RegionData }) {
  const [open, setOpen] = useState(false)
  const on = data.scenario.plan
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="pt-1">
      <CollapsibleTrigger asChild>
        <Button variant="link" size="sm" className="h-auto px-0 text-foreground">
          Compare the 10-, 100- and 500-year floods
          <ChevronDown className={cn("transition-transform duration-200", open && "rotate-180")} />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2">
        <div className="overflow-x-auto rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Flood</TableHead>
                <TableHead className="text-right">Towns</TableHead>
                <TableHead className="text-right">People in the zone</TableHead>
                <TableHead className="text-right">Shelter on foot</TableHead>
                <TableHead className="text-right">No place within 10 km</TableHead>
                <TableHead className="text-right">Care sites in the water</TableHead>
                <TableHead className="text-right">Shelter sites lost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.compare.map((r) => (
                <TableRow key={r.rp} className={cn(r.rp === on ? "bg-evacuate/[0.06] font-medium text-foreground" : "")}>
                  <TableCell>{r.rp}-year{r.rp === on && <span className="ml-2 text-xs text-evacuate">planned</span>}</TableCell>
                  <TableCell className="text-right">{fmt(r.towns)}</TableCell>
                  <TableCell className="text-right">{fmt(r.people)}</TableCell>
                  <TableCell className="text-right">{fmt(r.walk)}</TableCell>
                  <TableCell className="text-right">{fmt(r.noPlace)}</TableCell>
                  <TableCell className="text-right">{fmt(r.care)}</TableCell>
                  <TableCell className="text-right">{fmt(r.sheltersLost)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="mt-2 text-xs">All ten study areas. Zones nest: a rarer flood adds people and takes shelter sites away.</p>
      </CollapsibleContent>
    </Collapsible>
  )
}

function TownList({ towns, plan, onPick }: { towns: RegionTown[]; plan: number | null; onPick: (k: string) => void }) {
  const [q, setQ] = useState("")
  const [show, setShow] = useState<"act" | "watch">("act")
  const [n, setN] = useState(PAGE)
  const ev = towns.filter((t) => t.status === "evacuate" || t.status === "warn")
  const wt = towns.filter((t) => t.status === "watch")
  const base = plan ? (show === "act" ? ev : wt) : towns.filter((t) => t.people >= 10)
  const rows = q ? base.filter((t) => `${t.name} ${t.region}`.toLowerCase().includes(q.toLowerCase())) : base

  return (
    <div className="flex h-full max-h-[70vh] flex-col lg:max-h-none">
      <div className="space-y-3 border-b p-4">
        <SectionTitle aside={plan ? "people in the zone, most first" : "100-year zone, most people first"}>{plan ? "Where to act" : "Towns in the water"}</SectionTitle>
        {plan && (
          <ToggleGroup type="single" variant="outline" size="sm" value={show} onValueChange={(v) => v && (setShow(v as "act" | "watch"), setN(PAGE))} className="w-full">
            <ToggleGroupItem value="act" className="flex-1 gap-1.5"><Dot color="var(--evacuate)" />Evacuate · {ev.length}</ToggleGroupItem>
            <ToggleGroupItem value="watch" disabled={!wt.length} className="flex-1 gap-1.5"><Dot color="var(--watch)" />Watch · {wt.length}</ToggleGroupItem>
          </ToggleGroup>
        )}
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => (setQ(e.target.value), setN(PAGE))} placeholder={`Search ${base.length} towns`} className="pl-8" aria-label="Search towns" />
        </div>
      </div>
      <ol className="min-h-0 flex-1 overflow-y-auto">
        {rows.slice(0, n).map((t) => (
          <li key={t.key} className="border-b last:border-b-0">
            <button onClick={() => onPick(t.key)} className="group flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none">
              <Dot color={STATUS[t.status].color} className="size-2.5" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{t.name}</span>
                <span className="block text-xs text-muted-foreground sm:truncate">
                  {t.region}
                  {plan && t.status !== "watch" && t.todo > 0 && <> · <span className="whitespace-nowrap">{fmt(t.todo)} homes to clear</span></>}
                </span>
              </span>
              <span className="w-24 shrink-0 text-right">
                <span className="block text-sm font-medium tabular">{fmt(t.people)}</span>
                {plan && t.safe > 0 ? (
                  <Progress value={(100 * t.safe) / t.homes} className="mt-1 h-1" aria-label={`${fmt(t.safe)} of ${fmt(t.homes)} homes have left`} />
                ) : (
                  <span className="block text-xs text-muted-foreground">people</span>
                )}
              </span>
            </button>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="p-6 text-sm text-muted-foreground">
            {q ? `No town matches “${q}”.` : show === "watch" ? "No town is on watch: the 500-year flood reaches no town beyond this one's zone." : "Every town is at normal."}
          </li>
        )}
        {rows.length > n && (
          <li className="p-3">
            <Button variant="ghost" size="sm" className="w-full" onClick={() => setN(n + PAGE * 3)}>
              Show {Math.min(rows.length - n, PAGE * 3)} more of {rows.length - n}
            </Button>
          </li>
        )}
      </ol>
    </div>
  )
}

function TownPanel({ town, rp, plan, onBack }: { town: RegionTown; rp: number; plan: number | null; onBack: () => void }) {
  const s = STATUS[town.status]
  const noNews = town.todo - town.help
  const next =
    town.status === "evacuate" ? `Clear ${plural(town.todo, "home")} now. Help requests first, then single-storey homes.`
      : town.status === "watch" ? "Not in this flood. A 500-year flood would reach it: keep its list ready."
        : plan ? "Normal. No action needed." : `In a ${rp}-year flood, about ${fmt(town.people)} residents would sit in the water.`
  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-4">
        <Button variant="ghost" size="sm" onClick={onBack} className="-ml-2 mb-2 text-muted-foreground">
          <ArrowLeft /> All towns
        </Button>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-xl font-semibold tracking-tight">{town.name}</h2>
            <p className="text-sm text-muted-foreground">{town.region}</p>
          </div>
          <span className="mt-1"><StatusTag color={s.color}>{s.word}</StatusTag></span>
        </div>
        <p className="mt-3 text-sm font-medium leading-snug">{next}</p>
      </div>
      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        {town.homes > 0 && (
          <div className="space-y-2">
            <SectionTitle aside={`${fmt(town.safe)} of ${fmt(town.homes)} left`}>Homes in the zone</SectionTitle>
            {town.safe > 0 && <Progress value={(100 * town.safe) / town.homes} className="h-1.5" aria-label="Share of homes that have left" />}
            <dl className="grid grid-cols-3 gap-2 text-sm">
              {[["Asked for help", town.help, "var(--evacuate)"], ["No news", noNews, "var(--next)"], ["Have left", town.safe, "var(--shelter)"]].map(([k, v, c]) => (
                <div key={k as string} className="rounded-lg bg-muted/50 px-3 py-2">
                  <dt className="flex items-center gap-1.5 text-xs text-muted-foreground"><Dot color={c as string} />{k}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular">{fmt(v as number)}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
        <div className="space-y-2">
          <SectionTitle>People in each flood zone</SectionTitle>
          <ul className="divide-y rounded-lg border text-sm">
            {([10, 100, 500] as const).map((r) => (
              <li key={r} className={cn("flex justify-between px-3 py-2", r === rp && "font-medium")}>
                <span>{r}-year{r === rp && <span className="ml-2 text-xs text-muted-foreground">{plan ? "planned" : "for planning"}</span>}</span>
                <span className="tabular">about {fmt(town.byRp[r])}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      {town.hasPlan && (
        <div className="border-t p-4">
          <Button asChild className="w-full">
            <Link to={`/town/${encodeURIComponent(town.key)}`}>Open the town plan <ArrowRight /></Link>
          </Button>
        </div>
      )}
    </div>
  )
}

function Feed({ feed }: { feed: RegionData["feed"] }) {
  if (!feed.length) return <Source>None yet. A resident who taps “I am safe” on the resident page shows up here within seconds.</Source>
  return (
    <ul className="divide-y rounded-lg border">
      {feed.map((r) => (
        <li key={r.id} className="flex items-center gap-3 px-3 py-2 text-sm">
          <StatusTag color={r.status === "safe" ? "var(--shelter)" : r.status === "needs help" ? "var(--evacuate)" : "var(--normal)"}>
            {r.status === "safe" ? "Safe" : r.status === "needs help" ? "Needs help" : "Report undone"}
          </StatusTag>
          <span className="min-w-0 flex-1 truncate">
            <b className="font-medium">{r.door}</b>, {r.town}
            {r.status === "safe" && <span className="text-muted-foreground"> · {plural(r.people, "person", "people")}{r.where && ` · ${r.where}`}</span>}
          </span>
        </li>
      ))}
    </ul>
  )
}

function RegionSkeleton() {
  return (
    <div className="space-y-5" aria-busy>
      <Skeleton className="h-20 rounded-xl" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Skeleton className="h-[520px] rounded-xl" />
        <Skeleton className="h-[520px] rounded-xl" />
      </div>
    </div>
  )
}
