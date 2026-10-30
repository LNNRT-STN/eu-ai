import { useMemo, useRef, useState } from "react"
import { ArrowRight, Check, Copy, Search, X } from "lucide-react"
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom"

import { boundsOf, FloodMap, Legend, type Focus, type MapPoint } from "@/components/flood-map"
import { Dot, SectionTitle, Source, StatusTag, Verdict } from "@/components/page"
import { TownPicker } from "@/components/town-picker"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { type Home, type Town as TownData, useHomes, useScenario, useTown, useTownMap, useTowns } from "@/lib/api"
import { CHANCE, COUNTRY, fmt, pct, plural, TIER } from "@/lib/flood"
import { CHAIN, type Lang, LOCAL_LANG, message, PREPARE } from "@/lib/town-text"
import { cn } from "@/lib/utils"

const PAGE = 60

/** /town with no town: the town with the most people in the planned zone. */
export function TownIndex() {
  const { data: s } = useScenario()
  const { data: towns } = useTowns(s?.variant)
  if (!towns) return <TownSkeleton />
  return <Navigate to={`/town/${encodeURIComponent(towns[0].key)}`} replace />
}

export function Town() {
  const key = decodeURIComponent(useParams().key ?? "")
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const { data: s } = useScenario()
  const v = s?.variant
  const towns = useTowns(v)
  const town = useTown(key, v)
  const homes = useHomes(key, v)
  const map = useTownMap(key, v)
  const t = town.data?.key === key ? town.data : undefined  // the previous town's, while this one loads
  const rp = s?.plan ?? 100

  const pick = params.get("home") != null ? Number(params.get("home")) : null
  const shelterPick = params.get("shelter") != null ? Number(params.get("shelter")) : null
  const setPick = (k: "home" | "shelter", i: number | null) => setParams(i == null ? {} : { [k]: String(i) }, { replace: true })

  const H = homes.isPlaceholderData ? undefined : homes.data
  // what the map draws: one snapshot of town, homes and zone, swapped only when all three are this town's,
  // so the camera's flight and the data change in the same render (the map lands them together)
  const shownRef = useRef({ t: town.data, H: homes.data, map: map.data })
  if (t && H && map.data && !map.isPlaceholderData) shownRef.current = { t, H, map: map.data }
  const shown = shownRef.current
  const home = pick != null && H?.[pick] ? H[pick] : null
  const shelterById = useMemo(() => new Map((t?.shelters ?? []).map((x) => [x.n, x])), [t])

  // the camera moves once per change of place, when that place's data is in: until then it holds the last view
  const held = useRef<Focus>({ id: "start", bounds: [[4.6, 49.9], [7.4, 51.5]] })
  const focus: Focus = useMemo(() => {
    let f: Focus | null = null
    if (home) {
      const pts: [number, number][] = [[home.lon, home.lat]]
      if (home.goLon != null && home.goLat != null) pts.push([home.goLon, home.goLat])
      f = { id: `${key}:home:${pick}`, bounds: boundsOf(pts, 0.35, 0.006), maxZoom: 16 }
    } else if (shelterPick != null && shelterById.get(shelterPick) && t) {
      const sh = shelterById.get(shelterPick)!
      f = { id: `${key}:shelter:${sh.n}`, bounds: boundsOf([[sh.lon, sh.lat], [t.lon, t.lat]], 0.3, 0.008), maxZoom: 15 }
    } else if (H?.length) f = { id: key, bounds: spread(H) }
    else if (t && homes.isSuccess && !homes.isPlaceholderData) f = { id: key, bounds: boundsOf([[t.lon, t.lat]], 0, 0.05) }
    if (f) held.current = f
    return held.current
  }, [home, pick, shelterPick, shelterById, H, t, key, homes.isSuccess, homes.isPlaceholderData])

  const homePts = useMemo<MapPoint[]>(
    () => (shown.H ?? []).map((h, i) => ({ id: i, lon: h.lon, lat: h.lat, tier: h.tier, title: h.address, note: `${TIER[h.tier].word} · ${h.why}` })),
    [shown.H]
  )
  const shelterPts = useMemo<MapPoint[]>(
    () => (shown.t?.shelters ?? []).map((x) => ({ id: x.n, lon: x.lon, lat: x.lat, size: x.people, title: `${x.n}. ${x.name}`, note: `${fmt(x.people)} people from ${shown.t!.name} · ${fmt(x.places)} places in all` })),
    [shown.t]
  )
  const selected = useMemo(() => {
    if (!home) return null
    const hp: MapPoint = { id: -1, lon: home.lon, lat: home.lat, tier: home.tier, title: home.address, note: `${TIER[home.tier].word} · ${home.why}` }
    const sp = home.goLon != null && home.goLat != null ? { id: -2, lon: home.goLon, lat: home.goLat, title: home.go, note: home.goAddress ?? "" } : undefined
    return { home: hp, shelter: sp }
  }, [home])

  if (town.isError) {
    return (
      <Verdict tone="calm" head={`${key.split("|")[1] ?? "This town"} has no residents in the ${rp}-year zone.`}>
        <p>Pick another town, or switch to a rarer flood.</p>
        {towns.data && <div className="pt-2"><TownPicker towns={towns.data} rp={rp} onChange={(k) => nav(`/town/${encodeURIComponent(k)}`)} /></div>}
      </Verdict>
    )
  }

  return (
    <div className="space-y-5">
      <header className="space-y-1">
        {towns.data ? (
          <TownPicker towns={towns.data} value={key} rp={rp} onChange={(k) => nav(`/town/${encodeURIComponent(k)}`)} />
        ) : (
          <Skeleton className="h-9 w-56" />
        )}
        <p className="text-sm text-muted-foreground">
          {t ? <>{t.region}, {COUNTRY[t.country]} · {s?.plan ? `Plan for a ${rp}-year flood (${CHANCE[rp]})` : `No flood is on: the town in a ${rp}-year flood, for planning`}</> : " "}
        </p>
      </header>

      {t ? <TownVerdict t={t} planned={!!s?.plan} /> : <Skeleton className="h-28 rounded-xl" />}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px] xl:grid-cols-[minmax(0,1fr)_460px]">
        <div className="space-y-2 lg:sticky lg:top-20 lg:self-start">
          <FloodMap
            label={`Map of ${t?.name ?? "the town"}: homes in the ${rp}-year zone and the dry shelters they go to`}
            className="h-[48vh] min-h-[340px] lg:h-[calc(100svh-9rem)] lg:max-h-[760px]"
            focus={focus}
            zone={shown.map?.zone}
            roads={shown.map?.roads}
            homes={homePts}
            shelters={shelterPts}
            selected={selected}
            onHome={(i) => setPick("home", i)}
            onShelter={(n) => setPick("shelter", n)}
          />
          <Legend
            items={[
              ...([1, 2, 3] as const).map((k) => ({ color: TIER[k].color, label: TIER[k].word })),
              { color: "var(--shelter)", label: "Dry shelter (candidate)" },
              { color: "var(--water)", label: `${rp}-year zone`, shape: "area" as const },
              { color: "var(--next)", label: "Road out, in the water", shape: "line" as const },
              { color: "var(--evacuate)", label: "Closed", shape: "line" as const },
              ...(home ? [{ color: "var(--foreground)", label: "Way to its shelter: straight line, not the road", shape: "line" as const }] : []),
            ]}
          />
        </div>

        <div className="min-w-0 rounded-xl border bg-card">
          <Tabs defaultValue="who" className="gap-0">
            <div className="border-b px-4 pt-4 pb-3">
              <TabsList className="w-full">
                <TabsTrigger value="who">Who leaves</TabsTrigger>
                <TabsTrigger value="where">Shelters{t ? ` · ${t.shelters.length}` : ""}</TabsTrigger>
                <TabsTrigger value="first">Care sites{t ? ` · ${t.care.length}` : ""}</TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="who">
              {H ? <WhoLeaves homes={H} pick={pick} onPick={(i) => setPick("home", i)} /> : <ListSkeleton />}
            </TabsContent>
            <TabsContent value="where">{t ? <Shelters t={t} pick={shelterPick} onPick={(n) => setPick("shelter", n)} /> : <ListSkeleton />}</TabsContent>
            <TabsContent value="first">{t ? <CareSites t={t} /> : <ListSkeleton />}</TabsContent>
          </Tabs>
        </div>
      </div>

      {t && <Details t={t} />}
    </div>
  )
}

