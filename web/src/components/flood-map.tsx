import { useEffect, useRef, useState } from "react"
import * as maplibregl from "maplibre-gl"
import { type GeoJSONSource, type LngLatBoundsLike, type MapLayerMouseEvent } from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"
import type { Feature, FeatureCollection, Point } from "geojson"

import { HEX } from "@/lib/flood"
import type { Status } from "@/lib/api"
import { cn } from "@/lib/utils"

const STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] }
const TIER_HEX = { 1: HEX.evacuate, 2: HEX.next, 3: HEX.normal } as const
const STATUS_HEX: Record<Status, string> = { evacuate: HEX.evacuate, warn: HEX.next, watch: HEX.watch, none: HEX.normal }

export type Bounds = [[number, number], [number, number]]
/** Where the camera goes. A new id flies there: out, across, back in. */
export interface Focus {
  id: string
  bounds: Bounds
  maxZoom?: number
}

export interface MapTown {
  key: string
  name: string
  status: Status
  people: number
  lon: number
  lat: number
  note?: string
}
export interface MapPoint {
  id: number
  lon: number
  lat: number
  title: string
  note?: string
  tier?: 1 | 2 | 3
  size?: number
}

interface Props {
  focus: Focus
  zone?: FeatureCollection
  roads?: FeatureCollection
  towns?: MapTown[]
  selectedTown?: string | null
  homes?: MapPoint[]
  shelters?: MapPoint[]
  selected?: { home: MapPoint; shelter?: MapPoint } | null
  onTown?: (key: string) => void
  onHome?: (id: number) => void
  onShelter?: (id: number) => void
  className?: string
  label: string
}

const fc = <P,>(rows: P[], pos: (r: P) => [number, number], props: (r: P) => Record<string, unknown>): FeatureCollection<Point> => ({
  type: "FeatureCollection",
  features: rows.map((r): Feature<Point> => ({ type: "Feature", geometry: { type: "Point", coordinates: pos(r) }, properties: props(r) })),
})

