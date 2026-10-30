"""Static charts for the policy brief: the flood risk today, for a 10-, 100- and 500-year river flood (EFAS flood
hazard zones). python src/build_charts.py → outputs/charts/*.png (print, slides) and *.svg (editable). Reads only
outputs/rp/ (notebooks/pipeline.py with FLOOD=rp, then notebooks/rp_extras.py).

The zones are nested (10-year inside 100-year inside 500-year), so one area is drawn as three overlaid bars: the
most frequent flood darkest. The plan follows the 100-year flood (1 % chance in any year), as most flood plans do."""
from pathlib import Path

import matplotlib.lines
import matplotlib.patheffects
import matplotlib.patches
import matplotlib.pyplot as plt
import matplotlib.transforms
import pandas as pd

from chart_style import INK, MUTED, NAVY, NAVY_MID, NAVY_PALE, PAPER, RULE, WATER, heading, note, save as _save

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "outputs" / "rp"
OUT = ROOT / "outputs" / "charts"

RPS = ("rp10", "rp100", "rp500")
PLAN = "rp100"  # the flood the plan is made for
RP_NAME = {"rp10": "10-year flood", "rp100": "100-year flood", "rp500": "500-year flood"}
RP_ODDS = {"rp10": "10 % chance in any year", "rp100": "1 % chance in any year", "rp500": "0.2 % chance in any year"}
RP_COL = {"rp10": NAVY, "rp100": NAVY_MID, "rp500": NAVY_PALE}  # darkest = most frequent
SOURCE = "Source: EFAS flood hazard maps (JRC), GHS-OBAT, GHS-POP 2020 (challenge data); OpenStreetMap. Team analysis. " \
         "Zones are modelled with no dikes or\nflood walls, so towns behind them (Liège, Venlo) are an upper bound. " \
         "Residents are an order of magnitude."
LOCAL = {"Luik": "Liège", "Limburg": "Limbourg"}  # as anna.LOCAL: GISCO lists some Walloon communes in Dutch
LABEL_W = 2.4  # inches for the category labels, the same in every bar chart so they line up in the brief
W = 9


def frame(title, subtitle, notes=SOURCE, height=4.4, legend=False, right=0.88):
    """Message title, one-line subtitle, notes: each chart must stand alone in a brief. No axis: bars carry
    their own value labels. Spacing is set in inches so every chart has the same rhythm whatever its height."""
    fig, ax = plt.subplots(figsize=(W, height))
    top = 1 - (1.05 + 0.45 * legend) / height
    bottom = (0.4 + 0.19 * (notes.count("\n") + 1)) / height
    fig.subplots_adjust(left=LABEL_W / W, right=right, top=top, bottom=bottom)
    heading(fig, title, subtitle, height)
    note(fig, notes, height)
    return fig, ax


def legend(ax, handles):
    """One row above the plot, aligned with the bars."""
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.04), ncol=4, fontsize=9, handlelength=1.2,
              handleheight=1.0, borderaxespad=0, columnspacing=1.8)


def patch(label, color):
    # the pale step is near the paper colour: an outline keeps it visible
    return matplotlib.patches.Patch(facecolor=color, edgecolor=NAVY_MID if color == NAVY_PALE else color, label=label)


def save(fig, name):
    _save(fig, OUT, name)


def r100(v):
    return f"{round(v, -2):,.0f}" if v >= 100 else f"{v:,.0f}"