/** Frame the town's homes without the stray ones at the edge (2nd to 98th percentile). */
function spread(H: Home[]) {
  const q = (xs: number[], p: number) => xs.sort((a, b) => a - b)[Math.floor(p * (xs.length - 1))]
  const xs = H.map((h) => h.lon)
  const ys = H.map((h) => h.lat)
  return boundsOf([[q([...xs], 0.02), q([...ys], 0.02)], [q([...xs], 0.98), q([...ys], 0.98)]], 0.18, 0.012)
}

function TownVerdict({ t, planned }: { t: TownData; planned: boolean }) {
  const urgent = planned && (t.left >= 5 || t.care.length > 0 || t.rerouteWarning)
  const total = Math.max(t.walk + t.ride + t.left, 1)
  const parts = [
    { k: "Walk to a shelter", sub: "within 1.5 km", n: t.walk, c: "var(--shelter)" },
    { k: "Need a bus or car", sub: "1.5 to 10 km", n: t.ride, c: "var(--shelter-far)" },
    { k: "No place within 10 km", sub: t.left >= 5 ? "ask the next town" : "everyone fits", n: t.left, c: "var(--evacuate)" },
  ]
  return (
    <Verdict tone={urgent ? "act" : "calm"} head={planned ? <>First action: {lowerFirst(t.firstAction)}</> : <>If this flood came, the first action would be to {lowerFirst(t.firstAction)}</>}>
      <p>
        About {fmt(t.people)} residents and {plural(t.buildings, "building")} sit in the {t.rp}-year zone; {plural(t.shelters.length, "dry shelter")} can take them.
        {t.rerouteWarning && t.out && <> {pct(t.out.reroute)} of routes to a shelter cross the water again: leave before the river rises.</>}
      </p>
      <div className="mt-3 space-y-2" role="img" aria-label={parts.map((p) => `${p.k}: about ${fmt(p.n)}`).join(", ")}>
        <div className="flex h-2.5 overflow-hidden rounded-full bg-muted">
          {parts.map((p) => p.n > 0 && <span key={p.k} style={{ width: `${(100 * p.n) / total}%`, background: p.c }} className="h-full first:rounded-l-full last:rounded-r-full" />)}
        </div>
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
          {parts.map((p) => (
            <div key={p.k} className="flex gap-2">
              <Dot color={p.c} className="mt-1.5" />
              <div>
                <dt className="text-sm"><span className="font-semibold text-foreground tabular">{fmt(p.n)}</span> {p.k.toLowerCase()}</dt>
                <dd className="text-xs">{p.sub}</dd>
              </div>
            </div>
          ))}
        </dl>
      </div>
    </Verdict>
  )
}

