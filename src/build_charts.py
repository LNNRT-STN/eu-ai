"""Static charts for the policy brief: July 2021 and the flood risk today. python src/build_charts.py →
outputs/charts/*.png (print, slides) and *.svg (editable). Reads only the cleaned data in outputs/data/.

Observed (satellite) areas and the modelled Vesdre are never summed: the Vesdre is drawn apart, hatched."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines
import matplotlib.patches
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "outputs" / "data"
OUT = ROOT / "outputs" / "charts"

# dataviz reference palette (light): slots 1-3 validate as a set; text stays in ink, never series colour
INK, INK2, MUTED, SURFACE = "#0b0b0b", "#4f6580", "#5a6e87", "#fcfcfb"
BLUE, ORANGE, VIOLET, NEUTRAL = "#2a78d6", "#eb6834", "#6250d6", "#c3c2b7"
SOURCE = "Source: Copernicus EMS, EFAS, GHS-OBAT, GHS-POP 2020 (challenge data); OpenStreetMap. Team analysis. " \
         "Residents are an order of magnitude."
SMALL = 1000  # observed areas below this many residents fold into one row: their bars would be invisible

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 10,
    "text.color": INK, "ytick.color": INK, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.spines.bottom": False,
    "xtick.bottom": False, "xtick.labelbottom": False, "ytick.major.size": 0, "legend.frameon": False,
    "savefig.dpi": 200, "svg.fonttype": "none", "hatch.linewidth": 0.8,  # SVG text stays editable
})
LABEL_W = 2.2  # inches for the category labels, the same in every bar chart so they line up in the brief


def frame(title, subtitle, note=SOURCE, height=4.4, legend=False):
    """Message title, one-line subtitle, source line: each chart must stand alone in a brief. No axis: bars carry
    their own value labels. Spacing is set in inches so every chart has the same rhythm whatever its height."""
    fig, ax = plt.subplots(figsize=(9, height))
    pad, top = 0.2 / 9, 1 - (1.0 + 0.3 * legend) / height
    bottom = (0.25 + 0.15 * (note.count("\n") + 1)) / height
    fig.subplots_adjust(left=LABEL_W / 9, right=0.9, top=top, bottom=bottom)
    fig.text(pad, 1 - 0.25 / height, title, fontsize=14, weight="bold", va="top")
    fig.text(pad, 1 - 0.6 / height, subtitle, fontsize=10, color=INK2, va="top")
    fig.text(pad, 0.12 / height, note, fontsize=7.5, color=MUTED, linespacing=1.5)
    return fig, ax


def legend(ax, handles):
    """One row above the plot, clear of the bars."""
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.02), ncol=4, fontsize=9, handlelength=1.4,
              borderaxespad=0)


def patch(label, color, hatch=""):
    return matplotlib.patches.Patch(facecolor=color, edgecolor=BLUE if hatch else color, hatch=hatch, label=label)


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def areas():
    """Areas on the headline map (all satellite passes), largest first, small ones folded, modelled Vesdre last."""
    a = pd.read_csv(DATA / "area_summary.csv", encoding="utf-8-sig")
    w = a[a.variant == "worst"].set_index("area")
    w["label"] = w.name.str.replace(" - MODELLED", "")
    obs, vesdre = w[w.index != "vesdre"], w.loc[["vesdre"]]
    small = obs[obs.people_2020 < SMALL]
    folded = small.select_dtypes("number").sum().to_frame("other").T
    folded["label"] = f"{len(small)} smaller areas*"
    rows = pd.concat([obs[obs.people_2020 >= SMALL].sort_values("people_2020", ascending=False), folded])
    rows["modelled"], vesdre["modelled"] = False, True
    vesdre["label"] = vesdre.label + ", modelled"
    rows = pd.concat([rows, vesdre])
    rows["y"] = [-i for i in range(len(rows) - 1)] + [-(len(rows) - 1) - 0.5]  # Vesdre set apart
    names = small.label.str.replace(r" \(..\)| / Meuse", "", regex=True).str.replace("Liege", "Liège")
    return rows, ", ".join(names)


def bars(ax, w, col, left=0, **kw):
    ax.barh(w.y, w[col], left=left, height=0.62, hatch=["////" if m else "" for m in w.modelled], **kw)


def people_in_water(w, small):
    total = w[~w.modelled].people_2020.sum()
    fig, ax = frame(f"About {round(total, -3):,.0f} residents lived in buildings the 2021 flood reached",
                    "Residents of flooded buildings, July 2021", height=4.2,
                    note=f"* {small}. Vesdre: no satellite map, EFAS 500-year model, not in the total.\n" + SOURCE)
    bars(ax, w, "people_2020", color=[SURFACE if m else BLUE for m in w.modelled], edgecolor=BLUE, linewidth=1.2)
    for y, v in zip(w.y, w.people_2020):
        ax.text(v + w.people_2020.max() * 0.012, y, f"{round(v, -2):,.0f}", va="center", fontsize=9.5)
    ax.set_yticks(w.y, w.label)
    save(fig, "01_people_in_water_2021")


def shelter_gap(w, small):
    gap = w[~w.modelled]
    no = (gap.central_no_reach + gap.central_full).sum()
    fig, ax = frame(f"If 2021 happened today, about {round(no, -3):,.0f} residents would have no shelter place",
                    "Residents of the 2021 flood zone by shelter outcome", height=4.6, legend=True,
                    note=f"* {small}. Vesdre modelled, not in the total.\nShelters are candidates (schools, sports "
                         f"halls, civic buildings dry in 2021), not official; 1.5 km walk, 4 m² per person.\n" + SOURCE)
    parts = [("central_covered", "Has a place", NEUTRAL), ("central_no_reach", "No shelter within walking distance",
             ORANGE), ("central_full", "Shelters in reach are full", VIOLET)]
    left = 0
    for col, _, c in parts:
        bars(ax, w, col, left=left, color=c, edgecolor=SURFACE, linewidth=1.5)
        left = left + w[col]
    for y, l, n in zip(w.y, left, w.central_no_reach + w.central_full):
        ax.text(l + left.max() * 0.012, y, f"{round(n, -2):,.0f} without" if n >= 50 else "covered", va="center",
                fontsize=9.5, color=INK if n >= 50 else MUTED)
    ax.set_yticks(w.y, w.label)
    legend(ax, [patch(lab, c) for _, lab, c in parts])
    save(fig, "03_shelter_gap")


def care_sites():
    s = pd.read_csv(DATA / "critical_sites.csv", encoding="utf-8-sig")
    s = s[(s.share_of_site_flooded >= 0.05) & s.in_worst_flood]  # below 5 % the flood only touches the edge
    s["kind"] = s.source.str.startswith("EFAS").map({True: "Vesdre, modelled", False: "Satellite-mapped"})
    n = s.groupby(["type", "kind"]).size().unstack(fill_value=0).reindex(["hospital", "care home", "school"])
    fig, ax = frame(f"{n.loc[['hospital', 'care home']].values.sum()} hospitals and care homes stood in the 2021 water",
                    "Sites with at least 5 % of their footprint flooded: evacuate these first", height=3.4, legend=True,
                    note="Source: OpenStreetMap × Copernicus EMS flood extent; Vesdre: EFAS 500-year model. "
                         "OSM misses some care homes: a floor.")
    left = 0
    for kind, c, h in (("Satellite-mapped", BLUE, ""), ("Vesdre, modelled", SURFACE, "////")):
        ax.barh(n.index, n[kind], left=left, height=0.55, color=c, edgecolor=BLUE, hatch=h)
        left = left + n[kind]
    for i, v in enumerate(left):
        ax.text(v + 0.4, i, str(v), va="center", fontsize=9.5)
    ax.invert_yaxis()
    ax.set_yticks(range(len(n)), [t.capitalize() + "s" for t in n.index])
    legend(ax, [patch("Satellite-mapped", BLUE), patch("Vesdre, modelled", SURFACE, "////")])
    save(fig, "04_care_sites_flooded")


# shelter gap classes: EU yellow to EU navy (ec.europa.eu colour guidelines), lightness falls with every class
CLASSES = [(1, "1–249", "#fee5b1"), (250, "250–499", "#ffcc00"), (500, "500–999", "#8a9bb0"),
           (1000, "1,000–1,999", "#3d5675"), (2000, "2,000+", "#1a2634")]
NO_GAP = "#e9e8e4"


def gap_color(n):
    return next((c for lo, _, c in reversed(CLASSES) if n >= lo), NO_GAP)


def action(r):
    """The one concrete step that closes most of a municipality's gap."""
    if r.full >= r.no_reach:
        return f"Open ~{round(r.full, -1):,.0f} more shelter places"
    return f"Transport for ~{round(r.no_reach, -1):,.0f} residents"


