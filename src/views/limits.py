import streamlit as st

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
    ("Residents are an order of magnitude", "GHS-POP cells are spread equally over the residential buildings in each cell. "
     "Buildings are points, not footprints; inside the water is not the same as damaged."),
    ("Shelters are candidates", "Schools and town halls that stayed dry in 2021 (not within 100 m of the mapped water) "
     "and sit outside the EFAS 10- and 100-year zones. No capacity, accessibility or official designation. OSM has no "
     "sites for the Eschweiler area."),
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
st.caption("Full method: docs/METHODOLOGY.md. Code written with Claude (Claude Code), checked by the team; see the AI sheet.")