def nested(ax, labels, values, fmt=r100):
    """One row per label: the three zones overlaid (widest first, so the frequent flood sits on top), and the three
    numbers in columns right of the plot, the planned flood in bold. values: {rp: list}."""
    y = range(len(labels))
    for rp in reversed(RPS):
        ax.barh(y, values[rp], height=0.62, color=RP_COL[rp], linewidth=0.8,
                edgecolor=NAVY_MID if rp == "rp500" else RP_COL[rp])
    ax.invert_yaxis()
    ax.set_yticks(list(y), labels)
    tr = matplotlib.transforms.blended_transform_factory(ax.transAxes, ax.transData)
    inch = 1 / (ax.get_position().width * W)  # one inch in axes fractions: columns 0.8 in apart whatever the width
    for i, rp in enumerate(RPS):
        x = 1 + (0.8 + 0.8 * i) * inch
        ax.text(x, 1.04, RP_NAME[rp].replace(" flood", ""), transform=ax.transAxes, ha="right", va="bottom",
                fontsize=9, color=MUTED)  # on the legend row, whose labels are kept short to leave room
        for row, v in zip(y, values[rp]):
            ax.text(x, row, fmt(v), transform=tr, ha="right", va="center", fontsize=10,
                    weight="bold" if rp == PLAN else "normal", color=INK if rp == PLAN else MUTED)
    legend(ax, [patch(RP_NAME[rp].replace(" flood", ""), RP_COL[rp]) for rp in RPS])


def areas():
    """People per area and return period (area_summary), largest 100-year exposure first. The Vesdre box lies inside
    Liège's, so its homes are counted under Liège and its own row is empty: dropped."""
    a = pd.read_csv(DATA / "area_summary.csv", encoding="utf-8-sig")
    a["label"] = a.name.str.replace(" - MODELLED", "").str.replace(r" \(..\)| / Meuse", "", regex=True) \
        .str.replace("Liege", "Liège")
    keep = a[a.variant == "rp500"].set_index("area").people_2020 > 0
    a = a[a.area.isin(keep[keep].index)]
    order = a[a.variant == PLAN].sort_values("people_2020", ascending=False).area.tolist()
    return {rp: a[a.variant == rp].set_index("area").loc[order] for rp in RPS}


def people_in_zone(a):
    tot = {rp: a[rp].people_2020.sum() for rp in RPS}
    fig, ax = frame(f"A 100-year flood would reach about {round(tot[PLAN], -3):,.0f} residents today",
                    f"Residents of buildings in each flood zone, per area. A 10-year flood already reaches about "
                    f"{round(tot['rp10'], -3):,.0f}; a 500-year one {round(tot['rp500'], -3):,.0f}.",
                    height=4.6, legend=True, right=0.58,
                    notes="Vesdre valley: inside the Liège area's box, counted there. 10-year: 10 % chance in any "
                          "year; 100-year: 1 %; 500-year: 0.2 %.\n" + SOURCE)
    nested(ax, a[PLAN].label.tolist(), {rp: a[rp].people_2020.tolist() for rp in RPS})
    save(fig, "01_people_in_zone")


PARTS = [("central_covered", "Has a place", NAVY_PALE), ("central_full", "Shelter nearby, but full", NAVY),
         ("central_no_reach", "No shelter within 20 min walk", NAVY_MID)]


def stacked(ax, w, labels):
    """Has a place / full / too far, stacked, with the residents left without a place at the end of each bar."""
    y = list(range(len(w)))
    left = 0
    for col, _, c in PARTS:
        ax.barh(y, w[col], left=left, height=0.62, color=c, edgecolor=PAPER, linewidth=1)
        left = left + w[col].values
    for row, l, n in zip(y, left, (w.central_no_reach + w.central_full).values):
        ax.text(l + left.max() * 0.015, row, f"{r100(n)} without" if n >= 50 else "all have a place",
                va="center", fontsize=10, weight="bold" if n >= 50 else "normal", color=INK if n >= 50 else MUTED)
    ax.invert_yaxis()
    ax.set_yticks(y, labels)
    legend(ax, [patch(lab, c) for _, lab, c in PARTS])