const lowerFirst = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)

function WhoLeaves({ homes, pick, onPick }: { homes: Home[]; pick: number | null; onPick: (i: number | null) => void }) {
  const [tier, setTier] = useState<"all" | "1" | "2" | "3">("all")
  const [q, setQ] = useState("")
  const [n, setN] = useState(PAGE)
  const counts = { 1: 0, 2: 0, 3: 0 }
  homes.forEach((h) => counts[h.tier]++)
  const rows = homes
    .map((h, i) => ({ h, i }))
    .filter(({ h }) => (tier === "all" || h.tier === Number(tier)) && (!q || `${h.address} ${h.go}`.toLowerCase().includes(q.toLowerCase())))
  const care = homes.filter((h) => h.care).length

  return (
    <div>
      <div className="space-y-3 border-b p-4">
        <p className="text-sm text-muted-foreground">
          {plural(homes.length - care, "home")}{care ? ` and ${plural(care, "care site")}` : ""}, in the order to evacuate them. Pick one to see where it goes.
        </p>
        <ToggleGroup type="single" variant="outline" size="sm" value={tier} onValueChange={(x) => x && (setTier(x as typeof tier), setN(PAGE))} className="w-full" aria-label="Priority">
          <ToggleGroupItem value="all" className="flex-1">All</ToggleGroupItem>
          {([1, 2, 3] as const).map((k) => (
            <ToggleGroupItem key={k} value={String(k)} className="flex-1 gap-1.5" title={TIER[k].why}>
              <Dot color={TIER[k].color} />{TIER[k].word} <span className="text-muted-foreground tabular">{fmt(counts[k])}</span>
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => (setQ(e.target.value), setN(PAGE))} placeholder="Street or shelter" className="pl-8" aria-label="Search addresses and shelters" />
        </div>
      </div>
      <ol className="max-h-[calc(100svh-22rem)] min-h-64 overflow-y-auto">
        {rows.slice(0, n).map(({ h, i }) => {
          const on = i === pick
          return (
            <li key={i} className={cn("border-b last:border-b-0", on && "bg-muted/60")}>
              <button onClick={() => onPick(on ? null : i)} aria-expanded={on} className="flex w-full items-start gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none">
                <span className="w-7 shrink-0 pt-0.5 text-right text-xs text-muted-foreground tabular">{i + 1}</span>
                <Dot color={TIER[h.tier].color} className="mt-1.5" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{h.address}</span>
                  <span className="block truncate text-xs text-muted-foreground">{h.why}</span>
                </span>
                {h.goKm != null && <span className="shrink-0 pt-0.5 text-xs text-muted-foreground tabular">{h.goKm.toFixed(1)} km</span>}
              </button>
              {on && (
                <div className="flex items-start gap-2 px-4 pb-3 pl-[3.75rem] text-sm">
                  <ArrowRight className="mt-0.5 size-4 shrink-0 text-shelter" />
                  <div className="min-w-0">
                    <p className="font-medium">{h.go}</p>
                    <p className="text-xs text-muted-foreground">
                      {[h.goAddress, h.goKm != null && `about ${h.goKm.toFixed(1)} km by road`].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <Button size="icon" variant="ghost" className="ml-auto size-7" onClick={() => onPick(null)} aria-label="Back to every home"><X /></Button>
                </div>
              )}
            </li>
          )
        })}
        {!rows.length && <li className="p-6 text-sm text-muted-foreground">No address matches “{q}”.</li>}
        {rows.length > n && (
          <li className="p-3">
            <Button variant="ghost" size="sm" className="w-full" onClick={() => setN(n + PAGE * 4)}>
              Show {fmt(Math.min(rows.length - n, PAGE * 4))} more of {fmt(rows.length - n)}
            </Button>
          </li>
        )}
      </ol>
      <div className="border-t px-4 py-3">
        <Source>Residents: GHS-POP spread over homes, an order of magnitude. No data on age, disability or who lives alone: add the municipality's own list.</Source>
      </div>
    </div>
  )
}

function Shelters({ t, pick, onPick }: { t: TownData; pick: number | null; onPick: (n: number | null) => void }) {
  if (!t.shelters.length) return <div className="p-4"><Verdict tone="act" head="No dry candidate shelter within 10 km.">Ask the neighbouring municipalities.</Verdict></div>
  return (
    <div>
      <p className="border-b p-4 text-sm text-muted-foreground">One plan that fits the most people within 10 km, biggest first. Candidate sites, not official shelters: confirm keys, staff and access with each owner.</p>
      <ol className="max-h-[calc(100svh-20rem)] min-h-64 overflow-y-auto">
        {t.shelters.map((x) => (
          <li key={x.n} className={cn("border-b last:border-b-0", x.n === pick && "bg-muted/60")}>
            <button onClick={() => onPick(x.n === pick ? null : x.n)} className="flex w-full items-start gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none">
              <span className="w-6 shrink-0 pt-0.5 text-right text-xs text-muted-foreground tabular">{x.n}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{x.name}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {x.address || "no street address"} · {x.km.toFixed(1)} km from the centre{x.shared ? ` · shared with ${plural(x.shared, "other town")}` : ""}
                </span>
              </span>
              <span className="shrink-0 text-right text-xs tabular">
                <span className="block text-sm font-medium">{fmt(x.people)}</span>
                <span className="text-muted-foreground">of {fmt(x.places)}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  )
}

function CareSites({ t }: { t: TownData }) {
  return (
    <div className="space-y-5 p-4">
      {t.care.length ? (
        <div className="space-y-2">
          <SectionTitle>Evacuate these first</SectionTitle>
          <ul className="divide-y rounded-lg border">
            {t.care.map((c) => (
              <li key={c.name} className="space-y-0.5 px-3 py-2.5 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{c.name}</span>
                  <StatusTag color="var(--evacuate)">from a {c.fromRp}-year flood</StatusTag>
                </div>
                <p className="text-xs text-muted-foreground">
                  {c.type[0].toUpperCase() + c.type.slice(1)} · {c.goTo ? `nearest dry site of the same kind: ${c.goTo} (${c.goKm?.toFixed(1)} km)` : "no dry site of the same kind in reach"}
                </p>
              </li>
            ))}
          </ul>
          <Source>Free beds at receiving sites are not in the data: confirm with each operator.</Source>
        </div>
      ) : (
        <p className="text-sm"><b className="font-medium">No hospital or care home in the {t.rp}-year zone here.</b> <span className="text-muted-foreground">Still check sites at the zone's edge.</span></p>
      )}
      {t.schools.length > 0 && (
        <div className="space-y-2">
          <SectionTitle>{plural(t.schools.length, "school")} in the zone: close them, never use them as shelters</SectionTitle>
          <ul className="divide-y rounded-lg border text-sm">
            {t.schools.map((x) => (
              <li key={x.name} className="flex justify-between gap-2 px-3 py-2"><span className="truncate">{x.name}</span><span className="shrink-0 text-xs text-muted-foreground">from a {x.fromRp}-year flood</span></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Details({ t }: { t: TownData }) {
  return (
    <Accordion type="multiple" className="rounded-xl border bg-card px-4">
      <AccordionItem value="out">
        <AccordionTrigger>
          <span>Getting out {t.out && <span className="font-normal text-muted-foreground">· 9 in 10 reach a shelter within {t.out.routeMin} min</span>}</span>
        </AccordionTrigger>
        <AccordionContent>
          {t.out ? (
            <div className="space-y-3 text-sm">
              <dl className="grid gap-3 sm:grid-cols-3">
                <Fact k="Leave the water on foot" v={`${t.out.exitMin} min`} sub={`9 in 10 residents; half within ${t.out.exitMedMin} min. ${t.out.exitSlowMin} min at an older person's pace.`} />
                <Fact k="Reach the shelter" v={`${t.out.routeMin} min`} sub={`On foot or by bus; half within ${t.out.routeMedMin} min. Buses at 30 km/h, no boarding: a minimum.`} />
                <Fact k="Routes back through the water" v={pct(t.out.reroute)} sub={`Over ${plural(t.out.bridges, "bridge")} inside the zone.`} />
              </dl>
              <p className="max-w-[75ch]">
                <b className="font-medium">Put a marshal on {/^[a-z]/.test(t.out.busiestRoad) ? `an unnamed ${t.out.busiestRoad} road` : t.out.busiestRoad}</b>
                <span className="text-muted-foreground">: the busiest road out, about {fmt(t.out.busiestPeople)} people {t.out.busiestMode === "walk" ? "on foot" : "by bus"}.</span>
              </p>
            </div>
          ) : (
            <Source>The road simulation covers towns with at least 300 residents in the zone.</Source>
          )}
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="msg">
        <AccordionTrigger><span>Warning message <span className="font-normal text-muted-foreground">· draft for {t.country === "BE" ? "BE-Alert" : t.country === "NL" ? "NL-Alert" : "cell broadcast"}</span></span></AccordionTrigger>
        <AccordionContent><MessageDraft t={t} /></AccordionContent>
      </AccordionItem>
      <AccordionItem value="who">
        <AccordionTrigger><span>Who gives the order in {COUNTRY[t.country]} <span className="font-normal text-muted-foreground">· also call {t.district}</span></span></AccordionTrigger>
        <AccordionContent>
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader><TableRow><TableHead>Role</TableHead><TableHead>Who</TableHead><TableHead>What to do</TableHead></TableRow></TableHeader>
              <TableBody>
                {CHAIN[t.country].map(([r, w, h]) => (
                  <TableRow key={r}><TableCell className="align-top font-medium">{r}</TableCell><TableCell className="min-w-56 align-top whitespace-normal">{w}</TableCell><TableCell className="min-w-48 align-top whitespace-normal text-muted-foreground">{h}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="mt-4 space-y-2">
            <SectionTitle>Before the flood season</SectionTitle>
            <ul className="space-y-1.5 text-sm">
              {PREPARE.map((p) => <li key={p} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-muted-foreground" />{p}</li>)}
            </ul>
          </div>
          <p className="mt-3"><Source>Team summary of national crisis rules, not challenge data. Check it against the municipality's emergency plan and fill in names and deputies there.</Source></p>
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="across">
        <AccordionTrigger>{t.name} as the flood gets rarer</AccordionTrigger>
        <AccordionContent>
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader><TableRow><TableHead>Flood</TableHead><TableHead className="text-right">Residents in the zone</TableHead><TableHead className="text-right">Care sites</TableHead><TableHead className="text-right">No place within 10 km</TableHead></TableRow></TableHeader>
              <TableBody>
                {t.across.map((r) => (
                  <TableRow key={r.rp} className={cn(r.rp === t.rp && "font-medium")}>
                    <TableCell>{r.rp}-year{r.rp === t.rp && <Badge variant="secondary" className="ml-2">shown</Badge>}</TableCell>
                    <TableCell className="text-right">{fmt(r.people)}</TableCell>
                    <TableCell className="text-right">{fmt(r.care)}</TableCell>
                    <TableCell className="text-right">{fmt(r.noPlace)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="how" className="border-b-0">
        <AccordionTrigger>How this is computed</AccordionTrigger>
        <AccordionContent>
          <ul className="max-w-[75ch] list-disc space-y-1.5 pl-4 text-sm leading-relaxed text-muted-foreground">
            <li>Zone: EFAS {t.rp}-year flood, all rivers at once, no dikes or flood walls{t.modelledValley ? "" : "; towns behind dikes are an upper bound"}. A planning map, not a forecast.</li>
            <li>Order: First = care sites, and homes in the 10-year zone with no upper floor (under about 4.5 m). Next = one of the two. Then = the rest.</li>
            <li>Shelters: OpenStreetMap schools, sports halls and civic buildings of 200 m² or more, outside the zone. Places = floor × 50 % ÷ 4 m². One max-flow plan fits the most people within 10 km.</li>
            <li>Distances: by road, about the straight line × 1.3. Road times from today's OpenStreetMap network, walking 4 km/h, buses 30 km/h.</li>
            <li>Message: team template, AI-assisted (ai_log.md 15), filled with this town's shelters. A native speaker approves it before use.</li>
          </ul>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}

function Fact({ k, v, sub }: { k: string; v: string; sub: string }) {
  return (
    <div className="rounded-lg bg-muted/50 px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{k}</dt>
      <dd className="text-xl font-semibold tabular">{v}</dd>
      <dd className="mt-1 text-xs leading-relaxed text-muted-foreground">{sub}</dd>
    </div>
  )
}

function MessageDraft({ t }: { t: TownData }) {
  const langs: Lang[] = [LOCAL_LANG[t.country], "English"]
  const [lang, setLang] = useState<Lang>(langs[0])
  const [line, setLine] = useState("")
  const [copied, setCopied] = useState(false)
  const text = message(lang, t.name, t.message.walkers, t.message.bus, line.trim())
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid min-w-64 flex-1 gap-1.5 text-sm">
          <span className="font-medium">Help line for people who cannot leave alone</span>
          <Input value={line} onChange={(e) => setLine(e.target.value)} placeholder="e.g. the municipal crisis number" />
        </label>
        <ToggleGroup type="single" variant="outline" size="sm" value={lang} onValueChange={(x) => x && setLang(x as Lang)} aria-label="Language">
          {langs.map((l) => <ToggleGroupItem key={l} value={l} className="px-3">{l}</ToggleGroupItem>)}
        </ToggleGroup>
      </div>
      <div className="relative rounded-lg border bg-muted/40 p-4 pr-14">
        <p className="max-w-[75ch] text-sm leading-relaxed">{text}</p>
        <Button size="icon" variant="ghost" className="absolute top-2 right-2" aria-label="Copy the message" onClick={() => navigator.clipboard.writeText(text).then(() => (setCopied(true), setTimeout(() => setCopied(false), 1600)))}>
          {copied ? <Check /> : <Copy />}
        </Button>
      </div>
      <Source>Draft, AI-assisted and checked by the team: a native speaker and the communication officer approve it before use. Walkers go to the largest shelters within 1.5 km, the bus to the largest one farther away.</Source>
    </div>
  )
}

function ListSkeleton() {
  return <div className="space-y-2 p-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
}

function TownSkeleton() {
  return (
    <div className="space-y-5" aria-busy>
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-28 rounded-xl" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]"><Skeleton className="h-[560px] rounded-xl" /><Skeleton className="h-[560px] rounded-xl" /></div>
    </div>
  )
}
