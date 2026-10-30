import type { RP, Status } from "@/lib/api"

/** Shared vocabulary: status words and their colours (CSS variables from index.css), numbers, flood names. */

export const STATUS: Record<Status, { word: string; color: string }> = {
  evacuate: { word: "Evacuate", color: "var(--evacuate)" },
  warn: { word: "Warn", color: "var(--next)" },
  watch: { word: "Watch", color: "var(--watch)" },
  none: { word: "Normal", color: "var(--normal)" },
}

export const TIER: Record<1 | 2 | 3, { word: string; color: string; why: string }> = {
  1: { word: "First", color: "var(--evacuate)", why: "Care sites, and homes in the 10-year zone with no upper floor" },
  2: { word: "Next", color: "var(--next)", why: "Homes in the 10-year zone, or with no upper floor" },
  3: { word: "Then", color: "var(--normal)", why: "The rest of the zone" },
}

export const CHANCE: Record<RP, string> = { 10: "10 % chance in any year", 100: "1 % chance in any year", 500: "0.2 % chance in any year" }

export const COUNTRY = { BE: "Belgium", NL: "the Netherlands", DE: "Germany" } as const

const nf = new Intl.NumberFormat("en-GB")
export const fmt = (n: number | null | undefined) => (n == null ? "–" : nf.format(Math.round(n)))
export const pct = (x: number) => `${Math.round(x * 100)} %`
export const plural = (n: number, one: string, many = `${one}s`) => `${fmt(n)} ${n === 1 ? one : many}`

/** The same colours as hex, for MapLibre paint (index.css holds them as tokens). */
export const HEX = {
  evacuate: "#d01d21",
  watch: "#bb7400",
  normal: "#808080",
  next: "#dc6414",
  shelter: "#1d7d3e",
  water: "#4682cc",
  ink: "#171717",
} as const
