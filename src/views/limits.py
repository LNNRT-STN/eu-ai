import streamlit as st

import anna
import core
from core import fmt

core.style()  # the older analyst pages keep their custom look; the main pages use the theme only

core.header("Data & limits", "What every number on this dashboard comes from, and what it cannot tell you.")
st.space("small")

d = core.load()
core.group([
    ("Satellite flood map, July 2021", "Copernicus EMS Rapid Mapping (EMSR517 DE, EMSR518 BE, EMSR520 NL), first "
     "product and monitoring updates", "Challenge"),
    ("Modelled flood zones", "CEMS-EFAS 100- and 500-year maps: the Vesdre valley and the shelter screen", "Challenge"),
    ("Buildings", "GHS-OBAT 2020, with height for floor volume", "Challenge"),
    ("Residents", "GHS-POP 2020, ~1 km cells; 2025 is a projection", "Challenge"),
    ("Municipalities", "Eurostat GISCO LAU 2021 (© EuroGeographics)", "External"),
    ("Schools, sports halls, civic buildings, hospitals, care homes", "OpenStreetMap (ODbL), Geofabrik 29 Oct 2026",
     "External"),
    ("River and rain outlook", "Open-Meteo: GloFAS v4, forecast models, ERA5", "External, live"),
], "Sources", "Cleaned files and their method: outputs/data/README.md.")
st.space("small")

limits = [
    ("2021 counts are a floor", "The radar map shows water at overpass time, not at the peak, and saw little in narrow "
     "built-up valleys. Ahr: 7,202 buildings with all passes vs over 9,000 reported (bpb, 2023)."),
    ("Two flood maps", "“All satellite passes” is the headline; “first pass only” is a lower bound."),
    ("The Vesdre is modelled", "No satellite polygons in the valley, so the EFAS 100-year (first pass view) and "
     "500-year (all passes) zones stand in. Never added to observed totals."),
    ("Residents are an order of magnitude", "GHS-POP cells spread over each cell's homes by floor volume. Inside the "
     "water is not the same as damaged. No age data."),
    ("Shelters are candidates", "OSM schools, sports halls and civic buildings with at least 200 m² of floor, dry in "
     "2021 and outside the EFAS 100-year zone. Capacity is floor area × usable share ÷ m² per person, not an official "
     "figure. Sites above 20,000 m² (merged campuses, race circuits) count as 20,000 m²; the First action page caps "
     "oversized floors at the outlier fence instead. None is an official shelter."),
    ("Walking reach is a straight line", "1.5 km (1 and 2.5 km in the low and high cases). It understates walks in steep "
     "valleys and ignores flooded roads and bridges. People who cannot walk need transport."),
    ("The 100-year zone is a model", "EFAS ignores dikes and flood walls (overstates exposure in Dutch Limburg) and skips "
     "streams under 500 km². It is not a forecast."),
    ("Care sites", "OSM hospitals, care homes and schools; only sites with at least 5 % of their area in the water count."),
    ("The outlook is a heads-up", "GloFAS (~5 km) handles the Meuse well, small valleys poorly; it puts the 2021 Vesdre "
     "peak far below what was observed. The ten river points are all in the Meuse basin: no outlook for the Ahr or "
     "Erft yet. Official warnings: SPW, Rijkswaterstaat, German state flood centres."),
]
core.group([(f"<b>{t}</b>", d_, "") for t, d_ in limits], "Limits")
st.space("small")

v = d["qc"]["efas_validation"]
core.group([(f"<b>{a.capitalize()}</b>", f"EFAS 100-year zone finds {x['recall']:.0%} of the {fmt(x['observed_flooded'])} "
             f"buildings the satellite saw flooded", f"{fmt(x['efas_flooded'])} in the zone")
            for a, x in ((a, r["RP100"]) for a, r in v.items())],
           "How far the model matches 2021",
           "Why the modelled Vesdre is a stand-in, not a measurement. In Liège the model zone covers the whole city "
           "centre, the satellite saw little.")
st.space("small")

dq = d["dq"][d["dq"].status == "WARN"]
st.html("<div class='gh'>Data-quality warnings · " + f"{len(dq)} of {len(d['dq'])} checks</div>")
st.dataframe(dq[["area", "indicator", "value", "warn_above", "likely_cause", "who_can_fix"]], hide_index=True,
             column_config={"area": st.column_config.TextColumn("Area", width="small"), "indicator": "Check",
                            "value": st.column_config.NumberColumn("Value", format="%.1f", width="small"),
                            "warn_above": st.column_config.NumberColumn("Warn above", format="%.1f", width="small"),
                            "likely_cause": "Likely cause", "who_can_fix": "Who can fix"})
st.space("small")

# how the numbers were checked: official figures first (outside view), then the model against the satellite
head, towns, crit, shel, flood, summary, qc = anna.load()
obs = summary[(summary.variant == "worst") & ~summary.area.isin(anna.MODELLED)].set_index("area")
first = summary[summary.variant == "main"].set_index("area")
be = obs.loc[["liege", "rochefort"]].buildings.sum()
val = qc["efas_validation"]["ahr"]["RP100"]
core.group([
    ("<b>Ahr</b>", f"{core.fmt(obs.loc['ahr'].buildings)} buildings in the satellite water (all passes; "
                   f"{core.fmt(first.loc['ahr'].buildings)} with the first pass). Official: "
                   f"{anna.OFFICIAL['ahr'][0]} ({anna.OFFICIAL['ahr'][1]}).", "Lower, as expected"),
    ("<b>Wallonia</b>", f"{core.fmt(be)} buildings in the satellite water. Official: {anna.OFFICIAL['wallonia'][0]} "
                        f"({anna.OFFICIAL['wallonia'][1]}).", "Satellite misses most"),
    ("<b>Venlo</b>", f"{core.fmt(obs.loc['venlo'].people_2020)} residents in the satellite water. Official: "
                     f"{anna.OFFICIAL['venlo'][0]} ({anna.OFFICIAL['venlo'][1]}).", "Not comparable"),
    ("<b>100-year model vs 2021, Ahr</b>", f"The model floods {val['recall']:.0%} of the buildings the satellite saw "
                                           f"flooded; {val['precision']:.0%} of the buildings it floods were seen "
                                           "flooded. 2021 went beyond the model.", "Rough proxy"),
], "How we checked the numbers", "Official figures verified at the source document. Every check, and every error "
                                 "the AI made and how it was caught: ai_log.md.")
st.caption("Full method: outputs/data/README.md and docs/METHODOLOGY.md. Code written with Claude (Claude Code), "
           "checked by the team; see the AI sheet.")
