"""Figures for the policy brief 'From warning to safety' (EU visual style).

Reads outputs/data/, writes outputs/charts/report/fig*.png (300 dpi) and .svg.
Run: python notebooks/report_charts.py
"""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from chart_style import INK, MUTED, NAVY as EU_BLUE, NAVY_MID as BLUE_MID, NAVY_PALE as BLUE_PALE, RED, RULE, \
    YELLOW as EU_YELLOW, heading, note, save as _save  # noqa: E402

DATA = ROOT / "outputs" / "data"
OUT = ROOT / "outputs" / "charts" / "report"

SOURCE = ("Source: Copernicus EMS (EMSR517/518/520), EFAS, GHS-POP, GHS-OBAT (JRC); "
          "OpenStreetMap 29.10.2026. Team 5 analysis.")


def k(n):
    return f"{round(n, -2):,.0f}"


def header(fig, title, subtitle):
    heading(fig, title, subtitle, fig.get_figheight())


def footer(fig, lines):
    note(fig, "\n".join(lines), fig.get_figheight())


def save(fig, name):
    _save(fig, OUT, name)


def clean(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)


def key(fig, rect, items, size=0.022):
    """Legend row: square swatch + words, at fixed offsets so it lines up with the bars below."""
    lg = fig.add_axes(rect); lg.axis("off")
    for x, c, lab in items:
        lg.add_patch(FancyBboxPatch((x, 0.25), size, 0.5, boxstyle="square,pad=0", color=c, transform=lg.transAxes))
        lg.text(x + size + 0.01, 0.5, lab, va="center", fontsize=8.5, transform=lg.transAxes)
    return lg


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
ax = fig.add_axes([0.20, 0.19, 0.62, 0.56])
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
    ax.text(total + 70, y, lab, va="center", fontsize=9.5,
            fontweight="bold" if strong else "normal", color=INK if strong else MUTED)
ax.set_yticks(ys, towns.label, fontsize=10)
for t, y in zip(ax.get_yticklabels(), ys):
    t.set_fontweight("bold" if y > 2 else "normal")
    t.set_color(INK if y > 2 else MUTED)
ax.set_xlim(0, 5000)
ax.set_ylim(-0.6, 6.25)
ax.set_xticks([])
clean(ax)
ax.text(-0.27, 1.55, "For comparison", transform=ax.get_yaxis_transform(), fontsize=8.5, color=MUTED)
# Trooz callout
trooz = towns.set_index("label").loc["Trooz"]
ax.text((trooz.covered + trooz.covered + trooz.full) / 2, 4.6,
        f"only {trooz.covered:,.0f} of {trooz.people:,.0f} have a place",
        fontsize=8, color="white", va="center", ha="center", fontweight="bold")
key(fig, [0.20, 0.765, 0.76, 0.05], [(0, BLUE_PALE, "Has a place"), (0.21, EU_BLUE, "Shelter nearby, but full"),
                                     (0.53, BLUE_MID, "No shelter within 20 min walk")])
footer(fig, ["Vesdre flood area modelled (EFAS 100-year flood); satellites missed most of the 2021 water here.",
             "Shelters: schools, sports halls, town halls that stayed dry; candidates, not official. "
             "Central estimate; residents are an order of magnitude.",
             SOURCE])
save(fig, "fig1_priority_towns")

# ---------------------------------------------------------------- Figure 2
# Headline with ranges; observed and modelled kept in separate panels
obs, ves = head["worst"]["observed"], head["main"]["modelled_vesdre"]
fig = plt.figure(figsize=(7.2, 4.3))
header(fig, "Most people left without a place live near a shelter that is full",
       "Residents without a shelter place if the 2021 flood returned, central estimate and range")
panels = [
    ("Where satellites mapped the 2021 flood", "Ahr, Schleiden, Liège, Venlo and 5 more areas (observed)", obs),
    ("Vesdre valley", "once-a-century flood map (modelled)", ves),
]
XMAX = 33000
key(fig, [0.04, 0.74, 0.92, 0.05], [(0, EU_BLUE, "Shelter nearby, but full"),
                                    (0.27, BLUE_MID, "No shelter within 20 min walk")])
