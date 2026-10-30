import { Route, Routes, useLocation } from "react-router-dom"

import { AppSidebar } from "@/components/app-sidebar"
import { ScenarioSwitch } from "@/components/scenario-switch"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { Limits } from "@/pages/limits"
import { Region } from "@/pages/region"
import { Town, TownIndex } from "@/pages/town"

const TITLE: [RegExp, string][] = [[/^\/town/, "Town plan"], [/^\/limits/, "Data & limits"], [/^\//, "Region"]]

export default function App() {
  const { pathname } = useLocation()
  const title = TITLE.find(([r]) => r.test(pathname))![1]
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background/90 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/75 sm:px-4">
          <SidebarTrigger aria-label="Show or hide the menu" />
          <Separator orientation="vertical" className="mr-1 hidden data-[orientation=vertical]:h-4 sm:block" />
          <h1 className="min-w-0 flex-1 truncate text-sm font-medium">{title}</h1>
          <ScenarioSwitch className="ml-auto" />
        </header>
        <main className="min-w-0 flex-1 p-3 pb-10 sm:p-5 lg:p-6">
          <Routes>
            <Route path="/" element={<Region />} />
            <Route path="/town" element={<TownIndex />} />
            <Route path="/town/:key" element={<Town />} />
            <Route path="/limits" element={<Limits />} />
          </Routes>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
