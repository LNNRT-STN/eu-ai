import { toast } from "sonner"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { type RP, useScenario, useSetScenario } from "@/lib/api"
import { CHANCE } from "@/lib/flood"
import { cn } from "@/lib/utils"

const OPTIONS = ["normal", "10", "100", "500"] as const

/** The shared scenario: one flood for every screen and every person on the desk. */
export function ScenarioSwitch({ className }: { className?: string }) {
  const { data } = useScenario()
  const set = useSetScenario()
  const value = data ? (data.plan ? String(data.plan) : "normal") : ""
  const on = !!data?.plan

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span className="hidden items-center gap-2 text-sm text-muted-foreground lg:inline-flex">
        <span
          aria-hidden
          className="size-2 rounded-full"
          style={{ background: on ? "var(--evacuate)" : "var(--normal)" }}
        />
        Flood
      </span>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        spacing={0}
        value={value}
        disabled={!data || set.isPending}
        aria-label="Flood scenario for the whole desk"
        onValueChange={(v) => {
          if (!v || v === value) return
          set.mutate(v === "normal" ? [] : [Number(v) as RP], {
            onSuccess: (s) =>
              toast(s.plan ? `Planning for a ${s.plan}-year flood` : "Back to normal", {
                description: s.plan
                  ? `${CHANCE[s.plan]}. Every screen now shows this flood; briefings are being drafted.`
                  : "Alerts, briefings and closed roads are cleared. Check-ins stay.",
              }),
            onError: (e) => toast.error(e.message, { description: "Nothing changed. Try again in a moment." }),
          })
        }}
      >
        {OPTIONS.map((o) => (
          <Tooltip key={o}>
            <TooltipTrigger asChild>
              <ToggleGroupItem
                value={o}
                className={cn(
                  "px-3 tabular aria-checked:font-semibold",
                  "aria-checked:bg-foreground aria-checked:text-background aria-checked:hover:bg-foreground/90 aria-checked:hover:text-background max-sm:px-2"
                )}
              >
                {o === "normal" ? "Normal" : <span>{o}<span className="max-sm:hidden">-year</span><span className="sm:hidden">y</span></span>}
              </ToggleGroupItem>
            </TooltipTrigger>
            <TooltipContent>
              {o === "normal" ? "No flood switched on" : `${CHANCE[Number(o) as RP]}. EFAS zone, all rivers at once, no dikes.`}
            </TooltipContent>
          </Tooltip>
        ))}
      </ToggleGroup>
    </div>
  )
}