lg = fig.axes[-1]
lg.plot([0.585, 0.585, 0.615, 0.615], [0.38, 0.62, 0.62, 0.38], color=INK, lw=0.9, transform=lg.transAxes)
lg.text(0.63, 0.5, "Range, low to high assumptions", va="center", fontsize=8.5, transform=lg.transAxes)
for i, (t, sub, d) in enumerate(panels):
    ax = fig.add_axes([0.04, 0.47 - i * 0.29, 0.92, 0.11])
    clean(ax)
    ax.set_xlim(0, XMAX); ax.set_ylim(-0.6, 0.9); ax.set_xticks([]); ax.set_yticks([])
    lo, hi = d["no_shelter_range"]
    ax.plot([lo, lo, hi, hi], [0.42, 0.62, 0.62, 0.42], color=INK, lw=0.9)
    ax.barh(0, d["full"], 0.62, color=EU_BLUE, edgecolor="white", lw=0.8)
    ax.barh(0, d["too_far"], 0.62, left=d["full"], color=BLUE_MID, edgecolor="white", lw=0.8)
    ax.text(0, 1.75, t, fontsize=10, fontweight="bold", transform=ax.get_xaxis_transform())
    ax.text(0, 1.38, sub, fontsize=8.5, color=MUTED, transform=ax.get_xaxis_transform())
    x = max(hi, d["no_shelter"]) + 600
    ax.text(x, 0.18, k(d["no_shelter"]), fontsize=16, fontweight="bold", color=EU_BLUE, va="center")
    ax.text(x, -0.42, f"range {k(lo)} to {k(hi)}", fontsize=8, color=MUTED, va="center")
    share = d["full"] / d["no_shelter"]
    ax.text(d["full"] / 2, 0, f"{share:.0%} near a full shelter" if d["full"] > 9000 else f"{share:.0%}",
            color="white", fontsize=8.5, va="center", ha="center", fontweight="bold")
    if i == 1:
        ax.text(hi + 7500, 0.18, f"+{k(ves['coordination_gain'])} places", fontsize=10, fontweight="bold",
                va="center")
        ax.text(hi + 7500, -0.42, "if towns share shelters across borders", fontsize=8, color=MUTED, va="center")
footer(fig, ["The two estimates use different flood maps and are not added together. Range: shelter space 3-5 m² "
             "per person, walk 1-2.5 km.", SOURCE])
save(fig, "fig2_headline_ranges")

# ---------------------------------------------------------------- Figure 3
# Since 2021: four-line status board (symbol + word, never colour alone)
rows = [
    ("Warning", "Better", EU_BLUE,
     "New alert systems in Wallonia, tested in 2026;\nlonger forecasts and phone alerts in Germany"),
    ("Protection", "Slow", EU_YELLOW,
     "Most Vesdre works start in 2026-27;\nTrooz and Verviers still wait for studies"),
    ("Shelter", "Missing", RED,
     "No public list of flood shelters found in any municipality"),
    ("Building", "Risky", RED,
     "New homes planned in Trooz on land flooded by over 2 m in 2021"),
]
fig = plt.figure(figsize=(7.2, 3.7))
header(fig, "Since 2021, warnings have improved faster than protection",
       "What has changed in the Meuse and Vesdre region, five years on")
ax = fig.add_axes([0.04, 0.15, 0.92, 0.6]); ax.axis("off")
ax.set_xlim(0, 1); ax.set_ylim(0, 4)
for i, (topic, status, col, text) in enumerate(rows):
    y = 3.5 - i
    if i:
        ax.plot([0, 1], [y + 0.5, y + 0.5], color=RULE, lw=0.6)
    ax.text(0.0, y, topic, fontsize=10.5, fontweight="bold", va="center")
    ax.add_patch(FancyBboxPatch((0.17, y - 0.17), 0.11, 0.34, boxstyle="square,pad=0", fc=col, ec="none"))
    ax.text(0.225, y, status, color=INK if col == EU_YELLOW else "white", fontsize=9, fontweight="bold",
            va="center", ha="center")
    ax.text(0.33, y, text, fontsize=9.5, va="center", linespacing=1.45)
footer(fig, ["Sources: Wallonia (26.06.2026); RTBF (15.07.2026); Gouvernement wallon (25.06.2026);",
             "Rhein-Zeitung/dpa (07.2026); Bezirksregierung Köln (17.06.2025)."])
save(fig, "fig3_since_2021")
print("written to", OUT)
