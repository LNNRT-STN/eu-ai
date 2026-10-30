"""Data & limits: where every number comes from and what it cannot tell you. First the return-period scenario of the
response pages (outputs/rp), then July 2021 (outputs/data, the "2021 vs today" page). Short grouped lists; the detail
of each row sits behind its ?, the 2021 data-quality table behind one expander."""
import streamlit as st

import anna
import core
import live
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

head, *_, qc = anna.load()  # the return-period zones (outputs/rp)
d = core.load(core.D2021)   # July 2021 (outputs/data)
summary = anna.load(anna.D2021)[5]
obs = summary[(summary.variant == "worst") & ~summary.area.isin(anna.MODELLED)].set_index("area")
first = summary[summary.variant == "main"].set_index("area")
twice = qc["qc"]["vesdre"]["exposed_already_counted_in_earlier_area"]

st.markdown("### :blue[:material/flood:] The flood scenario")
left, right = st.columns(2, gap="medium")
with left:
    heading(":blue[:material/database:] Sources",
            help="Built by notebooks/pipeline.py (FLOOD=rp) and notebooks/rp_extras.py into outputs/rp/. Full method: "
                 "docs/METHODOLOGY.md.")
    rows("src", [
        ("**Flood zones: EFAS flood hazard maps** :gray[· challenge]",
         "Copernicus EMS European Flood Awareness System, Joint Research Centre: the 10-, 100- and 500-year river "
         "flood maps, water deeper than 0.1 m. The crisis room switches them on; the plan follows the rarest one on."),
        ("**Buildings** :gray[· challenge]", "GHS-OBAT 2020, with height for floor volume and single-storey homes."),
        ("**Residents** :gray[· challenge]", "GHS-POP 2020, ~1 km cells, spread over each cell's homes by floor "
                                              "volume; 2025 is a projection."),
        ("**Municipalities** :gray[· external]", "Eurostat GISCO LAU 2021 (© EuroGeographics)."),
        ("**Shelter candidates, hospitals, care homes, schools** :gray[· external]",
         "OpenStreetMap (ODbL), Geofabrik extract of 29 Oct 2026. A shelter counts for a return period only when it "
         "is dry in that zone."),
        ("**Roads and addresses** :gray[· external]",
         "OpenStreetMap: the road network for routes out and closures, street addresses for homes and shelters."),
        ("**River and rain outlook** :gray[· external, live]", "Open-Meteo: GloFAS v4, forecast models, ERA5."),
    ])

with right:
    heading(":orange[:material/warning:] Limits", help="What each number cannot tell you. Hover a ? for why.")
    rows("lim", [
        ("**No dikes or flood walls in the model**",
         "EFAS floods the land behind defences as if they were not there. Along the Meuse at Liège and Venlo the "
         "zones and the people in them are an upper bound."),
        ("**Small rivers are missing**",
         "EFAS models rivers with a catchment of at least 500 km². Small streams, such as the Urft at Kall, and rain "
         "running off slopes are not in the zones: a home outside them is not guaranteed safe."),
        ("**A planning map, not one storm**",
         "Each map puts every river at that return period at once; a real flood hits some valleys, not all. It is "
         "not a forecast and not an official warning."),
        ("**The Vesdre is counted in the Liège area**",
         f"The two study boxes overlap: {fmt(twice)} buildings of the Vesdre box sit inside the Liège box and are "
         "counted there, once. The Vesdre's own rows show no buildings."),
        ("**Residents are an order of magnitude**",
         "GHS-POP cells spread over each cell's homes by floor volume. Inside the zone is not the same as damaged. "
         "No age data."),
        ("**Shelters are candidates, not official**",
         "OSM schools, sports halls and civic buildings with at least 200 m² of floor, dry in the zone of each return "
         "period. Capacity is floor area × usable share ÷ m² per person, not an official figure. Sites above "
         "20,000 m² (merged campuses, race circuits) count as 20,000 m². None is an official shelter."),
        ("**Walking reach is a straight line**",
         "1.5 km (1 and 2.5 km in the low and high cases). It understates walks in steep valleys and ignores flooded "
         "roads and bridges. People who cannot walk need transport."),
        ("**Care sites count from 5 % in the water**",
         "OSM hospitals, care homes and schools; only sites with at least 5 % of their area in the zone count."),
        ("**The outlook is a heads-up, not a warning**",
         "GloFAS (~5 km) handles the Meuse well, small valleys poorly. The ten river points are all in the Meuse "
         "basin: no outlook for the Ahr or Erft yet. Official warnings: SPW, Rijkswaterstaat, German state flood "
         "centres."),
    ])

