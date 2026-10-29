import streamlit as st

import anna
import core

core.header("Data & limits", "What every number on this dashboard comes from, and what it cannot tell you.")
st.space("small")

core.group([
    ("Satellite flood map, July 2021", "Copernicus EMS Rapid Mapping (EMSR518 BE, EMSR520 NL, EMSR517 DE)", "Challenge"),
    ("Modelled 100-year flood zone", "CEMS-EFAS flood hazard map", "Challenge"),
    ("Buildings", "GHS-OBAT 2020, points with use", "Challenge"),
    ("Residents", "GHS-POP 2020, ~1 km cells", "Challenge"),
    ("Communes", "Eurostat GISCO LAU 2021 (© EuroGeographics)", "External"),
    ("Schools, town halls, hospitals, care homes", "OpenStreetMap (ODbL)", "External"),
    ("River and rain outlook", "Open-Meteo: GloFAS v4, forecast models, ERA5", "External, live"),
], "Sources")
st.space("small")

limits = [
    ("2021 counts are a floor", "The radar map shows water at overpass time, not at the peak, and saw little in narrow "
     "built-up valleys (Vesdre, central Liège)."),
    ("The 100-year zone is a model", "EFAS ignores dikes and flood walls (overstates exposure in Dutch Limburg) and skips "
     "streams under 500 km². It is not a forecast."),
    ("Residents are an order of magnitude", "GHS-POP cells are spread over the residential buildings in each cell by "
     "floor volume (footprint × storeys, oversized footprints capped). An equal split put 1 person per 2.5–5 m² into 1 % "
     "of homes. Inside the water is not the same as damaged."),
    ("Shelters are candidates", "Meuse pages: schools and town halls that stayed dry in 2021 and sit outside the EFAS 10- "
     "and 100-year zones. First action page: schools, sports halls and civic buildings, dry in 2021 and in the 100-year "
     "model, with capacity estimated from floor area (4 m² per person, 50 % usable; low and high cases 5 and 3 m²). "
     "None is an official shelter."),
    ("Walking reach is a straight line", "1.5 km as the crow flies (1 and 2.5 km in the low and high cases). Roads in "
     "steep valleys are longer, and people who cannot walk need transport."),
    ("The Vesdre is modelled", "The satellite map has no flood polygons in the Vesdre valley: the nearest is 7–15 km "
     "from Pepinster. The First action page uses the EFAS 100-year zone there, labelled as a model."),
    ("Care sites at risk", "OSM hospitals and care homes inside or within 100 m of the 2021 water, or in the 10- or "
     "100-year zone. OSM coverage varies by country."),
    ("The outlook is a heads-up", "GloFAS (~5 km) handles the Meuse well, small valleys poorly; it puts the 2021 Vesdre "
     "peak far below what was observed. Thresholds: 2-year flood = median annual peak 2011–2020; July 2021 = the "
     "model's own peak. Official warnings: SPW, Rijkswaterstaat, German state flood centres."),
    ("Why the priority score is a rule, not a model", "We tested a LightGBM model trained on the 2021 satellite map. "
     "Tested on areas it had not seen, it did no better than the EFAS 100-year zone on its own (AUC 0.796 vs 0.798) and "
     "ranked the under-mapped Vesdre communes lower. So the score stays a rule you can redo by hand. Detail: docs/ML.md."),
    ("Commune impact colours are relative", "Hit communes ranked on residents, buildings and share of population, then "
     "split into quarters. “Severe” means worst quarter here, not a damage threshold."),
]
core.group([(f"<b>{t}</b>", d, "") for t, d in limits], "Limits")
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
st.caption("Full method: docs/METHODOLOGY.md. Code written with Claude (Claude Code), checked by the team; see the AI sheet.")