def shelter_gap_by_rp(a):
    w = pd.DataFrame({rp: a[rp][[c for c, _, _ in PARTS] + ["people_2020", "bus_covered"]].sum() for rp in RPS}).T
    no = w.central_full + w.central_no_reach
    bus = (w.people_2020 - w.bus_covered).clip(lower=0)
    fig, ax = frame(f"In a 100-year flood, about {round(no[PLAN], -3):,.0f} residents would have no shelter place "
                    "on foot", "Residents of each flood zone by shelter outcome, today's homes and candidate shelters",
                    height=3.6, legend=True,
                    notes=f"With buses taking people up to 10 km, about {r100(bus['rp10'])} (10-year), "
                          f"{r100(bus['rp100'])} (100-year) and {r100(bus['rp500'])} (500-year) are left without a "
                          "place.\nShelters are candidates (schools, sports halls, civic buildings dry in that zone), "
                          "not official; 1.5 km walk, 4 m² per person.\n" + SOURCE)
    stacked(ax, w, [f"{RP_NAME[rp].capitalize()}\n{RP_ODDS[rp]}" for rp in RPS])
    for t in ax.get_yticklabels():
        t.set_fontsize(9.5)
    save(fig, "02_shelter_gap_by_return_period")


def shelter_gap(a):
    w = a[PLAN]
    no = (w.central_no_reach + w.central_full).sum()
    fig, ax = frame(f"Where the 100-year flood would leave {round(no, -3):,.0f} residents without a shelter place",
                    "Residents of the 100-year zone by shelter outcome, per area", height=4.6, legend=True,
                    notes="Vesdre valley counted in the Liège area. Shelters are candidates (schools, sports halls, "
                          "civic buildings dry in the 100-year zone),\nnot official; 1.5 km walk, 4 m² per person.\n"
                          + SOURCE)
    stacked(ax, w, w.label.tolist())
    save(fig, "03_shelter_gap")


def care_sites():
    s = pd.read_csv(DATA / "critical_sites.csv", encoding="utf-8-sig")
    s = s[s.share_of_site_flooded >= 0.05]  # below 5 % the flood only touches the edge
    types = ["hospital", "care home", "school"]
    n = {rp: s[s[f"in_{rp}_flood"].astype(bool)].type.value_counts().reindex(types, fill_value=0) for rp in RPS}
    care = {rp: n[rp][["hospital", "care home"]].sum() for rp in RPS}
    fig, ax = frame(f"{care[PLAN]} hospitals and care homes stand in the 100-year flood zone",
                    f"Sites with at least 5 % of their footprint in each zone: evacuate these first. "
                    f"{care['rp10']} are already in the 10-year zone.", height=3.4, legend=True, right=0.58,
                    notes="Source: OpenStreetMap × EFAS flood hazard maps (JRC), modelled, no dikes. OSM misses some "
                          "care homes: a floor.")
    nested(ax, [t.capitalize() + "s" for t in types], {rp: n[rp].tolist() for rp in RPS}, fmt=str)
    save(fig, "04_care_sites_flooded")


# shelter gap classes: EU yellow to EU navy (ec.europa.eu colour guidelines), lightness falls with every class
CLASSES = [(1, "1–249", "#fee5b1"), (250, "250–499", "#ffcc00"), (500, "500–999", "#8a9bb0"),
           (1000, "1,000–1,999", "#3d5675"), (2000, "2,000+", "#1a2634")]
NO_GAP = "#dcdad3"
LAND = "#f3f3f1"  # outside the study area: land, not data
BORDER = "#8c95a5"
RAW = ROOT / "src" / "out" / "raw"
# reference places for orientation, none of them a top-ten badge: (lon, lat, label side). Namur sits under Andenne's
# badge and Koblenz under the locator, so both are left out.
CITIES = {"Brussels": (4.352, 50.847, "r"), "Maastricht": (5.690, 50.851, "r"), "Aachen": (6.084, 50.776, "r"),
          "Cologne": (6.958, 50.938, "r"), "Bonn": (7.099, 50.737, "r"), "Düsseldorf": (6.773, 51.227, "r"),
          "Eindhoven": (5.478, 51.441, "r"), "Venlo": (6.172, 51.370, "r"),
          "Hasselt": (5.338, 50.931, "l"), "Luxembourg": (6.130, 49.611, "r")}
