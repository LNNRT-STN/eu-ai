"""Data & limits: where every number comes from and what it cannot tell you. Four short grouped lists; the detail of
each row sits behind its ?, the data-quality table behind one expander."""
import streamlit as st

import anna
import core
from core import fmt

core.style()  # page header and the white grouped lists
# a list of rows with a ? each: one white group, tight rows
st.html("""<style>
[class*=st-key-lst-]{background:#fff;border-radius:12px;padding:.8rem 1rem!important;gap:.6rem!important;height:auto!important;overflow:visible!important}
[class*=st-key-lst-] [data-testid=stMarkdownContainer]{margin-bottom:0!important}
[class*=st-key-lst-] [data-testid=stMarkdownContainer] p{margin:0}
</style>""")


def heading(title, help):
    st.markdown(f"#### {title}", help=help)


def rows(key, items):
    """items: (visible line, detail behind the ?)."""
    with st.container(key=f"lst-{key}"):
        for line, detail in items:
            st.markdown(line, help=detail)


core.header("Data & limits", "What every number on this dashboard comes from, and what it cannot tell you.")
st.space("small")

d = core.load()
head, towns, crit, shel, flood, summary, qc = anna.load()
obs = summary[(summary.variant == "worst") & ~summary.area.isin(anna.MODELLED)].set_index("area")
first = summary[summary.variant == "main"].set_index("area")

left, right = st.columns(2, gap="medium")
with left:
    heading(":blue[:material/database:] Sources",
                 help="Cleaned files and their method: outputs/data/README.md. Full method: docs/METHODOLOGY.md.")
    rows("src", [
        ("**Satellite flood map, July 2021** :gray[· challenge]",
         "Copernicus EMS Rapid Mapping (EMSR517 DE, EMSR518 BE, EMSR520 NL), first product and monitoring updates."),
        ("**Modelled flood zones** :gray[· challenge]",
         "CEMS-EFAS 100- and 500-year maps: the Vesdre valley and the shelter screen."),
        ("**Buildings** :gray[· challenge]", "GHS-OBAT 2020, with height for floor volume."),
        ("**Residents** :gray[· challenge]", "GHS-POP 2020, ~1 km cells; 2025 is a projection."),
        ("**Municipalities** :gray[· external]", "Eurostat GISCO LAU 2021 (© EuroGeographics)."),
        ("**Shelter candidates, hospitals, care homes, schools** :gray[· external]",
         "OpenStreetMap (ODbL), Geofabrik extract of 29 Oct 2026: schools, sports halls, civic buildings, hospitals, "
         "care homes."),
        ("**River and rain outlook** :gray[· external, live]", "Open-Meteo: GloFAS v4, forecast models, ERA5."),
        ("**Measures and money since 2021** :gray[· external]",
         "Desk research, October 2026: official, water-authority and press sources, URL per row (docs/BUDGETS.md). "
         "Rows from a secondary source are marked partly verified."),
    ])

with right:
    heading(":orange[:material/warning:] Limits", help="What each number cannot tell you. Hover a ? for why.")
    rows("lim", [
        ("**2021 counts are a floor**",
         "The radar map shows water at overpass time, not at the peak, and saw little in narrow built-up valleys. "
         f"Ahr: {fmt(obs.loc['ahr'].buildings)} buildings with all passes vs over 9,000 reported (bpb, 2023)."),
        ("**The Vesdre is modelled, never added**",
         "No satellite polygons in the valley, so the EFAS 100-year (first pass view) and 500-year (all passes) zones "
         "stand in. Never added to observed totals."),
        ("**Two flood maps**", "“All satellite passes” is the headline; “first pass only” is a lower bound."),
        ("**Residents are an order of magnitude**",
         "GHS-POP cells spread over each cell's homes by floor volume. Inside the water is not the same as damaged. "
         "No age data."),
        ("**Shelters are candidates, not official**",
         "OSM schools, sports halls and civic buildings with at least 200 m² of floor, dry in 2021 and outside the "
         "EFAS 100-year zone. Capacity is floor area × usable share ÷ m² per person, not an official figure. Sites "
         "above 20,000 m² (merged campuses, race circuits) count as 20,000 m²; the First action view caps oversized "
         "floors at the outlier fence instead. None is an official shelter."),
        ("**Walking reach is a straight line**",
         "1.5 km (1 and 2.5 km in the low and high cases). It understates walks in steep valleys and ignores flooded "
         "roads and bridges. People who cannot walk need transport."),
        ("**The 100-year zone is a model, not a forecast**",
         "EFAS ignores dikes and flood walls (overstates exposure in Dutch Limburg) and skips streams under 500 km²."),
        ("**Care sites count from 5 % in the water**",
         "OSM hospitals, care homes and schools; only sites with at least 5 % of their area in the water count."),
        ("**The outlook is a heads-up, not a warning**",
         "GloFAS (~5 km) handles the Meuse well, small valleys poorly; it puts the 2021 Vesdre peak far below what was "
         "observed. The ten river points are all in the Meuse basin: no outlook for the Ahr or Erft yet. Official "
         "warnings: SPW, Rijkswaterstaat, German state flood centres."),
        ("**The drill is a replay**",
         "The river flows are those of 12–17 July 2021, modelled afterwards (GloFAS), shown as if they started today. "
         "Only the dates move."),
    ])