def swatch(fig, x, y, color, w=0.018, h=0.022, hatch=""):
    fig.patches.append(matplotlib.patches.Rectangle((x, y), w, h, facecolor=color, hatch=hatch,
                                                    linewidth=0.6 if hatch else 0,
                                                    edgecolor=INK2, transform=fig.transFigure, figure=fig))


def risk_map():
    """Residents with no shelter place if the 2021 flood returned, per municipality, and the first action for the
    ten largest gaps."""
    import geopandas as gpd

    q = pd.read_csv(DATA / "q4_ranking.csv", encoding="utf-8-sig")
    m = gpd.read_file(DATA / "municipality_outlines.geojson").merge(q, on="municipality", how="left").to_crs(3035)
    m["color"] = m.no_shelter.fillna(0).map(gap_color)
    modelled = m.source.fillna("").str.startswith("MODELLED")
    floods = pd.concat([gpd.read_file(f) for f in DATA.glob("flood_*_worst.geojson")]).to_crs(3035)

    fig = plt.figure(figsize=(15, 8.6))
    big = q[q.no_shelter >= 1000]
    fig.text(0.02, 0.96, f"{len(big)} municipalities would leave over 1,000 residents each without a shelter place",
             fontsize=17, weight="bold", va="top")
    fig.text(0.02, 0.91, f"If the July 2021 flood returned. {big.source.str.startswith('MODELLED').sum()} of the "
                         f"{len(big)} are in the modelled Vesdre valley.", fontsize=11, color=INK2, va="top")
    ax = fig.add_axes([0.01, 0.06, 0.53, 0.80])
    ax.set_axis_off()
    m.plot(ax=ax, color=m.color, edgecolor="white", linewidth=0.8)
    m[modelled].plot(ax=ax, facecolor="none", edgecolor=INK2, hatch="///", linewidth=0)
    floods.plot(ax=ax, color=BLUE, linewidth=0)
    top = m[m["rank"] <= 10].sort_values("rank")
    for _, r in top.iterrows():  # numbered badges tie the map to the action list
        p = r.geometry.representative_point()
        ax.annotate(str(int(r["rank"])), (p.x, p.y), ha="center", va="center", fontsize=8, weight="bold",
                    bbox=dict(boxstyle="circle,pad=0.25", facecolor="white", edgecolor=INK, linewidth=0.8))
    ax.set_aspect("equal")

    # scale: one stepped bar, classes left to right
    x0, y = 0.575, 0.80
    fig.text(x0, y + 0.03, "Residents without a shelter place", fontsize=10, weight="bold")
    for i, (lab, color) in enumerate([("0", NO_GAP)] + [(r, c) for _, r, c in CLASSES]):
        swatch(fig, x0 + i * 0.068, y - 0.012, color, w=0.066, h=0.024)
        fig.text(x0 + i * 0.068, y - 0.036, lab, fontsize=9, color=INK2)
    swatch(fig, x0, y - 0.09, BLUE)
    fig.text(x0 + 0.024, y - 0.086, "July 2021 flood", fontsize=9, color=INK2)
    swatch(fig, x0 + 0.13, y - 0.09, "none", hatch="///")
    fig.text(x0 + 0.154, y - 0.086, "Modelled (Vesdre, EFAS)", fontsize=9, color=INK2)

    # action list: the ten largest gaps
    y -= 0.17
    cols = [(x0, "", "left"), (x0 + 0.022, "Municipality", "left"), (0.80, "No place", "right"),
            (0.815, "First action", "left"), (0.985, "Care sites\nflooded", "right")]
    for x, h, ha in cols:
        fig.text(x, y, h, fontsize=9, color=INK2, ha=ha, va="bottom")
    fig.add_artist(matplotlib.lines.Line2D([x0, 0.985], [y - 0.01] * 2, color=INK2, linewidth=0.6))
    for _, r in top.iterrows():
        y -= 0.036
        name = r.municipality.replace(", Stadt", "") + (" *" if r.source.startswith("MODELLED") else "")
        cells = [f"{int(r['rank'])}", name, f"{round(r.no_shelter, -1):,.0f}", action(r),
                 str(int(r.hospitals_carehomes_flooded)) if r.hospitals_carehomes_flooded else ""]
        for (x, _, ha), t in zip(cols, cells):
            fig.text(x, y, t, fontsize=10, ha=ha, va="bottom", weight="bold" if x == 0.80 else "normal")
        swatch(fig, 0.735, y - 0.002, r.color, w=0.01)
    fig.text(x0, y - 0.04, "* Modelled. Care sites flooded: hospitals and care homes in the 2021 water, evacuate first.",
             fontsize=8.5, color=INK2, va="top")
    fig.text(0.02, 0.015, SOURCE + " Municipalities: GISCO LAU 2021. Shelters are candidates, not official "
                                   "(1.5 km walk, 4 m² per person). Counts rounded to 10.", fontsize=8, color=MUTED)
    save(fig, "06_risk_map_actions")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    w, small = areas()
    people_in_water(w, small)
    shelter_gap(w, small)
    care_sites()
    risk_map()