# country names placed by hand in open land: (lon, lat)
COUNTRIES = {"BE": ("BELGIUM", 4.62, 50.62), "NL": ("NETHERLANDS", 4.62, 51.57), "DE": ("GERMANY", 7.25, 51.12),
             "LU": ("LUX.", 6.10, 49.80), "FR": ("FRANCE", 4.90, 49.85)}
WATER_RIM = "#A9C8EE"  # the 500-year zone beyond the 100-year one: the same water, lighter


def gap_color(n):
    return next((c for lo, _, c in reversed(CLASSES) if n >= lo), NO_GAP)


def action(r):
    """The one concrete step that closes most of a municipality's gap."""
    if r.full >= r.no_reach:
        return f"Open ~{round(r.full, -1):,.0f} more shelter places"
    return f"Transport for ~{round(r.no_reach, -1):,.0f} residents"


def swatch(fig, x, y, color, w=0.018, h=0.022):
    fig.patches.append(matplotlib.patches.Rectangle((x, y), w, h, facecolor=color, linewidth=0,
                                                    transform=fig.transFigure, figure=fig))


def countries():
    """Country outlines from the GISCO NUTS 3 file already on disk, dissolved to one shape per country."""
    import geopandas as gpd

    n = gpd.read_file(RAW / "NUTS_RG_01M_2021_4326_LEVL_3.geojson")
    return n[n.CNTR_CODE.isin(COUNTRIES)].dissolve("CNTR_CODE").to_crs(3035)


def basemap(ax, m, c, pad=0.06, size=7, extra=None):
    """Where the study area sits: land and country borders around it, country names and a few reference cities.
    Sets the extent to fill the axes so the land runs to the frame. Returns the extent."""
    import geopandas as gpd

    fig = ax.figure
    fig.canvas.draw()
    bb = ax.get_position()
    aspect = bb.width * fig.get_figwidth() / (bb.height * fig.get_figheight())
    x0, y0, x1, y1 = m.total_bounds
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
    w, h = max(w, h * aspect), max(h, w / aspect)
    ext = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    ax.set_facecolor(PAPER)
    c.plot(ax=ax, color=LAND, edgecolor="none", zorder=0)
    c.boundary.plot(ax=ax, color=BORDER, linewidth=0.7, linestyle=(0, (3, 1.5)), zorder=3)
    ax.set_xlim(ext[0], ext[2])
    ax.set_ylim(ext[1], ext[3])
    ax.set_aspect("equal")
    inside = lambda x, y, e=0.06: ext[0] + w * e < x < ext[2] - w * e and ext[1] + h * e < y < ext[3] - h * e  # noqa: E731
    lonlat = lambda pts: gpd.GeoSeries(gpd.points_from_xy(*zip(*pts)), crs=4326).to_crs(3035)  # noqa: E731
    for (name, _, _), p in zip(COUNTRIES.values(), lonlat([v[1:] for v in COUNTRIES.values()])):
        if not inside(p.x, p.y, -0.02):  # well outside this view: not named
            continue
        y = min(max(p.y, ext[1] + h * 0.04), ext[3] - h * 0.04)  # near an edge: pulled in, not dropped
        ax.text(p.x, y, " ".join(name), ha="center", va="center", fontsize=size - 0.5, color=BORDER,
                weight="bold", zorder=6)
    halo = [matplotlib.patheffects.withStroke(linewidth=2, foreground="white")]
    cities = CITIES | (extra or {})
    for (name, (_, _, side)), p in zip(cities.items(), lonlat([v[:2] for v in cities.values()])):
        if not inside(p.x, p.y):
            continue
        ax.plot(p.x, p.y, "o", ms=size * 0.42, mfc=INK, mec="white", mew=0.6, zorder=7)
        ax.annotate(name, (p.x, p.y), xytext=(3.5 if side == "r" else -3.5, 1.5), textcoords="offset points",
                    fontsize=size - 0.5, color=INK, va="bottom", ha="left" if side == "r" else "right", zorder=7,
                    path_effects=halo)
    return ext


