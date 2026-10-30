import type { ReactNode } from "react"

import { SectionTitle, Source } from "@/components/page"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useLimits } from "@/lib/api"
import { CHANCE, fmt, pct } from "@/lib/flood"

type Row = [title: string, tag: string | null, detail: ReactNode]

const REPO = "https://github.com/LNNRT-STN/eu-ai/blob/main"

const SOURCES: Row[] = [
  ["Flood zones: EFAS flood hazard maps", "challenge data", "Copernicus EMS European Flood Awareness System, Joint Research Centre: the 10-, 100- and 500-year river flood maps, water deeper than 0.1 m. The desk switches them on; the plan follows the rarest one on."],
  ["Buildings", "challenge data", "GHS-OBAT 2020, with height for floor volume and single-storey homes."],
  ["Residents", "challenge data", "GHS-POP 2020, ~1 km cells, spread over each cell's homes by floor volume; 2025 is a projection."],
  ["Municipalities", "public source", "Eurostat GISCO LAU 2021 (© EuroGeographics)."],
  ["Shelter candidates, hospitals, care homes, schools", "public source", "OpenStreetMap (ODbL), Geofabrik extract of 29 Oct 2026. A shelter counts for a return period only when it is dry in that zone."],
  ["Roads and addresses", "public source", "OpenStreetMap: the road network for routes out and closures, street addresses for homes and shelters."],
  ["River and rain outlook", "public source, live", "Open-Meteo: GloFAS v4, forecast models, ERA5."],
]