st.space("small")
heading(":blue[:material/stacked_bar_chart:] What each flood covers",
        help="All ten study areas (outputs/rp/q4_headline.json). The zones nest: each holds nearly all of the more frequent ones.")
rows("rp", [(f"**{r}-year flood** :gray[· {c} chance in any year] · {fmt(m['buildings'])} buildings, "
             f"≈ {core.about(m['people'])} residents, {fmt(m['flood_km2'])} km² of water",
             f"≈ {core.about(m['bus_covered'])} residents have a candidate shelter place within 10 km by bus; "
             f"≈ {core.about(m['no_shelter'])} have none within walking reach (1.5 km).")
            for r, c in zip(live.RPS, ("10 %", "1 %", "0.2 %")) for m in [head[f"rp{r}"]["modelled"]]])

st.divider()
st.markdown("### :violet[:material/history:] July 2021 :gray[· the “2021 vs today” page]")
left, right = st.columns(2, gap="medium")
with left:
    heading(":blue[:material/database:] Sources",
            help="Cleaned files and their method: outputs/data/README.md.")
    rows("src21", [
        ("**Satellite flood map, July 2021** :gray[· challenge]",
         "Copernicus EMS Rapid Mapping (EMSR517 DE, EMSR518 BE, EMSR520 NL), first product and monitoring updates."),
        ("**Modelled Vesdre** :gray[· challenge]",
         "No satellite polygons in the valley: the EFAS 100-year zone stands in for the first pass, the 500-year zone "
         "for all passes."),
        ("**Measures and money since 2021** :gray[· external]",
         "Desk research, October 2026: official, water-authority and press sources, URL per row (docs/BUDGETS.md). "
         "Rows from a secondary source are marked partly verified."),
    ])
with right:
    heading(":orange[:material/warning:] Limits", help="What the 2021 numbers cannot tell you.")
    rows("lim21", [
        ("**2021 counts are a floor**",
         "The radar map shows water at overpass time, not at the peak, and saw little in narrow built-up valleys. "
         f"Ahr: {fmt(obs.loc['ahr'].buildings)} buildings with all passes vs over 9,000 reported (bpb, 2023)."),
        ("**The Vesdre is modelled, never added**", "Never added to observed 2021 totals."),
        ("**Two flood maps**", "“All satellite passes” is the headline; “first pass only” is a lower bound."),
    ])

st.space("small")
left, right = st.columns(2, gap="medium")
with left:
    heading(":green[:material/fact_check:] How we checked the numbers",
            help="Official figures verified at the source document. Every check, and every error the AI made and "
                 "how it was caught: ai_log.md. Code written with Claude (Claude Code), checked by the team.")
    be = obs.loc[["liege", "rochefort"]].buildings.sum()
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
    ])

with right:
    heading(":gray[:material/compare:] How far the return periods match 2021",
            help="Buildings inside both the 2021 satellite water and the EFAS zone, over the buildings in the "
                 "satellite water. In Liège the zone covers the whole city centre, the satellite saw little.")
    v = d["qc"]["efas_validation"]
    rows("val", [(f"**{anna.AREA.get(ar, ar)}** :gray[· 100-year finds {x['RP100']['recall']:.0%}, 500-year "
                  f"{x['RP500']['recall']:.0%}]",
                  f"Of the {fmt(x['RP100']['observed_flooded'])} buildings the satellite saw flooded, the 10-year zone "
                  f"holds {x['RP10']['recall']:.0%}, the 100-year {x['RP100']['recall']:.0%} and the 500-year "
                  f"{x['RP500']['recall']:.0%}; {fmt(x['RP100']['efas_flooded'])} buildings are in the 100-year zone.")
                 for ar, x in v.items()])

st.space("small")
dq = d["dq"][d["dq"].status == "WARN"]
with st.expander(f"2021 data-quality warnings · {len(dq)} of {len(d['dq'])} checks", icon=":material/rule:"):
    st.dataframe(dq[["area", "indicator", "value", "warn_above", "likely_cause", "who_can_fix"]], hide_index=True,
                 column_config={"area": st.column_config.TextColumn("Area", width="small"), "indicator": "Check",
                                "value": st.column_config.NumberColumn("Value", format="%.1f", width="small"),
                                "warn_above": st.column_config.NumberColumn("Warn above", format="%.1f", width="small"),
                                "likely_cause": "Likely cause", "who_can_fix": "Who can fix"})