export function boundsOf(points: [number, number][], pad = 0.15, minSpan = 0.01): Bounds {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  let [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const w = Math.max(x1 - x0, minSpan)
  const h = Math.max(y1 - y0, minSpan / 1.55)
  ;[x0, x1, y0, y1] = [x0 - w * pad, x1 + w * pad, y0 - h * pad, y1 + h * pad]
  return [[x0, y0], [x1, y1]]
}

export function FloodMap({ focus, zone, roads, towns, selectedTown, homes, shelters, selected, onTown, onHome, onShelter, className, label }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const [ready, setReady] = useState(false)
  const handlers = useRef({ onTown, onHome, onShelter })
  handlers.current = { onTown, onHome, onShelter }
  const flown = useRef<string | null>(null)

  useEffect(() => {
    const m = new maplibregl.Map({
      container: box.current!,
      style: STYLE,
      bounds: focus.bounds as LngLatBoundsLike,
      fitBoundsOptions: { padding: 40, maxZoom: focus.maxZoom ?? 15 },
      attributionControl: { compact: true },
      cooperativeGestures: true,
      dragRotate: false,
      pitchWithRotate: false,
    })
    flown.current = focus.id
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right")
    m.touchZoomRotate.disableRotation()
    m.on("load", () => {
      const src = (id: string) => m.addSource(id, { type: "geojson", data: EMPTY })
      ;["zone", "roads", "towns", "homes", "shelters", "route", "pick"].forEach(src)
      m.addLayer({ id: "zone-fill", type: "fill", source: "zone", paint: { "fill-color": HEX.water, "fill-opacity": 0.26 } })
      m.addLayer({ id: "zone-line", type: "line", source: "zone", paint: { "line-color": HEX.water, "line-opacity": 0.55, "line-width": 0.8 } })
      const w = ["interpolate", ["linear"], ["get", "people"], 0, 2, 3000, 6] as unknown as number
      m.addLayer({ id: "roads-case", type: "line", source: "roads", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#fff", "line-width": ["+", w, 3] as unknown as number } })
      m.addLayer({
        id: "roads", type: "line", source: "roads", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-width": w, "line-color": ["match", ["get", "state"], "closed", HEX.evacuate, "wet", HEX.next, HEX.ink] as unknown as string, "line-opacity": ["match", ["get", "state"], "dry", 0.55, 1] as unknown as number },
      })
      m.addLayer({
        id: "towns", type: "circle", source: "towns",
        paint: {
          "circle-color": ["get", "color"] as unknown as string,
          "circle-radius": ["+", 3, ["*", 16, ["sqrt", ["get", "share"]]]] as unknown as number,
          "circle-opacity": ["case", ["get", "dim"], 0.25, 0.85] as unknown as number,
          "circle-stroke-color": ["case", ["get", "sel"], HEX.ink, "#fff"] as unknown as string,
          "circle-stroke-width": ["case", ["get", "sel"], 2.5, 1] as unknown as number,
        },
      })
      m.addLayer({
        id: "homes", type: "circle", source: "homes",
        paint: {
          "circle-color": ["get", "color"] as unknown as string,
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 1.6, 14, 3.5, 17, 6] as unknown as number,
          "circle-opacity": ["case", ["get", "dim"], 0.18, 0.9] as unknown as number,
          "circle-stroke-color": "#fff",
          "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 12, 0, 15, 0.8] as unknown as number,
        },
      })
      m.addLayer({
        id: "shelters", type: "circle", source: "shelters",
        paint: {
          "circle-color": HEX.shelter,
          "circle-radius": ["+", 4, ["*", 10, ["sqrt", ["get", "share"]]]] as unknown as number,
          "circle-opacity": ["case", ["get", "dim"], 0.25, 0.95] as unknown as number,
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 1.5,
        },
      })
      m.addLayer({ id: "route", type: "line", source: "route", layout: { "line-cap": "round" }, paint: { "line-color": HEX.ink, "line-width": 2.5, "line-dasharray": [1.5, 1.5] } })
      m.addLayer({
        id: "pick", type: "circle", source: "pick",
        paint: { "circle-color": ["get", "color"] as unknown as string, "circle-radius": 8, "circle-stroke-color": "#fff", "circle-stroke-width": 3 },
      })

      const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: "260px" })
      for (const id of ["towns", "homes", "shelters", "pick", "roads"]) {
        m.on("mousemove", id, (e: MapLayerMouseEvent) => {
          const p = e.features?.[0]?.properties
          if (!p?.title) return
          m.getCanvas().style.cursor = id === "roads" || id === "pick" ? "" : "pointer"
          const el = document.createElement("div")
          const b = document.createElement("b")
          b.textContent = p.title
          el.append(b)
          if (p.note) el.append(p.note)
          pop.setLngLat(e.lngLat).setDOMContent(el).addTo(m)
        })
        m.on("mouseleave", id, () => {
          m.getCanvas().style.cursor = ""
          pop.remove()
        })
      }
      m.on("click", "towns", (e: MapLayerMouseEvent) => handlers.current.onTown?.(String(e.features?.[0]?.properties?.key)))
      m.on("click", "homes", (e: MapLayerMouseEvent) => handlers.current.onHome?.(Number(e.features?.[0]?.properties?.id)))
      m.on("click", "shelters", (e: MapLayerMouseEvent) => handlers.current.onShelter?.(Number(e.features?.[0]?.properties?.id)))
      setReady(true)
    })
    map.current = m
    // the card changes size with the layout (sidebar, expanding rows, phone rotation): keep the canvas filling it
    const ro = new ResizeObserver(() => m.resize())
    ro.observe(box.current!)
    return () => (ro.disconnect(), m.remove())
    // the map is made once; data and focus flow in through the effects below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // while the camera flies, the old place's data stays drawn; the new place's lands with the camera
  const flying = useRef(0)
  const pending = useRef(new Map<string, FeatureCollection>())
  const draw = (id: string, data: FeatureCollection) => (map.current?.getSource(id) as GeoJSONSource | undefined)?.setData(data)
  const set = (id: string, data: FeatureCollection) => (flying.current ? pending.current.set(id, data) : draw(id, data))
  const land = () => {
    flying.current = 0
    pending.current.forEach((d, id) => draw(id, d))
    pending.current.clear()
  }

  // the signature move: a new place flies the camera out, across and back in (flyTo); reduced motion jumps.
  // No maxDuration: MapLibre jumps, not shortens, a flight that would run longer than it. Runs before the data
  // effects below, so the data of the same render waits for the landing.
  useEffect(() => {
    const m = map.current
    if (!m || !ready || flown.current === focus.id) return
    flown.current = focus.id
    const flight = ++flying.current
    m.fitBounds(focus.bounds as LngLatBoundsLike, { padding: 48, maxZoom: focus.maxZoom ?? 15, linear: false, curve: 1.42, speed: 1.6 })
    if (!m.isMoving()) land()
    else m.once("moveend", () => flight === flying.current && land())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, focus])

  useEffect(() => {
    if (ready) set("zone", zone ?? EMPTY)
  }, [ready, zone])

  useEffect(() => {
    if (!ready) return
    const roadTitle = (p: Record<string, unknown>) =>
      `${p.name || "Unnamed road"}${p.state === "closed" ? " · closed" : p.state === "wet" ? " · inside the zone" : ""}`
    set("roads", roads ? {
      ...roads,
      features: roads.features.map((f) => ({ ...f, properties: { ...f.properties, title: roadTitle(f.properties ?? {}), note: `Road out for about ${f.properties?.people} people` } })),
    } : EMPTY)
  }, [ready, roads])

  useEffect(() => {
    if (!ready) return
    const big = Math.max(1, ...(towns ?? []).map((t) => t.people))
    set("towns", fc(towns ?? [], (t) => [t.lon, t.lat], (t) => ({
      key: t.key, title: t.name, note: t.note, color: STATUS_HEX[t.status], share: t.people / big,
      sel: t.key === selectedTown, dim: !!selectedTown && t.key !== selectedTown,
    })))
  }, [ready, towns, selectedTown])

  useEffect(() => {
    if (!ready) return
    const dim = !!selected
    set("homes", fc(homes ?? [], (h) => [h.lon, h.lat], (h) => ({ id: h.id, title: h.title, note: h.note, color: TIER_HEX[h.tier ?? 3], dim })))
    const big = Math.max(1, ...(shelters ?? []).map((s) => s.size ?? 1))
    set("shelters", fc(shelters ?? [], (s) => [s.lon, s.lat], (s) => ({
      id: s.id, title: s.title, note: s.note, share: (s.size ?? 1) / big, dim: dim && s.id !== selected?.shelter?.id,
    })))
    const pick: (MapPoint & { color: string })[] = selected ? [{ ...selected.home, color: TIER_HEX[selected.home.tier ?? 3] }] : []
    if (selected?.shelter) pick.unshift({ ...selected.shelter, color: HEX.shelter })
    set("pick", fc(pick, (p) => [p.lon, p.lat], (p) => ({ title: p.title, note: p.note, color: p.color })))
    const s = selected?.shelter
    set("route", s ? {
      type: "FeatureCollection",
      features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[selected!.home.lon, selected!.home.lat], [s.lon, s.lat]] } }],
    } : EMPTY)
  }, [ready, homes, shelters, selected])


  return (
    <div className={cn("relative overflow-hidden rounded-xl border bg-muted", className)}>
      <div ref={box} className="size-full" role="region" aria-label={label} />
      {!ready && <div className="absolute inset-0 animate-pulse bg-muted" aria-hidden />}
    </div>
  )
}

export function Legend({ items, className }: { items: { color: string; label: string; shape?: "dot" | "area" | "line" }[]; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground", className)}>
      {items.map((i) => (
        <li key={i.label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn("inline-block shrink-0", i.shape === "area" ? "size-3 rounded-[3px] opacity-60" : i.shape === "line" ? "h-[3px] w-4 rounded-full" : "size-2.5 rounded-full")}
            style={{ background: i.color }}
          />
          {i.label}
        </li>
      ))}
    </ul>
  )
}