def locator(fig, rect, c, ext):
    """Small outline of the surrounding countries with the map's frame on it."""
    x0, y0, x1, y1 = c.drop(index="FR", errors="ignore").total_bounds  # France has overseas regions: not its bounds
    aspect = rect[2] * fig.get_figwidth() / (rect[3] * fig.get_figheight())
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 1.08, (y1 - y0) * 1.08
    w, h = max(w, h * aspect), max(h, w / aspect)
    view = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    ax = fig.add_axes(rect)
    c.clip(view).plot(ax=ax, color=LAND, edgecolor=BORDER, linewidth=0.4)
    ax.add_patch(matplotlib.patches.Rectangle((ext[0], ext[1]), ext[2] - ext[0], ext[3] - ext[1], fill=False,
                                              edgecolor=INK, linewidth=0.9))
    ax.set_xlim(view[0], view[2])
    ax.set_ylim(view[1], view[3])
    ax.set_aspect("auto")  # the view already matches the box, so the outline keeps its true shape
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_facecolor(PAPER)
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_color(BORDER)
        sp.set_linewidth(0.6)


def gap_title(q, sep=" "):
    """Lead with the people, not a municipality count: the total without a place and the top ten's share of it."""
    tot = q.no_shelter.sum()
    share = q.nlargest(10, "no_shelter").no_shelter.sum() / tot
    part = "half of them" if 0.45 <= share <= 0.55 else f"{share:.0%} of them"
    return f"About {round(tot, -3):,.0f} residents would have no shelter place,{sep}{part} in ten municipalities"


