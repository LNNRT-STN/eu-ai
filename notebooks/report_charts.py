"""Figures for the policy brief 'From warning to safety' (EU visual style).

Reads outputs/data/, writes outputs/charts/report/fig*.png (300 dpi) and .svg.
Run: python notebooks/report_charts.py
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "outputs" / "data"
OUT = ROOT / "outputs" / "charts" / "report"
OUT.mkdir(parents=True, exist_ok=True)

# EU palette: flag blue and yellow, with blue tints for secondary marks
EU_BLUE = "#003399"
EU_YELLOW = "#FFCC00"
BLUE_MID = "#5A7FD6"
BLUE_PALE = "#D6DFF2"
INK = "#14213D"
MUTED = "#5B6577"
RULE = "#C7CCD6"
RED = "#B8202F"

plt.rcParams.update({
    "font.family": ["Arial", "Helvetica Neue", "DejaVu Sans"],
    "font.size": 9.5,
    "text.color": INK,
    "axes.edgecolor": RULE,
    "svg.fonttype": "none",
})

SOURCE = ("Source: Copernicus EMS (EMSR517/518/520), EFAS, GHS-POP, GHS-OBAT (JRC); "
          "OpenStreetMap 29.10.2026. Team 5 analysis.")


def k(n):
    return f"{round(n, -2):,.0f}"


def header(fig, title, subtitle):
    # EU-blue rule with a yellow tab, then title and subtitle, left-aligned
    fig.add_artist(plt.Line2D([0.04, 0.96], [0.975, 0.975], color=EU_BLUE, lw=2.2,
                              transform=fig.transFigure))
    fig.add_artist(plt.Line2D([0.04, 0.10], [0.975, 0.975], color=EU_YELLOW, lw=4.5,
                              transform=fig.transFigure, solid_capstyle="butt"))
    fig.text(0.04, 0.925, title, fontsize=14, fontweight="bold", color=EU_BLUE, va="top")
    fig.text(0.04, 0.855, subtitle, fontsize=10, color=MUTED, va="top")


def footer(fig, lines):
    y = 0.035
    for line in reversed(lines):
        fig.text(0.04, y, line, fontsize=7.2, color=MUTED, va="bottom")
        y += 0.038


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=300, facecolor="white")
    fig.savefig(OUT / f"{name}.svg", facecolor="white")
    plt.close(fig)


def clean(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)


head = json.loads((DATA / "q4_headline.json").read_text())
rank = pd.read_csv(DATA / "q4_ranking.csv", encoding="utf-8-sig")

# ---------------------------------------------------------------- Figure 1
# The four priority towns: who has a shelter place, who does not and why
names = {"Pepinster (BE)": "Pepinster", "Trooz (BE)": "Trooz", "Limburg (BE)": "Limbourg",
         "Theux (BE)": "Theux", "Chaudfontaine (BE)": "Chaudfontaine", "Verviers (BE)": "Verviers"}
towns = rank.set_index("municipality").loc[list(names)].reset_index()
towns["label"] = towns.municipality.map(names)

fig = plt.figure(figsize=(7.2, 4.6))
header(fig, "In four Vesdre towns, most residents would find no shelter place",
       "Residents of the flood area by shelter outcome, if the 2021 flood returned")
ax = fig.add_axes([0.20, 0.235, 0.62, 0.49])
ys = [5.6, 4.6, 3.6, 2.6, 1.0, 0.0]  # gap separates priority towns from comparison towns
H = 0.62
for y, r in zip(ys, towns.itertuples()):
    ax.barh(y, r.covered, H, color=BLUE_PALE, edgecolor="white", lw=0.8)
    ax.barh(y, r.full, H, left=r.covered, color=EU_BLUE, edgecolor="white", lw=0.8)
    ax.barh(y, r.no_reach, H, left=r.covered + r.full, color=BLUE_MID, edgecolor="white", lw=0.8)
    total = r.covered + r.full + r.no_reach
    pct = r.no_shelter / r.people
    strong = y > 2
    lab = f"{k(r.no_shelter)} without a place" if strong else f"{pct:.0%} without a place"
    ax.text(total + 70, y, lab, va="center", fontsize=9,
            fontweight="bold" if strong else "normal", color=INK if strong else MUTED)
ax.set_yticks(ys, towns.label, fontsize=10)
for t, y in zip(ax.get_yticklabels(), ys):
    t.set_fontweight("bold" if y > 2 else "normal")
    t.set_color(INK if y > 2 else MUTED)
ax.set_xlim(0, 5000)
ax.set_ylim(-0.6, 6.25)
ax.xaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
ax.tick_params(axis="x", labelsize=8, colors=MUTED)
ax.grid(axis="x", color=RULE, lw=0.5)
ax.set_axisbelow(True)
clean(ax)
ax.text(-0.27, 6.05, "PRIORITY TOWNS", transform=ax.get_yaxis_transform(),
        fontsize=7.5, fontweight="bold", color=EU_BLUE)
ax.text(-0.27, 1.45, "FOR COMPARISON", transform=ax.get_yaxis_transform(),
        fontsize=7.5, fontweight="bold", color=MUTED)
# Trooz callout
trooz = towns.set_index("label").loc["Trooz"]
ax.text((trooz.covered + trooz.covered + trooz.full) / 2, 4.6,
        f"only {trooz.covered:,.0f} of {trooz.people:,.0f} have a place",
        fontsize=8, color="white", va="center", ha="center", fontweight="bold")
# legend
lg = fig.add_axes([0.20, 0.755, 0.76, 0.05]); lg.axis("off")
for x, c, lab in [(0, BLUE_PALE, "Has a place"), (0.22, EU_BLUE, "Shelter nearby, but full"),
                  (0.56, BLUE_MID, "No shelter within 20 min walk")]:
    lg.add_patch(FancyBboxPatch((x, 0.25), 0.025, 0.5, boxstyle="square,pad=0", color=c,
                                transform=lg.transAxes))
    lg.text(x + 0.035, 0.5, lab, va="center", fontsize=8.5, transform=lg.transAxes)
footer(fig, ["Vesdre flood area modelled (EFAS 100-year flood); satellites missed most of the 2021 water here. "
             "Shelters: schools, sports halls, town halls",
             "that stayed dry; candidates, not official. Central estimate, residents are an order of magnitude.",
             SOURCE])
save(fig, "fig1_priority_towns")

# ---------------------------------------------------------------- Figure 2
# Headline with ranges; observed and modelled kept in separate panels
obs, ves = head["worst"]["observed"], head["main"]["modelled_vesdre"]
fig = plt.figure(figsize=(7.2, 3.9))
header(fig, "Most people left without a place live near a shelter that is full",
       "Residents without a shelter place if the 2021 flood returned, central estimate and range")
panels = [
    ("Where satellites mapped the 2021 flood", "Ahr, Schleiden, Liège, Venlo and 5 more areas (observed)", obs),
    ("Vesdre valley", "once-a-century flood map (modelled)", ves),
]
XMAX = 33000
for i, (t, sub, d) in enumerate(panels):
    ax = fig.add_axes([0.04, 0.53 - i * 0.255, 0.92, 0.12])
    ax.set_xticks(range(0, 25001, 5000))
    clean(ax)
    ax.set_xlim(0, XMAX); ax.set_ylim(-0.6, 0.6); ax.set_yticks([])
    lo, hi = d["no_shelter_range"]
    ax.plot([lo, hi], [0, 0], color=INK, lw=1, zorder=1)
    for v in (lo, hi):
        ax.plot([v, v], [-0.38, 0.38], color=INK, lw=1, zorder=1)
    ax.barh(0, d["full"], 0.5, color=EU_BLUE, zorder=2)
    ax.barh(0, d["too_far"], 0.5, left=d["full"], color=BLUE_MID, zorder=2)
    ax.text(0, 1.55, t, fontsize=10, fontweight="bold", transform=ax.get_xaxis_transform())
    ax.text(0, 1.18, sub, fontsize=8.5, color=MUTED, transform=ax.get_xaxis_transform())
    ax.text(hi + 400, 0.12, f"{k(d['no_shelter'])}", fontsize=15, fontweight="bold",
            color=EU_BLUE, va="center")
    ax.text(hi + 400, -0.42, f"range {k(lo)} to {k(hi)}", fontsize=7.8, color=MUTED, va="center")
    share = d["full"] / d["no_shelter"]
    ax.text(d["full"] / 2, 0, f"{share:.0%} near a full shelter" if d["full"] > 9000 else f"{share:.0%}", color="white",
            fontsize=8, va="center", ha="center", zorder=3, fontweight="bold")
    if i == 0:
        ax.tick_params(axis="x", labelbottom=False)
    else:
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
        ax.tick_params(axis="x", labelsize=8, colors=MUTED)
        ax.text(16500, 0,
                f"Sharing shelters across\ntown borders: +{k(ves['coordination_gain'])} places",
                fontsize=8.5, va="center", color=INK,
                bbox=dict(boxstyle="round,pad=0.45", fc="#FFF6CC", ec=EU_YELLOW, lw=1))
lg = fig.add_axes([0.04, 0.115, 0.92, 0.05]); lg.axis("off")
for x, c, lab in [(0, EU_BLUE, "Shelter nearby, but full"), (0.29, BLUE_MID, "No shelter within 20 min walk")]:
    lg.add_patch(FancyBboxPatch((x, 0.25), 0.022, 0.5, boxstyle="square,pad=0", color=c, transform=lg.transAxes))
    lg.text(x + 0.03, 0.5, lab, va="center", fontsize=8.5, transform=lg.transAxes)
lg.plot([0.62, 0.66], [0.5, 0.5], color=INK, lw=1, transform=lg.transAxes)
lg.text(0.67, 0.5, "range (low to high assumptions)", va="center", fontsize=8.5, transform=lg.transAxes)
footer(fig, ["The two estimates use different flood maps and are not added together. Range: shelter space 3-5 m² "
             "per person, walk 1-2.5 km.", SOURCE])
save(fig, "fig2_headline_ranges")

# ---------------------------------------------------------------- Figure 3
# Since 2021: four-line status board (symbol + word, never colour alone)
rows = [
    ("Warning", "BETTER", "✓", EU_BLUE,
     "New alert systems in Wallonia, tested in 2026;\nlonger forecasts and phone alerts in Germany"),
    ("Protection", "SLOW", "◔", EU_YELLOW,
     "Most Vesdre works start in 2026-27;\nTrooz and Verviers still wait for studies"),
    ("Shelter", "MISSING", "✕", RED,
     "No public list of flood shelters found in any municipality"),
    ("Building", "RISKY", "!", RED,
     "New homes planned in Trooz on land flooded by over 2 m in 2021"),
]
fig = plt.figure(figsize=(7.2, 3.7))
header(fig, "Since 2021, warnings have improved faster than protection",
       "What has changed in the Meuse and Vesdre region, five years on")
ax = fig.add_axes([0.04, 0.12, 0.92, 0.66]); ax.axis("off")
ax.set_xlim(0, 1); ax.set_ylim(0, 4)
for i, (topic, status, sym, col, text) in enumerate(rows):
    y = 3.5 - i
    ax.plot([0, 1], [y - 0.5, y - 0.5], color=RULE, lw=0.6)
    ax.text(0.0, y, topic, fontsize=11, fontweight="bold", va="center")
    fg = INK if col == EU_YELLOW else "white"
    ax.text(0.17, y, f"{sym}  {status}".ljust(12), color=fg, fontsize=8.5, fontweight="bold",
            va="center", fontfamily=["DejaVu Sans Mono"],
            bbox=dict(boxstyle="round,pad=0.55,rounding_size=0.3", fc=col, ec="none"))
    ax.text(0.37, y, text, fontsize=9, va="center", linespacing=1.4)
ax.plot([0, 1], [4, 4], color=RULE, lw=0.6)
footer(fig, ["Sources: Wallonia (26.06.2026); RTBF (15.07.2026); Gouvernement wallon (25.06.2026);",
             "Rhein-Zeitung/dpa (07.2026); Bezirksregierung Köln (17.06.2025)."])
save(fig, "fig3_since_2021")
print("written to", OUT)
