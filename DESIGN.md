---
name: Flood desk
description: A calm, neutral crisis desk where colour appears only to say how wet a place is, and always next to its word.
colors:
  ink: "oklch(0.145 0 0)"
  ink-fill: "oklch(0.205 0 0)"
  paper: "oklch(1 0 0)"
  sidebar-paper: "oklch(0.985 0 0)"
  quiet-surface: "oklch(0.97 0 0)"
  quiet-text: "oklch(0.556 0 0)"
  hairline: "oklch(0.922 0 0)"
  focus-ring: "oklch(0.708 0 0)"
  evacuate: "#d01d21"
  next: "#dc6414"
  watch: "#bb7400"
  normal: "#808080"
  shelter: "#1d7d3e"
  shelter-far: "#8cc49c"
  water: "#4682cc"
typography:
  display:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.025em"
    fontFeature: "\"ss01\", \"cv11\""
  headline:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.375
    fontFeature: "\"ss01\", \"cv11\", \"tnum\""
  title:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.43
    fontFeature: "\"ss01\", \"cv11\""
  body:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.625
    fontFeature: "\"ss01\", \"cv11\""
  label:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.33
    fontFeature: "\"ss01\", \"cv11\""
  figure:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.4
    fontFeature: "\"ss01\", \"cv11\", \"tnum\""
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.ink-fill}"
    textColor: "{colors.paper}"
    typography: "{typography.title}"
    rounded: "{rounded.lg}"
    height: "32px"
    padding: "0 10px"
  button-outline:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    height: "32px"
    padding: "0 10px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    height: "28px"
    padding: "0 10px"
  scenario-segment:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    rounded: "{rounded.md}"
    height: "28px"
    padding: "0 12px"
  scenario-segment-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    height: "28px"
    padding: "0 12px"
  filter-segment-selected:
    backgroundColor: "{colors.quiet-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "28px"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    height: "32px"
    padding: "0 10px 0 32px"
  verdict-act:
    backgroundColor: "color-mix(in oklch, #d01d21 3.5%, white)"
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
    rounded: "{rounded.xl}"
    padding: "14px 20px"
  verdict-calm:
    backgroundColor: "color-mix(in oklch, oklch(0.97 0 0) 40%, white)"
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
    rounded: "{rounded.xl}"
    padding: "14px 20px"
  panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "16px"
  list-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "10px 16px"
  list-row-selected:
    backgroundColor: "color-mix(in oklch, oklch(0.97 0 0) 60%, white)"
    textColor: "{colors.ink}"
    padding: "10px 16px"
  status-tag:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    size: "8px dot + word"
---

# Design System: Flood desk

## Overview

**Creative North Star: "The Calm Desk"**

The React frontend (`web/`) is a crisis desk for a coordinator who has just received a flood warning and has ministers on the phone. It is built on shadcn's Nova style with a neutral base: white paper, near-black ink, oklch greys, hairline borders, a 10px base radius and Geist throughout. The world is deliberately colourless so that the few colours it does carry are unmistakable. Urgency comes from the facts in the sentence, not from the styling around it.

Every screen reads top-down in three levels and opens each level only when asked: one Verdict (the sentence that says whether to act and what the first action is), then a ranked list beside a map, then the detail behind rows, tabs and accordions, with "How this is computed" always last. Density is that of a working tool, not a dashboard: one figure per row, small labels, tabular numbers, no wall of metric tiles.

The signature move is the map camera. Every change of place (region to town, town to home, home to shelter) flies: out, across, back in. The data for the new place lands with the camera, never before it.

Scope: this file describes the React frontend in `web/` only (Region, Town plan, Data & limits). The older Streamlit app in `src/` keeps its own Apple-HIG styling for the surfaces it still serves (door-knock, resident, 2021 vs today) and is not governed by these tokens until those surfaces move.

**Key Characteristics:**
- Neutral shadcn Nova base; colour carries flood status only, always paired with a word.
- One Verdict per screen, then the list, then detail behind accordions.
- Flat, hairline-bordered panels at 14px corners; no card shadows.
- Geist Variable with stylistic set 01 and tabular figures for every number.
- One flood-scenario control for the whole desk, in the header.
- Every change of place on the map is a fly-to; reduced motion jumps.