def risk_map():
    """Residents with no shelter place in a 100-year flood, per municipality, and the first action for the ten
    largest gaps. The 500-year zone shows as a lighter rim: where the water goes if the flood is rarer."""
    import geopandas as gpd

    q = pd.read_csv(DATA / "q4_ranking.csv", encoding="utf-8-sig")
    q = q[q.variant == PLAN]
    m = gpd.read_file(DATA / "municipality_outlines.geojson").merge(q, on="municipality", how="left").to_crs(3035)
    m["color"] = m.no_shelter.fillna(0).map(gap_color)
    zone = {rp: pd.concat([gpd.read_file(f) for f in DATA.glob(f"flood_*_{rp}.geojson")]).to_crs(3035)
            for rp in ("rp100", "rp500")}

    fig = plt.figure(figsize=(15, 8.6))
    fig.text(0.02, 0.96, gap_title(q),
             fontsize=17, weight="bold", va="top")
    fig.text(0.02, 0.91, "In a 100-year river flood (1 % chance in any year), with today's homes and candidate "
                         "shelters. Modelled zones (EFAS), no dikes.", fontsize=11, color=MUTED, va="top")
    ax = fig.add_axes([0.02, 0.07, 0.52, 0.79])
    ax.set_axis_off()
    c = countries()
    ext = basemap(ax, m, c, size=9)
    m.plot(ax=ax, color=m.color, edgecolor="white", linewidth=0.8, zorder=1)
    zone["rp500"].plot(ax=ax, color=WATER_RIM, linewidth=0, zorder=2)
    zone["rp100"].plot(ax=ax, color=WATER, linewidth=0, zorder=2)
    ax.set_xlim(ext[0], ext[2])
    ax.set_ylim(ext[1], ext[3])
    top = m[m["rank"] <= 10].sort_values("rank")
    pts = [(p.x, p.y) for p in top.geometry.representative_point()]
    for (x0, y0), (x, y), rank in zip(pts, spread(ax, pts, 15), top["rank"]):  # badges tie the map to the list
        if abs(x - x0) + abs(y - y0) > 0:
            ax.plot([x0, x], [y0, y], color=INK, linewidth=0.6, zorder=8)
        ax.annotate(str(int(rank)), (x, y), ha="center", va="center", fontsize=8, weight="bold", zorder=9,
                    bbox=dict(boxstyle="circle,pad=0.25", facecolor="white", edgecolor=INK, linewidth=0.8))
    locator(fig, [0.462, 0.085, 0.07, 0.15], c, ext)

    # scale: one stepped bar, classes left to right
    x0, y = 0.575, 0.80
    fig.text(x0, y + 0.03, "Residents without a shelter place, 100-year flood", fontsize=10, weight="bold")
    for i, (lab, color) in enumerate([("0", NO_GAP)] + [(r, c) for _, r, c in CLASSES]):
        swatch(fig, x0 + i * 0.068, y - 0.012, color, w=0.066, h=0.016)
        fig.text(x0 + i * 0.068, y - 0.036, lab, fontsize=9, color=MUTED)
    swatch(fig, x0, y - 0.09, WATER)
    fig.text(x0 + 0.024, y - 0.086, "100-year flood zone", fontsize=9, color=MUTED)
    swatch(fig, x0 + 0.15, y - 0.09, WATER_RIM)
    fig.text(x0 + 0.174, y - 0.086, "Also flooded in a 500-year flood", fontsize=9, color=MUTED)

    # action list: the ten largest gaps
    y -= 0.17
    cols = [(x0, "", "left"), (x0 + 0.022, "Municipality", "left"), (0.80, "No place", "right"),
            (0.815, "First action", "left"), (0.985, "Care sites\nflooded", "right")]
    for x, h, ha in cols:
        fig.text(x, y, h, fontsize=9, color=MUTED, ha=ha, va="bottom")
    fig.add_artist(matplotlib.lines.Line2D([x0, 0.985], [y - 0.01] * 2, color=MUTED, linewidth=0.6))
    for _, r in top.iterrows():
        y -= 0.036
        cells = [f"{int(r['rank'])}", " ".join(LOCAL.get(w, w) for w in r.municipality.replace(", Stadt", "").split(" ")), f"{round(r.no_shelter, -1):,.0f}",
                 action(r), str(int(r.hospitals_carehomes_flooded)) if r.hospitals_carehomes_flooded else ""]
        for (x, _, ha), t in zip(cols, cells):
            fig.text(x, y, t, fontsize=10, ha=ha, va="bottom", weight="bold" if x == 0.80 else "normal")
        swatch(fig, 0.735, y - 0.002, r.color, w=0.01)
    fig.text(x0, y - 0.04, "Care sites flooded: hospitals and care homes in the 100-year zone, evacuate first.",
             fontsize=8.5, color=MUTED, va="top")
    fig.text(0.02, 0.015, SOURCE.replace("\n", " ") + " Municipalities: GISCO LAU 2021. Shelters are candidates, not "
                                                      "official (1.5 km walk, 4 m² per person). Counts rounded to 10.",
             fontsize=8, color=MUTED)
    save(fig, "06_risk_map_actions")


def spread(ax, pts, gap):
    """Push badges apart until no two are closer than gap (in points), so neighbours like Remagen and Unkel stay
    readable. Works in display space; returns the moved positions in data space."""
    import numpy as np

    px = ax.figure.dpi / 72 * gap
    d = ax.transData.transform(pts)
    for _ in range(200):
        moved = False
        for i in range(len(d)):
            for j in range(i + 1, len(d)):
                v = d[j] - d[i]
                n = np.hypot(*v)
                if n < px:
                    v = v / n if n else np.array([1.0, 0.0])
                    d[i] -= v * (px - n) / 2
                    d[j] += v * (px - n) / 2
                    moved = True
        if not moved:
            break
    return ax.transData.inverted().transform(d)


