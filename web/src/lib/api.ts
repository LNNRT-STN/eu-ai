import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { FeatureCollection } from "geojson"

/** api/main.py: the same numbers as the Streamlit dashboard. */

export type RP = 10 | 100 | 500
export type Variant = "rp10" | "rp100" | "rp500"
export type Status = "evacuate" | "warn" | "watch" | "none"

export interface Scenario {
  rps: RP[]
  /** the rarest flood switched on; null = normal */
  plan: RP | null
  /** the plan's data variant, rp100 when normal (for planning) */
  variant: Variant
}

export interface TownListItem {
  key: string
  name: string
  label: string
  area: string
  region: string
  country: "BE" | "NL" | "DE"
  people: number
  buildings: number
  lon: number
  lat: number
}

export interface RegionTown {
  key: string
  name: string
  region: string
  status: Status
  people: number
  byRp: Record<RP, number>
  homes: number
  todo: number
  help: number
  safe: number
  lon: number
  lat: number
  hasPlan: boolean
}

export interface Region {
  scenario: Scenario
  verdict: { tone: "normal" | "evacuate"; head: string; detail: string }
  compare: {
    rp: RP
    towns: number
    people: number
    buildings: number
    walk: number
    noPlace: number
    care: number
    sheltersLost: number
  }[]
  towns: RegionTown[]
  feed: { id: number; door: string; town: string; status: string; people: number; where: string; when: string }[]
}

export interface Briefing {
  id: number
  kind: string
  recipient: string
  town: string
  t: string
  ready: boolean
  source: string | null
}

export interface Shelter {
  n: number
  name: string
  cat: string
  km: number
  people: number
  places: number
  shared: number
  lon: number
  lat: number
  address: string
}

export interface Town {
  key: string
  name: string
  label: string
  region: string
  country: "BE" | "NL" | "DE"
  modelledValley: boolean
  lon: number
  lat: number
  rp: RP
  people: number
  buildings: number
  walk: number
  ride: number
  left: number
  district: string
  firstAction: string
  rerouteWarning: boolean
  shelters: Shelter[]
  care: { name: string; type: string; fromRp: RP; lon: number; lat: number; goTo: string | null; goKm: number | null }[]
  schools: { name: string; fromRp: RP }[]
  out: null | {
    exitMin: number
    exitMedMin: number
    exitSlowMin: number
    routeMin: number
    routeMedMin: number
    reroute: number
    bridges: number
    busiestRoad: string
    busiestPeople: number
    busiestMode: "walk" | "bus"
  }
  across: { rp: RP; people: number; care: number; noPlace: number }[]
  message: { walkers: string[]; bus: string | null }
}

export interface Home {
  tier: 1 | 2 | 3
  care: boolean
  address: string
  why: string
  go: string
  goAddress: string | null
  goKm: number | null
  lon: number
  lat: number
  goLon: number | null
  goLat: number | null
}

export interface Limits {
  floods: { rp: RP; buildings: number; people: number; km2: number; busCovered: number; noWalk: number }[]
  vesdreTwice: number
  checks: {
    ahr: number
    ahrFirst: number
    wallonia: number
    venlo: number
    official: Record<"ahr" | "wallonia" | "venlo", [string, string]>
  }
  validation: { area: string; rp10: number; rp100: number; rp500: number; observed: number; inZone: number }[]
  dq: {
    total: number
    warn: { area: string; indicator: string; value: number; warn_above: number; likely_cause: string; who_can_fix: string }[]
  }
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(r.status === 404 ? "Not in this flood zone" : `The data server answered ${r.status}`)
  return r.json()
}

const q = (key: string) => encodeURIComponent(key)

export const useScenario = () => useQuery({ queryKey: ["scenario"], queryFn: () => get<Scenario>("/api/scenario") })

export function useSetScenario() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (rps: RP[]) => {
      const r = await fetch("/api/scenario", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rps }),
      })
      if (!r.ok) throw new Error("The scenario could not be switched")
      return (await r.json()) as Scenario
    },
    onSuccess: (s) => {
      qc.setQueryData(["scenario"], s)
      qc.invalidateQueries({ predicate: (x) => x.queryKey[0] !== "scenario" && x.queryKey[0] !== "flood" })
    },
  })
}

export const useRegion = () =>
  useQuery({ queryKey: ["region"], queryFn: () => get<Region>("/api/region"), refetchInterval: 5000 })

export const useTowns = (v?: Variant) =>
  useQuery({ queryKey: ["towns", v], queryFn: () => get<TownListItem[]>(`/api/towns?v=${v}`), enabled: !!v })

export const useFlood = (v?: Variant) =>
  useQuery({
    queryKey: ["flood", v],
    queryFn: () => get<FeatureCollection>(`/api/flood/${v}`),
    enabled: !!v,
    staleTime: Infinity,
  })

export const useTown = (key?: string, v?: Variant) =>
  useQuery({
    queryKey: ["town", key, v],
    queryFn: () => get<Town>(`/api/town?key=${q(key!)}&v=${v}`),
    enabled: !!key && !!v,
    // the last town stays on the map while the camera flies to the next
    placeholderData: keepPreviousData,
    retry: false,
  })

export const useHomes = (key?: string, v?: Variant) =>
  useQuery({
    queryKey: ["homes", key, v],
    queryFn: () => get<Home[]>(`/api/town/homes?key=${q(key!)}&v=${v}`),
    enabled: !!key && !!v,
    // the last town stays on the map while the camera flies to the next
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    retry: false,
  })

export const useTownMap = (key?: string, v?: Variant) =>
  useQuery({
    queryKey: ["townmap", key, v],
    queryFn: () => get<{ zone: FeatureCollection; roads: FeatureCollection }>(`/api/town/map?key=${q(key!)}&v=${v}`),
    enabled: !!key && !!v,
    // the last town stays on the map while the camera flies to the next
    placeholderData: keepPreviousData,
    retry: false,
  })

export const useBriefings = (enabled: boolean) =>
  useQuery({ queryKey: ["briefings"], queryFn: () => get<Briefing[]>("/api/briefings"), enabled, refetchInterval: 5000 })

export const useBriefing = (id?: number) =>
  useQuery({
    queryKey: ["briefing", id],
    queryFn: () => get<{ id: number; text: string | null; source: string | null }>(`/api/briefings/${id}`),
    enabled: id != null,
    refetchInterval: (x) => (x.state.data?.text ? false : 2000),
  })

export const useLimits = () => useQuery({ queryKey: ["limits"], queryFn: () => get<Limits>("/api/limits") })