export function Limits() {
  const { data: d } = useLimits()
  const limits: Row[] = [
    ["No dikes or flood walls in the model", null, "EFAS floods the land behind defences as if they were not there. Along the Meuse at Liège and Venlo the zones and the people in them are an upper bound."],
    ["Small rivers are missing", null, "EFAS models rivers with a catchment of at least 500 km². Small streams, such as the Urft at Kall, and rain running off slopes are not in the zones: a home outside them is not guaranteed safe."],
    ["A planning map, not one storm", null, "Each map puts every river at that return period at once; a real flood hits some valleys, not all. It is not a forecast and not an official warning."],
    ["The Vesdre is counted in the Liège area", null, `The two study boxes overlap: ${d ? fmt(d.vesdreTwice) : "some"} buildings of the Vesdre box sit inside the Liège box and are counted there, once. The Vesdre's own rows show no buildings.`],
    ["Residents are an order of magnitude", null, "GHS-POP cells spread over each cell's homes by floor volume. Inside the zone is not the same as damaged. No age data."],
    ["Shelters are candidates, not official", null, "OSM schools, sports halls and civic buildings with at least 200 m² of floor, dry in the zone of each return period. Capacity is floor area × usable share ÷ m² per person. Sites above 20,000 m² (merged campuses, race circuits) count as 20,000 m². None is an official shelter."],
    ["Walking reach is a straight line", null, "1.5 km (1 and 2.5 km in the low and high cases). It understates walks in steep valleys and ignores flooded roads and bridges. People who cannot walk need transport."],
    ["Care sites count from 5 % in the water", null, "OSM hospitals, care homes and schools; only sites with at least 5 % of their area in the zone count."],
    ["The outlook is a heads-up, not a warning", null, "GloFAS (~5 km) handles the Meuse well, small valleys poorly. Official warnings: SPW, Rijkswaterstaat, German state flood centres."],
  ]

  return (
    <div className="mx-auto max-w-5xl space-y-10">
      <header className="space-y-1.5">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Data & limits</h2>
        <p className="max-w-[65ch] text-muted-foreground">Where every number on this desk comes from, and what it cannot tell you. Open a row for the detail.</p>
      </header>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">The flood scenario</h2>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <List title="Sources" rows={SOURCES} />
            <Source>Challenge data: the files the European AI Challenge provided. Public source: open data anyone can download.</Source>
          </div>
          <List title="Limits" rows={limits} />
        </div>
        <div className="space-y-2">
          <SectionTitle aside="all ten study areas; the zones nest">What each flood covers</SectionTitle>
          {d ? (
            <div className="overflow-x-auto rounded-xl border">
              <Table>
                <TableHeader><TableRow><TableHead>Flood</TableHead><TableHead className="text-right">Buildings</TableHead><TableHead className="text-right">Residents</TableHead><TableHead className="text-right">Water, km²</TableHead><TableHead className="text-right">No shelter on foot</TableHead><TableHead className="text-right">Place by bus</TableHead></TableRow></TableHeader>
                <TableBody>
                  {d.floods.map((f) => (
                    <TableRow key={f.rp}>
                      <TableCell>{f.rp}-year <span className="ml-1 text-xs text-muted-foreground">{CHANCE[f.rp]}</span></TableCell>
                      <TableCell className="text-right">{fmt(f.buildings)}</TableCell>
                      <TableCell className="text-right">≈ {fmt(f.people)}</TableCell>
                      <TableCell className="text-right">{fmt(f.km2)}</TableCell>
                      <TableCell className="text-right">≈ {fmt(f.noWalk)}</TableCell>
                      <TableCell className="text-right">≈ {fmt(f.busCovered)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : <Skeleton className="h-40 rounded-xl" />}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">July 2021</h2>
          <p className="text-sm text-muted-foreground">The satellite record behind the “2021 vs today” page, and how the model compares with it.</p>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <List title="How we checked the numbers" rows={d ? [
            ["Ahr", "lower than official, as expected", `${fmt(d.checks.ahr)} buildings in the satellite water (all passes; ${fmt(d.checks.ahrFirst)} with the first pass). Official: ${d.checks.official.ahr[0]} (${d.checks.official.ahr[1]}).`],
            ["Wallonia", "the satellite misses most", `${fmt(d.checks.wallonia)} buildings in the satellite water. Official: ${d.checks.official.wallonia[0]} (${d.checks.official.wallonia[1]}).`],
            ["Venlo", "not comparable", `${fmt(d.checks.venlo)} residents in the satellite water. Official: ${d.checks.official.venlo[0]} (${d.checks.official.venlo[1]}).`],
          ] : []} />
          <List title="Limits of the 2021 record" rows={[
            ["2021 counts are a floor", null, "The radar map shows water at overpass time, not at the peak, and saw little in narrow built-up valleys."],
            ["The Vesdre is modelled, never added", null, "No satellite polygons in the valley: the EFAS 100-year zone stands in. Never added to observed 2021 totals."],
            ["Two flood maps", null, "“All satellite passes” is the headline; “first pass only” is a lower bound."],
          ]} />
        </div>
        <div className="space-y-2">
          <SectionTitle aside="buildings the satellite saw flooded that the zone also holds">How far the return periods match 2021</SectionTitle>
          {d ? (
            <div className="overflow-x-auto rounded-xl border">
              <Table>
                <TableHeader><TableRow><TableHead>Area</TableHead><TableHead className="text-right">Seen flooded</TableHead><TableHead className="text-right">10-year finds</TableHead><TableHead className="text-right">100-year</TableHead><TableHead className="text-right">500-year</TableHead></TableRow></TableHeader>
                <TableBody>
                  {d.validation.map((r) => (
                    <TableRow key={r.area}>
                      <TableCell>{r.area}</TableCell>
                      <TableCell className="text-right">{fmt(r.observed)}</TableCell>
                      <TableCell className="text-right">{pct(r.rp10)}</TableCell>
                      <TableCell className="text-right">{pct(r.rp100)}</TableCell>
                      <TableCell className="text-right">{pct(r.rp500)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : <Skeleton className="h-48 rounded-xl" />}
          <Source>In Liège the zone covers the whole city centre while the satellite saw little: a high share there says little.</Source>
        </div>
        {d && d.dq.warn.length > 0 && (
          <Accordion type="single" collapsible className="rounded-xl border px-4">
            <AccordionItem value="dq" className="border-b-0">
              <AccordionTrigger>Data-quality warnings <span className="font-normal text-muted-foreground">· {d.dq.warn.length} of {d.dq.total} checks</span></AccordionTrigger>
              <AccordionContent>
                <div className="overflow-x-auto rounded-lg border">
                  <Table>
                    <TableHeader><TableRow><TableHead>Area</TableHead><TableHead>Check</TableHead><TableHead className="text-right">Value</TableHead><TableHead className="text-right">Warn above</TableHead><TableHead>Likely cause</TableHead><TableHead>Who can fix</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {d.dq.warn.map((r, i) => (
                        <TableRow key={i}>
                          <TableCell>{r.area}</TableCell><TableCell className="min-w-48 whitespace-normal">{r.indicator}</TableCell>
                          <TableCell className="text-right">{r.value.toFixed(1)}</TableCell><TableCell className="text-right">{r.warn_above.toFixed(1)}</TableCell>
                          <TableCell className="min-w-56 whitespace-normal text-muted-foreground">{r.likely_cause}</TableCell><TableCell className="min-w-32 whitespace-normal text-muted-foreground">{r.who_can_fix}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        )}
      </section>

      <footer className="border-t pt-4">
        <Source>
          Every check, and every error the AI made and how it was caught: <a className="underline underline-offset-2 hover:text-foreground" href={`${REPO}/ai_log.md`} target="_blank" rel="noreferrer">ai_log.md</a>.
          Full method: <a className="underline underline-offset-2 hover:text-foreground" href={`${REPO}/docs/METHODOLOGY.md`} target="_blank" rel="noreferrer">docs/METHODOLOGY.md</a>.
          Code written with Claude (Claude Code), checked by the team.
        </Source>
      </footer>
    </div>
  )
}

function List({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="space-y-2">
      <SectionTitle>{title}</SectionTitle>
      {rows.length ? (
        <Accordion type="multiple" className="rounded-xl border bg-card px-4">
          {rows.map(([t, tag, detail], i) => (
            <AccordionItem key={t} value={t} className={i === rows.length - 1 ? "border-b-0" : ""}>
              <AccordionTrigger className="py-3">
                <span className="flex flex-wrap items-center gap-2">{t}{tag && <Badge variant="secondary" className="font-normal">{tag}</Badge>}</span>
              </AccordionTrigger>
              <AccordionContent className="max-w-[65ch] text-muted-foreground">{detail}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      ) : <Skeleton className="h-40 rounded-xl" />}
    </div>
  )
}