def risk_map_square():
    """The risk map as a 6 × 6 in square for the report: the map alone, the legend in one row under it. No badges or
    list, so the places with the largest gaps are named on the map instead."""
    import geopandas as gpd

    q = pd.read_csv(DATA / "q4_ranking.csv", encoding="utf-8-sig")
    q = q[q.variant == PLAN]
    m = gpd.read_file(DATA / "municipality_outlines.geojson").merge(q, on="municipality", how="left").to_crs(3035)
    m["color"] = m.no_shelter.fillna(0).map(gap_color)
    zone = {rp: pd.concat([gpd.read_file(f) for f in DATA.glob(f"flood_*_{rp}.geojson")]).to_crs(3035)
            for rp in ("rp100", "rp500")}
    S = 6.0
    fig = plt.figure(figsize=(S, S))
    fx = lambda inch: inch / S  # noqa: E731  inches to figure fractions
    L, R = fx(0.25), 1 - fx(0.25)
    fig.text(L, 1 - fx(0.22), gap_title(q, sep="\n"),
             fontsize=13, weight="bold", va="top", linespacing=1.15)
    fig.text(L, 1 - fx(0.72), "100-year river flood (1 % chance in any year), today's homes and candidate shelters",
             fontsize=8.5, color=MUTED, va="top")

    # map: the full width
    ax = fig.add_axes([L, fx(1.2), R - L, fx(3.85)])
    ax.set_axis_off()
    c = countries()
    ext = basemap(ax, m, c, pad=0.03, size=7.5,
                  extra={"Liège": (5.571, 50.633, "l"), "Namur": (4.867, 50.467, "l")})
    m.plot(ax=ax, color=m.color, edgecolor="white", linewidth=0.4, zorder=1)
    zone["rp500"].plot(ax=ax, color=WATER_RIM, linewidth=0, zorder=2)
    zone["rp100"].plot(ax=ax, color=WATER, linewidth=0, zorder=2)
    ax.set_xlim(ext[0], ext[2])
    ax.set_ylim(ext[1], ext[3])
    locator(fig, [R - fx(0.62), fx(1.2 + 0.04), fx(0.58), fx(0.72)], c, ext)

    # legend: one stepped bar for the classes, the water and the backdrop beside it
    y = fx(0.98)
    fig.text(L, y, "Residents without a shelter place", fontsize=7.5, weight="bold", va="top")
    step = fx(0.56)
    for i, (lab, color) in enumerate([("0", NO_GAP)] + [(r, c) for _, r, c in CLASSES]):
        swatch(fig, L + i * step, y - fx(0.3), color, w=step - fx(0.03), h=fx(0.1))
        fig.text(L + i * step, y - fx(0.34), lab, fontsize=7, color=INK, va="top")
    lx = L + fx(3.7)
    for i, (lab, color) in enumerate([("100-year flood zone", WATER), ("Also in a 500-year flood", WATER_RIM),
                                      ("Outside the study area", LAND)]):
        yy = y - fx(0.02 + 0.17 * i)
        swatch(fig, lx, yy - fx(0.1), color, w=fx(0.16), h=fx(0.1))
        fig.text(lx + fx(0.22), yy - fx(0.05), lab, fontsize=7, color=INK, va="center")

    fig.text(L, fx(0.1), "Source: EFAS flood hazard maps (JRC), modelled with no dikes, so towns behind flood walls "
                         "(Liège, Venlo) are an upper bound; GHS-OBAT, GHS-POP 2020;\nOpenStreetMap; GISCO LAU 2021. "
                         "Shelters are candidates, not official (1.5 km walk, 4 m² per person). Residents are an order "
                         "of magnitude;\ncounts rounded to 10.", fontsize=5.3, color=MUTED, linespacing=1.4)
    save(fig, "06_risk_map_actions_square")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    a = areas()
    people_in_zone(a)
    shelter_gap_by_rp(a)
    shelter_gap(a)
    care_sites()
    risk_map()
    risk_map_square()
