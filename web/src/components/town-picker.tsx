import { useState } from "react"
import { Check, ChevronsUpDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { TownListItem } from "@/lib/api"
import { fmt } from "@/lib/flood"
import { cn } from "@/lib/utils"

/** The town name is the control: click it to search every town in the zone. */
export function TownPicker({ towns, value, onChange, rp }: { towns: TownListItem[]; value?: string; onChange: (key: string) => void; rp: number }) {
  const [open, setOpen] = useState(false)
  const t = towns.find((x) => x.key === value)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" role="combobox" aria-expanded={open} aria-label="Change town" className="-ml-3 h-auto max-w-full gap-2 px-3 py-1 text-2xl font-semibold tracking-tight sm:text-3xl">
          <span className="truncate">{t?.name ?? "Pick a town"}</span>
          <ChevronsUpDown className="size-5 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(92vw,380px)] p-0" align="start">
        <Command>
          <CommandInput placeholder={`Search ${towns.length} towns`} />
          <CommandList className="max-h-80">
            <CommandEmpty>No town in the {rp}-year zone by that name.</CommandEmpty>
            <CommandGroup heading={`Most people in the ${rp}-year zone first`}>
              {towns.map((x) => (
                <CommandItem
                  key={x.key}
                  value={`${x.label} ${x.region} ${x.key}`}
                  onSelect={() => {
                    onChange(x.key)
                    setOpen(false)
                  }}
                >
                  <Check className={cn("size-4", x.key === value ? "opacity-100" : "opacity-0")} />
                  <span className="min-w-0 flex-1 truncate">
                    {x.label}
                    <span className="ml-1.5 text-xs text-muted-foreground">{x.region}</span>
                  </span>
                  <span className="text-xs tabular text-muted-foreground">{fmt(x.people)}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