st.space("small")
left, right = st.columns(2, gap="medium")
with left:
    heading(":green[:material/fact_check:] How we checked the numbers",
                 help="Official figures verified at the source document. Every check, and every error the AI made and "
                      "how it was caught: ai_log.md. Code written with Claude (Claude Code), checked by the team.")
    be = obs.loc[["liege", "rochefort"]].buildings.sum()
    val = qc["efas_validation"]["ahr"]["RP100"]
    rows("chk", [
        ("**Ahr** :gray[· lower than official, as expected]",
         f"{fmt(obs.loc['ahr'].buildings)} buildings in the satellite water (all passes; "
         f"{fmt(first.loc['ahr'].buildings)} with the first pass). Official: {anna.OFFICIAL['ahr'][0]} "
         f"({anna.OFFICIAL['ahr'][1]})."),
        ("**Wallonia** :gray[· the satellite misses most]",
         f"{fmt(be)} buildings in the satellite water. Official: {anna.OFFICIAL['wallonia'][0]} "
         f"({anna.OFFICIAL['wallonia'][1]})."),
        ("**Venlo** :gray[· not comparable]",
         f"{fmt(obs.loc['venlo'].people_2020)} residents in the satellite water. Official: {anna.OFFICIAL['venlo'][0]} "
         f"({anna.OFFICIAL['venlo'][1]})."),
        ("**100-year model vs 2021, Ahr** :gray[· rough proxy]",
         f"The model floods {val['recall']:.0%} of the buildings the satellite saw flooded; {val['precision']:.0%} of "
         "the buildings it floods were seen flooded. 2021 went beyond the model."),
    ])

with right:
    heading(":gray[:material/compare:] How far the model matches 2021",
                 help="Why the modelled Vesdre is a stand-in, not a measurement. In Liège the model zone covers the "
                      "whole city centre, the satellite saw little.")
    v = d["qc"]["efas_validation"]
    rows("val", [(f"**{ar.capitalize()}** :gray[· finds {x['recall']:.0%}]",
                  f"The EFAS 100-year zone finds {x['recall']:.0%} of the {fmt(x['observed_flooded'])} buildings the "
                  f"satellite saw flooded; {fmt(x['efas_flooded'])} buildings are in the zone.")
                 for ar, x in ((ar, r["RP100"]) for ar, r in v.items())])

st.space("small")
dq = d["dq"][d["dq"].status == "WARN"]
with st.expander(f"Data-quality warnings · {len(dq)} of {len(d['dq'])} checks", icon=":material/rule:"):
    st.dataframe(dq[["area", "indicator", "value", "warn_above", "likely_cause", "who_can_fix"]], hide_index=True,
                 column_config={"area": st.column_config.TextColumn("Area", width="small"), "indicator": "Check",
                                "value": st.column_config.NumberColumn("Value", format="%.1f", width="small"),
                                "warn_above": st.column_config.NumberColumn("Warn above", format="%.1f", width="small"),
                                "likely_cause": "Likely cause", "who_can_fix": "Who can fix"})
