import { Info, Map, Waves } from "lucide-react"
import { NavLink, useLocation } from "react-router-dom"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

const NAV = [
  { to: "/", label: "Region", hint: "Where to act", icon: Map, match: (p: string) => p === "/" },
  { to: "/town", label: "Town plan", hint: "Who leaves, where to", icon: Waves, match: (p: string) => p.startsWith("/town") },
  { to: "/limits", label: "Data & limits", hint: "What the numbers can't say", icon: Info, match: (p: string) => p === "/limits" },
]

export function AppSidebar() {
  const { pathname } = useLocation()
  const { setOpenMobile } = useSidebar()
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <NavLink to="/" onClick={() => setOpenMobile(false)}>
                <span className="grid size-8 shrink-0 place-items-center rounded-md bg-foreground text-background">
                  <Waves className="size-4" />
                </span>
                <span className="grid leading-tight">
                  <span className="font-semibold">Flood desk</span>
                  <span className="text-xs text-muted-foreground">Meuse, Ahr, Erft, Rur</span>
                </span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.map((n) => (
                <SidebarMenuItem key={n.to}>
                  <SidebarMenuButton asChild isActive={n.match(pathname)} tooltip={n.label} className="h-auto py-2">
                    <NavLink to={n.to} onClick={() => setOpenMobile(false)}>
                      <n.icon />
                      <span className="grid leading-tight">
                        <span>{n.label}</span>
                        <span className="text-xs text-muted-foreground">{n.hint}</span>
                      </span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="group-data-[collapsible=icon]:hidden">
        <p className="px-2 pb-1 text-xs leading-relaxed text-muted-foreground">
          A planning tool, not an official warning. Warnings come from SPW, Rijkswaterstaat and the German state flood
          centres.
        </p>
      </SidebarFooter>
    </Sidebar>
  )
}