## Colors

A greyscale desk with seven status colours that never appear without the word they stand for.

### Primary
- **Desk Ink** (ink-fill, oklch(0.205 0 0)) and **Ink** (ink, oklch(0.145 0 0)): the only "accent" the desk has. Primary buttons ("Open the town plan"), the selected scenario segment, the brand mark in the sidebar, the selected town's ring and the dashed home-to-shelter route on the map. Selection is always ink, never a status colour.

### Secondary (alert status)
- **Evacuate Red** (#d01d21): towns to evacuate, First-priority homes, care sites in the water, homes that asked for help, closed roads, "No place within 10 km". Also tints the act-tone Verdict (3.5% fill, 20% border) and marks the planned row in comparison tables, next to the word "planned".
- **Next Orange** (#dc6414): the Next tier of homes, towns at Warn, homes with no news, roads out that run through the water.
- **Watch Amber** (#bb7400): towns reached only by the 500-year flood.
- **Normal Grey** (#808080): Normal status, the Then tier, towns when no flood is switched on.

### Tertiary (place)
- **Dry Shelter Green** (#1d7d3e): candidate shelters that stay dry, people who walk to one, homes that have left, the arrow to a home's shelter.
- **Bus Shelter Green** (#8cc49c): people who reach a shelter only by bus or car (1.5 to 10 km). A lighter step of the same green, so the two read as one family.
- **EFAS Water Blue** (#4682cc): the modelled flood zone on the map (26% fill, 55% outline) and text selection (28% mix). Water, never a link or a button.

### Neutral
- **Paper** (paper, oklch(1 0 0)): page, cards, panels, popovers.
- **Sidebar Paper** (sidebar-paper, oklch(0.985 0 0)): the navigation rail, one step off white.
- **Quiet Surface** (quiet-surface, oklch(0.97 0 0)): hover and selected rows (at 50-60%), the calm Verdict (40%), stat cells, the map's loading shimmer, selected filter segments.
- **Quiet Text** (quiet-text, oklch(0.556 0 0)): secondary lines, hints, sources, table meta, legend labels.
- **Hairline** (hairline, oklch(0.922 0 0)): every border and divider, and the scrollbar thumb.
- **Focus Ring** (focus-ring, oklch(0.708 0 0)): the 2px focus outline at 2px offset.

Dark mode mirrors every token in `index.css` (status colours become lighter OKLCH steps of the same hues). MapLibre cannot read CSS variables, so `web/src/lib/flood.ts` `HEX` repeats the light-mode status hex for map paint; the two must change together.

### Named Rules
**The Word-Beside-Colour Rule.** No colour carries meaning alone. Every status dot sits beside its word (StatusTag, legend item, filter segment, list row with its status in the text); every map layer has a legend line; the stacked shelter bar carries an `aria-label` and a labelled key below it.

**The Status-Only Rule.** Colour is reserved for flood status and the two place colours (shelter, water). There is no brand colour. Decoration, links, selection and emphasis use ink and greys.

**The Neutral Selection Rule.** A selected control is filled with ink (the scenario switch) or quiet grey (filters, rows), never with evacuate red. Red means "evacuate", so it cannot also mean "you picked this".

## Typography

**Display Font:** Geist Variable (via @fontsource-variable/geist, with sans-serif)
**Body Font:** Geist Variable
**Label/Mono Font:** Geist Variable; no mono face in the build.

**Character:** One neutral grotesque at every size, with stylistic set 01 and cv11 on for the whole body and antialiased rendering. Hierarchy comes from weight (400 / 500 / 600) and from ink versus quiet grey, not from size jumps.

### Hierarchy
- **Display** (600, 1.5rem to 1.875rem from sm, tight tracking): page titles where the page has its own header (Data & limits); the town name in a panel uses the 1.25rem step.
- **Headline** (600, 1rem to 1.125rem from sm, leading 1.375, balanced wrap): the Verdict sentence, and section heads on Data & limits.
- **Title** (600, 0.875rem): SectionTitle above lists and stat groups; the header page title is the same size at 500.
- **Body** (400, 0.875rem, leading 1.625): Verdict detail, list rows, accordion content. Prose is capped at 65 to 75ch.
- **Label** (500, 0.75rem): status tags, legend items, row meta, sources, sidebar hints.
- **Figure** (600, 1.125rem, tabular): the counts in stat cells and the Verdict's shelter key.

### Named Rules
**The Tabular Figures Rule.** Every number sits on tabular figures: all table cells, plus anything carrying the `tabular` class (counts, km, ranks, scenario years). Numbers are grouped en-GB style ("12,340") and percentages carry a thin space before "%".

## Layout

An app shell: a collapsible left sidebar (icon rail when collapsed, a sheet on phones) and an inset main column. The header is sticky, 56px tall, with a hairline bottom border and a 75-90% paper backdrop blur; it holds the sidebar trigger, the page title and the flood scenario switch on the right. Main padding steps 12px / 20px / 24px (base / sm / lg), with 40px at the bottom.

Pages stack in 20px rhythm: Verdict, then a two-column body, then the accordion. From lg the body is the map (flexible, roughly 60%) beside a fixed list column (380 to 420px on Region, 420 to 460px on Town plan, wider from xl). The map fills the viewport height less the chrome (`100svh - 15rem` on Region, minimum 520px) and sticks on Town plan; below lg the map comes first at about half the viewport and the list follows. Columns are separated by a 16px gap. Data & limits is a reading page: one centred column capped at 1024px with 40px between sections.

Inside panels the rhythm is 16px padding, list rows at 10px by 16px, and 8 to 12px between a SectionTitle and its content. Long lists are paged ("Show 120 more of 340") rather than rendered whole.

### Named Rules
**The Verdict-List-Detail Rule.** Each screen opens with exactly one Verdict, then the list (with its map), then detail behind accordions or tabs. "How this is computed" is always the last accordion item. Nothing below the Verdict is open by default.

**The One Switch Rule.** The flood scenario switch lives in the header only: one control for the whole desk and every person on it. No page, panel or sidebar repeats it. The sidebar's foot holds the planning-tool disclaimer ("A planning tool, not an official warning...") and nothing else.

## Elevation & Depth

Flat. Panels, the Verdict, the map frame, tables and lists are separated by hairline borders and the quiet surface tint, never by shadows. Depth appears only where something floats over the map or the page: MapLibre popups (a soft ambient shadow, no tip) and the map's zoom control group (a faint 1px lift), plus the header's backdrop blur when content scrolls under it. Stock shadcn overlays (tooltips, toasts, popovers) keep their own preset elevation.

### Shadow Vocabulary
- **Map popup** (`box-shadow: 0 4px 16px rgb(0 0 0 / 0.12)`): hover popups over towns, homes, shelters and roads.
- **Map control** (`box-shadow: 0 1px 3px rgb(0 0 0 / 0.1)`): the zoom buttons.

### Named Rules
**The Flat Panel Rule.** In-page surfaces never cast shadows; a border and a tint are enough. Shadows belong only to things that float over the map.

## Shapes

Softly rounded rectangles from one 10px base radius. Outer containers (Verdict, map frame, list panel, accordion card, skeletons) use the 14px step; inner lists, tables, stat cells and drafts use 10px; buttons and inputs 10px; small segmented controls 8px. Status marks are circles (8px dots, 10px in town rows); legend swatches are a 10px dot, a 12px square at 3px radius for areas, and a 16 by 3px pill for lines. The shelter-reach bar is a 10px full pill.

## Components

### Buttons
Restrained and compact; shadcn Nova as shipped.
- **Shape:** gently rounded (10px), 32px default height, 28px small.
- **Primary:** ink fill, paper text, 14px medium; hover 80% ink. Used once per panel at most ("Open the town plan").
- **Outline / Ghost / Link:** outline for secondary actions (Copy), ghost for back and "Show more", link for in-sentence disclosure ("Compare the 10-, 100- and 500-year floods").
- **Hover / Focus:** hover to quiet surface; focus shows a 3px ring at 50% ring grey; press nudges 1px down.

### Chips (status tags and badges)
- **Style:** a StatusTag is not a pill: an 8px colour dot and a 12px medium word, inline. Badges (secondary or outline variant) are for neutral facts only: "Draft · not sent", "shown", data-limit tags.
- **State:** none; tags are read-only.

### Cards / Containers
- **Corner Style:** 14px outer, 10px inner.
- **Background:** paper; stat cells and calm Verdicts in quiet surface.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** one hairline.
- **Internal Padding:** 16px; list rows 10px by 16px; Verdict 14px by 16px (20px from sm).

### Inputs / Fields
- **Style:** hairline border, transparent fill, 10px radius, 32px tall, a leading search icon in quiet grey.
- **Focus:** ring-grey border with a 3px ring at 50%.
- **Error / Disabled:** stock shadcn (destructive border; 50% opacity).

### Navigation
The sidebar (sidebar paper) opens with the brand mark (a 32px ink square holding the waves icon), then three items, each a label with a one-line quiet hint below it: Region "Where to act", Town plan "Who leaves, where to", Data & limits "What the numbers can't say". The active item takes the sidebar accent tint. It collapses to an icon rail with tooltips, and on phones it is a sheet that closes on navigation. The foot holds the planning-tool disclaimer in 12px quiet text, hidden in the icon rail.

### Flood scenario switch (signature)
A connected outline segmented control in the header: Normal / 10-year / 100-year / 500-year ("10y" on phones), preceded from lg by a dot and the word "Flood" (evacuate dot when a flood is on, normal grey when not). The selected segment fills with ink and goes semibold. Each segment's tooltip gives its yearly chance; changing it raises a toast saying what changed on every screen. It is disabled while saving.

### Verdict (signature)
The one sentence a screen opens with. Two tones only: **act** (evacuate tint, alert-triangle icon in evacuate red) when a flood is planned and the place needs action, and **calm** (quiet surface, info icon in quiet grey) otherwise. Headline sentence first, then at most two lines of detail in quiet text, then optional in-place disclosure (a comparison table, the shelter-reach bar and its labelled key).

### Flood map (signature)
MapLibre on Carto Positron (grey basemap), framed as a 14px panel with a pulsing quiet placeholder until it loads. Layers: the EFAS zone in water blue; towns as status-coloured circles sized by the square root of their share of people, white 1px stroke, ink 2.5px ring when selected, others dimmed to 25%; homes as tier-coloured dots growing with zoom; shelters in dry green sized by people; roads out in ink, next orange when wet, evacuate red when closed, on a white casing; the picked home-to-shelter link as a dashed ink line. Hover popups give a bold title and one line of note in the page's own type. Cooperative gestures, no rotation.

**Camera:** every change of place is a fly-to: `fitBounds` with `linear: false`, `curve: 1.42`, `speed: 1.6`, padding 48, and no `maxDuration` (MapLibre jumps rather than shortens a flight that would exceed it). Data for the new place waits until the camera lands; the old place stays drawn in flight. Under `prefers-reduced-motion` MapLibre's own check turns the flight into a jump, so no flight may be marked `essential`.

### Lists with progress
Ranked rows: status dot, name in 14px medium, one quiet meta line, a tabular figure on the right. A 4px progress bar replaces the "people" caption only once at least one home has left; before that there is no bar.

## Do's and Don'ts

### Do:
- **Do** pair every status colour with its word: a dot plus "Evacuate", a legend line for every map layer.
- **Do** fill a selected control with ink (#171717 on the map, `foreground` in CSS) or the quiet surface tint.
- **Do** open every screen with one Verdict, follow it with the list and map, and put detail in accordions with "How this is computed" last.
- **Do** fly the camera on every change of place (`linear: false`, curve 1.42, speed 1.6, no `maxDuration`) and swap the data on landing.
- **Do** set numbers in tabular figures and format them en-GB.
- **Do** keep the light-mode status hex in `index.css` and `lib/flood.ts` `HEX` identical.
- **Do** keep panels flat: a hairline border and a 14px corner.

### Don't:
- **Don't** use evacuate red (or any status colour) to show selection, focus, links or emphasis.
- **Don't** let a colour carry meaning alone, on the map or off it.
- **Don't** add a second flood scenario control anywhere: the header holds the only one.
- **Don't** put anything but the planning-tool disclaimer in the sidebar foot.
- **Don't** show a progress bar before there is progress.
- **Don't** pass `maxDuration` or `essential: true` to a camera move, and don't draw the new place's data before the camera lands.
- **Don't** add shadows to in-page panels or rebuild the Streamlit wall of metric tiles, tabs and captions all open at once.
