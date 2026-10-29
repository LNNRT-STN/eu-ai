"""Evacuation plan, one town at a time: if the July 2021 water came back, who leaves, which dry shelter they go to,
who gives the order, and the message that tells them. Answers the 2021 failures the team listed: unclear roles across
levels, warnings that never became instructions, missing local plans and drills, people who could not leave alone.
Numbers: outputs/data/ (app_towns: walking plan; bus_plan: the 10 km max-flow plan, per shelter; critical_sites;
receiving_sites). The roles and the message are team text, not data: labelled on the page and in the download."""
from datetime import date
from html import escape

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
import forecast
from core import about, fmt

head, towns, crit, shel, flood, *_ = anna.load()
recv, bus = anna.load_moves()
V = "worst"                       # the bus plan exists only for all satellite passes (EFAS 500-year for the Vesdre)
T = (towns[(towns.variant == V) & (towns.people >= 10)].sort_values("people", ascending=False).reset_index(drop=True))
CC = {"BE": "Belgium", "NL": "Netherlands", "DE": "Germany"}

# Who does what, per country. Team summary of the national crisis rules, not challenge data: check it against the
# municipality's own emergency plan. (role, who, how)
CHAIN = {
    "BE": [("Warns of the flood", "Wallonia's hydrological service (SPW) for rivers; the Royal Meteorological "
            "Institute for rain", "Flood and weather alerts to the governor and the mayors"),
           ("Orders the evacuation", "The mayor (municipal phase). The provincial governor takes over when several "
            "municipalities are hit; the Interior Minister, supported by the National Crisis Centre, in the federal phase",
            "Write down now who has the authority at each phase, and their deputy"),
           ("Alerts residents", "Mayor, governor or Interior Minister", "BE-Alert text and call, door-to-door for those not reached"),
           ("Opens the shelters", "Municipality, with its emergency planning officer", "Keys, staff, beds, food")],
    "NL": [("Warns of the flood", "Rijkswaterstaat for the Meuse; the water board for smaller rivers; KNMI for rain",
            "Warnings to the safety region and the mayors"),
           ("Orders the evacuation", "The mayor; the chair of the safety region when more than one municipality is hit",
            "Write down who decides and their deputy"),
           ("Alerts residents", "Safety region, for the mayor", "NL-Alert, sirens, door-to-door"),
           ("Opens the shelters", "Municipality, with the safety region", "Keys, staff, beds, food")],
    "DE": [("Warns of the flood", "The state flood service (Rhineland-Palatinate: LfU; North Rhine-Westphalia: LANUK and the district "
            "governments) for rivers; the German Weather Service for rain",
            "Warnings to the district and the municipalities"),
           ("Orders the evacuation", "The district (Kreis) or independent city as disaster-protection authority, led "
            "by the Landrat or mayor; the municipality for a local danger", "Write down who declares the disaster and orders the evacuation, and their deputy"),
           ("Alerts residents", "District and municipality", "Cell broadcast, NINA app, sirens, loudspeaker vans"),
           ("Opens the shelters", "Municipality, with the district", "Keys, staff, beds, food")],
}

# Draft evacuation message. Team-written template (AI-assisted, ai_log.md 15); have a native speaker check it.
MSG = {
    "English": ("FLOOD WARNING – {town}. The river may flood the streets that flooded in July 2021. Leave now. "
                "Take medicines, ID papers and a phone charger. Go to a shelter on higher ground: {near}. "
                "Cannot leave on your own? Call {line}. A bus will take you to {far}. "
                "Check on neighbours who are old, ill or alone. Never walk or drive through flood water."),
    "Français": ("ALERTE INONDATION – {town}. La rivière risque d'inonder les rues déjà touchées en juillet 2021. "
                 "Quittez votre domicile maintenant. Prenez vos médicaments, vos papiers d'identité et un chargeur de "
                 "téléphone. Rendez-vous dans un centre d'accueil situé en hauteur : {near}. Vous ne pouvez pas partir "
                 "par vos propres moyens ? Appelez le {line}. Un bus vous conduira à {far}. Prenez des nouvelles de vos "
                 "voisins âgés, malades ou isolés. Ne traversez jamais une zone inondée, ni à pied ni en voiture."),
    "Deutsch": ("HOCHWASSERWARNUNG – {town}. Der Fluss kann die Straßen überfluten, die im Juli 2021 unter Wasser "
                "standen. Verlassen Sie jetzt Ihr Haus. Nehmen Sie Medikamente, Ausweis und Handy-Ladegerät mit. "
                "Gehen Sie zu einer höher gelegenen Notunterkunft: {near}. Können Sie nicht selbst gehen? Rufen Sie "
                "{line} an. Ein Bus bringt Sie zu {far}. Sehen Sie nach älteren, kranken oder alleinlebenden "
                "Nachbarn. Gehen oder fahren Sie niemals durch Hochwasser."),
    "Nederlands": ("WAARSCHUWING OVERSTROMING – {town}. De rivier kan de straten overstromen die in juli 2021 onder water "
                   "stonden. Vertrek nu. Neem medicijnen, uw identiteitsbewijs en een oplader mee. Ga naar een hoger "
                   "gelegen opvanglocatie: {near}. Kunt u niet zelf weg? Bel {line}. Een bus brengt u naar {far}. Kijk "
                   "om naar buren die oud, ziek of alleen zijn. Loop of rijd nooit door overstromingswater."),
}
OR = {"English": " or ", "Français": " ou ", "Deutsch": " oder ", "Nederlands": " of "}
OFFICIAL = {"BE": "SPW (hydrometrie.wallonie.be)", "NL": "Rijkswaterstaat and the water board",
            "DE": "the state flood centre (hochwasser.rlp.de, hochwasserportal.nrw)"}
LOCAL_LANG = {"BE": "Français", "NL": "Nederlands", "DE": "Deutsch"}

# Before the season: the contingency steps 2021 showed missing. Team text.
PREPARE = ["Confirm each shelter with its owner: keys, a 24/7 contact, beds, food, step-free access.",
           "Agree the buses with a transport operator, and where they pick people up.",
           "Keep a list of residents who cannot leave on their own (kept by the municipality, not in this tool).",
           "Name who orders the evacuation and a deputy, for every crisis phase.",
           "Run a drill: send the message, open one shelter, time it."]

st.html("""<style>
.ev-n{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}
.ev-n div{background:#fff;border-radius:14px;padding:.9rem 1.1rem}
.ev-n b{display:block;font-size:2rem;font-weight:700;letter-spacing:-.03em;line-height:1.05;font-variant-numeric:tabular-nums}
.ev-n span{display:block;margin-top:.25rem;color:#6e6e73;font-size:.92rem;line-height:1.35}
.ev-n i{font-style:normal;color:#1d1d1f;font-weight:600}
.ev-msg{background:#fff;border-radius:14px;padding:1rem 1.2rem;font-size:1.02rem;line-height:1.5;color:#1d1d1f;max-width:75ch}
.ev-river{display:flex;gap:.6rem;align-items:baseline;margin:0;color:#6e6e73;font-size:.92rem;line-height:1.45}
.ev-river i{flex:none;width:.7rem;height:.7rem;border-radius:50%;transform:translateY(.05rem)}
.ev-river b{color:#1d1d1f;font-weight:600}
@media (max-width:900px){.ev-n{grid-template-columns:1fr}}
</style>""")

core.header("Evacuation plan", "If the July 2021 flood came back: who leaves, which dry shelter they go to, "
            "who gives the order.")
st.space("small")


# Who Anna calls: the authority that orders an evacuation across municipalities, per study area (team summary of the
# administrative map; check against the emergency plan). The mayor is called too.
CALL = {"ahr": "Kreis Ahrweiler", "erftstadt": "Rhein-Erft-Kreis", "schleiden": "Kreis Euskirchen",
        "euskirchen": "Kreis Euskirchen", "eschweiler": "StädteRegion Aachen", "wassenberg": "Kreis Heinsberg",
        "venlo": "Safety region Limburg-Noord", "liege": "Province of Liège (governor)",
        "vesdre": "Province of Liège (governor)", "rochefort": "Province of Namur (governor)"}
cs_all = crit[crit.in_worst_flood.astype(bool) & crit.share_of_site_flooded.ge(.05) & crit.type.isin(["hospital", "care home"])]
first_n = cs_all.groupby(["area", "municipality"]).size()
calls = (T.assign(care=[int(first_n.get((a, m), 0)) for a, m in zip(T.area, T.municipality)], call=T.area.map(CALL),
                  short=T.label.str.replace(" (modelled)", " *"))
         .sort_values(["no_shelter", "care"], ascending=False).head(6))


def pick_call():
    rows = st.session_state.ev_calls.selection.rows
    if rows:
        st.session_state.ev_town = int(calls.index[rows[0]])


st.html("<div class='gh'>First action: call these towns, in this order</div>")
st.dataframe(calls[["short", "call", "no_shelter", "care"]].assign(no_shelter=calls.no_shelter.map(about)),
             hide_index=True, key="ev_calls", on_select=pick_call, selection_mode="single-row",
             column_config={"short": st.column_config.TextColumn("Town (and its mayor)"),
                            "call": st.column_config.TextColumn("Also call"),
                            "no_shelter": st.column_config.TextColumn("No shelter on foot",
                                                                      help="Residents in the 2021 water with no free "
                                                                           "shelter place within 1.5 km"),
                            "care": st.column_config.NumberColumn("Care sites to evacuate", format="%d")})
st.html("<p class='asof'>Ordered by residents with no shelter place on foot: they need transport, so these calls take "
        "longest to act on. * modelled (Vesdre). Click a town to open its plan below.</p>")
st.space("small")


def option(i):
    r = T.iloc[i]
    return f"{r.label} · {about(r.people)} residents in the 2021 water"


i = st.selectbox("Town", range(len(T)), format_func=option, key="ev_town")
t = T.iloc[i]
cc = t.municipality[-3:-1]
modelled = t.area in anna.MODELLED

# ------------------------------------------------------------------ where the people go (10 km max-flow plan)
plan = bus[(bus.municipality == t.municipality) & (bus.area == t.area)].copy()
plan["km"] = core.km(t.lon, t.lat, plan.s_lon, plan.s_lat).round(1)
others = bus[bus.municipality != t.municipality].groupby(["s_lon", "s_lat"]).municipality.nunique()
plan["shared"] = [int(others.get((a, b), 0)) for a, b in zip(plan.s_lon, plan.s_lat)]
plan = plan[plan.people >= .5].sort_values(["people", "km"], ascending=[False, True]).reset_index(drop=True)  # open the big ones first
plan.insert(0, "n", range(1, len(plan) + 1))
walk = min(t.covered, t.people)
ride = max(t.bus_covered - t.covered, 0) if pd.notna(t.bus_covered) else 0
left = max(t.people - walk - ride, 0)

care = crit[(crit.municipality == t.municipality) & (crit.area == t.area) & crit.in_worst_flood.astype(bool)
            & crit.share_of_site_flooded.ge(.05)]
care = care.sort_values(["share_of_site_flooded"], ascending=False)
weak = care[care.type.isin(["hospital", "care home"])]
schools = care[care.type == "school"]

verdict = (f"{t['name']}: move about {about(t.people)} residents to {len(plan)} dry shelters"
           + (f"; {about(left)} still have no place within 10 km" if left >= 5 else ", all of them have a place"))
sub = (f"{about(walk)} can walk to one (within 1.5 km); {about(ride)} need a bus or car (up to 10 km)."
       + (f" Evacuate {len(weak)} hospital{'s' if len(weak) != 1 else ''} or care home{'s' if len(weak) != 1 else ''} "
          "first." if len(weak) else ""))
note = ("Modelled: the satellite missed the Vesdre, so the EFAS 500-year flood zone stands in."
        if modelled else "Observed: all Copernicus satellite passes of July 2021, a floor, not the peak.")


def river_line():
    """Is a flood coming here? The nearest GloFAS outlook point within 15 km of the town centre, else say there is none."""
    gauges, *_, err = core.outlook()
    pts = pd.DataFrame([(g, la, lo) for g, (la, lo) in forecast.GAUGES.items()], columns=["gauge", "lat", "lon"])
    pts["d"] = core.km(t.lon, t.lat, pts.lon, pts.lat)
    near_g = pts[pts.d <= 15].nsmallest(1, "d")
    if gauges is None:
        txt, c = f"River outlook unavailable right now. Follow {OFFICIAL[cc]}.", core.OFFLINE
    elif near_g.empty:
        txt, c = f"No river outlook point near {t['name']} in this tool. Follow {OFFICIAL[cc]}.", core.OFFLINE
    else:
        g = gauges[gauges.gauge == near_g.gauge.iloc[0]].iloc[0]
        name, col = forecast.LEVELS[g.level]
        txt = (f"<b>{g.gauge}, next 30 days: {name.lower()}</b> · peak {g.pct_2021:.0%} of its July 2021 peak on "
               f"{g.peak_day:%a %d %b}" + (f"; wettest run: {forecast.LEVELS[g.level_worst][0].lower()}"
                                           if g.level_worst > g.level else "")
               + f". A model heads-up, not a warning: official warnings come from {OFFICIAL[cc]}.")
        c = col
    st.html(f"<p class='ev-river'><i style='background:{c}'></i><span>{txt}</span></p>")


river_line()
core.banner("#d70015" if left >= 5 or len(weak) else "#0071e3", verdict, sub + f"<small>{note}</small>", note=False)
st.space("small")

st.html("<div class='ev-n'>"
        f"<div><b style='color:{core.SHELTER}'>{about(walk)}</b><span><i>walk</i> to a shelter within 1.5 km</span></div>"
        f"<div><b style='color:#0071e3'>{about(ride)}</b><span><i>need transport</i> to a shelter 1.5–10 km away</span></div>"
        + (f"<div><b style='color:{core.EVACUATE}'>{about(left)}</b><span><i>no place</i> within 10 km: ask the next "
         "municipality</span></div></div>" if left >= 5 else
         "<div><b>0</b><span><i>no place</i> within 10 km: everyone fits</span></div></div>"))
st.space("small")

# ------------------------------------------------------------------ map + shelter list
MAP_H = 470
lm, rm = st.columns([3, 2], gap="small")
with lm:
    a = 70 if modelled else 140
    layers = [pdk.Layer("GeoJsonLayer", flood[(t.area, V)], filled=True, stroked=True, line_width_min_pixels=1,
                        get_fill_color=[0, 113, 227, a], get_line_color=[0, 90, 200, 200])]
    if len(care):
        cs = care.assign(tname=care.name, tinfo=[f"{k} in the 2021 water · {s:.0%} of the site"
                                                 for k, s in zip(care.type, care.share_of_site_flooded)])
        layers.append(core.points(cs, core.rgb(core.EVACUATE), 6))
    if len(plan):
        ps = plan.assign(lon=plan.s_lon, lat=plan.s_lat, tname=[f"{n}. {s}" for n, s in zip(plan.n, plan.shelter)],
                         tinfo=[f"{about(p)} people from {t['name']} · {fmt(c)} places in all · {k} km from the centre"
                                for p, c, k in zip(plan.people, plan.places, plan.km)],
                         r=lambda d: d.people ** .5 * .35 + 5)
        lab = ps.head(10).assign(txt=lambda d: d.n.astype(str), r=lambda d: d.r.clip(lower=9))
        layers += [pdk.Layer("ScatterplotLayer", ps, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                             get_fill_color=core.rgb(core.SHELTER, 230), get_line_color=[255, 255, 255],
                             line_width_min_pixels=2, stroked=True, pickable=True),
                   pdk.Layer("ScatterplotLayer", lab, get_position=["lon", "lat"], get_radius="r",
                             radius_units="'pixels'", get_fill_color=core.rgb(core.SHELTER), get_line_color=[255, 255, 255],
                             line_width_min_pixels=2, stroked=True, pickable=True),
                   pdk.Layer("TextLayer", lab, get_position=["lon", "lat"], get_text="txt", get_size=12,
                             get_color=[255, 255, 255], font_weight=700, get_alignment_baseline="'center'")]
    ctr = pd.DataFrame([{"lon": t.lon, "lat": t.lat, "tname": f"{t['name']} centre",
                         "tinfo": "distances in the list are straight lines from here"}])
    layers.append(pdk.Layer("ScatterplotLayer", ctr, get_position=["lon", "lat"], get_radius=7, radius_units="'pixels'",
                            get_fill_color=[255, 255, 255], get_line_color=[29, 29, 31], line_width_min_pixels=3,
                            stroked=True, pickable=True))
    pts = pd.concat([plan.rename(columns={"s_lon": "lon", "s_lat": "lat"})[["lon", "lat"]],
                     pd.DataFrame([{"lon": t.lon, "lat": t.lat}])])
    spread = core.km(pts.lon.mean(), pts.lat.mean(), pts.lon, pts.lat).max()
    z = 13 if spread < 1.5 else 12 if spread < 3 else 11 if spread < 6 else 10 if spread < 12 else 9
    tip = {"html": "<b>{tname}</b><br/>{tinfo}",
           "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}}
    st.pydeck_chart(pdk.Deck(layers=layers, map_style=pdk.map_styles.CARTO_LIGHT, tooltip=tip,
                             initial_view_state=pdk.ViewState(longitude=pts.lon.mean(), latitude=pts.lat.mean(), zoom=z),
                             views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=MAP_H)
    core.legend(core.swatch(core.SHELTER, "Dry shelter (size = people sent there; the ten largest numbered as in the list)", True)
                + (core.swatch(core.EVACUATE, "Hospital, care home or school in the 2021 water", True) if len(care) else "")
                + core.swatch("rgba(0,113,227,.55)", "2021 water" + (" (modelled)" if modelled else ""))
                + "<span><i style='border:3px solid #1d1d1f;border-radius:50%;background:#fff'></i>Town centre</span>")
with rm:
    if len(plan):
        st.dataframe(plan[["n", "shelter", "km", "people", "places", "shared"]], hide_index=True, height=MAP_H - 10,
                     column_config={
                         "n": st.column_config.NumberColumn("#", width=36),
                         "shelter": st.column_config.TextColumn("Dry shelter", width=175),
                         "km": st.column_config.NumberColumn("km", format="%.1f", width=44,
                                                             help="Straight line from the town centre"),
                         "people": st.column_config.NumberColumn("Send", format="%d", width=54,
                                                                 help="People from this town sent here"),
                         "places": st.column_config.NumberColumn("Places", format="%d", width=54,
                                                                 help="All places, rough estimate"),
                         "shared": st.column_config.NumberColumn("Shared", format="%d", width=54,
                                                                 help="Number of other towns sent here too: agree who uses it")})
    else:
        st.info("No dry candidate shelter within 10 km in the data. Ask the neighbouring municipalities.")
st.html("<p class='asof'>One plan that fits the most people in (max-flow, 10 km straight line). Shelters are "
        "OpenStreetMap schools, sports halls and civic buildings, dry in 2021 and in the 100-year model: candidates, not "
        "official shelters. Places: floor area × 50 % usable ÷ 4 m² per person.</p>")
st.space("medium")

# ------------------------------------------------------------------ the four steps that broke in 2021
first, order, msg, prep = st.tabs(["Evacuate first", "Who gives the order", "Warning message", "Plan and drill"])

with first:
    if len(weak):
        rows = []
        for r in weak.itertuples():
            d = recv[recv.from_name == r.name].sort_values("km").head(1)
            to = f"nearest dry {r.type}: {d.to_name.iloc[0]}, {d.km.iloc[0]:.1f} km" if len(d) else "no dry site in reach"
            rows.append((f"<b>{escape(r.name)}</b>", f"{r.type} · {r.share_of_site_flooded:.0%} of the site under water · "
                         f"{escape(to)}", "First"))
        core.group(rows, "Hospitals and care homes in the 2021 water")
    else:
        core.group([("No hospital or care home in the 2021 water here", "Still check sites at the edge of the flood.",
                     "")], "Hospitals and care homes")
    if len(schools):
        core.group([(f"<b>{escape(r.name)}</b>", f"{r.share_of_site_flooded:.0%} of the site under water: close it, "
                     "and do not use it as a shelter", "Close") for r in schools.itertuples()], "Schools in the 2021 water")
    st.html("<p class='asof'>Not in any dataset: age, income, disability or who lives alone. Older riverside homes and "
            "people without a car are most at risk: the municipality's own list of residents who need help leaving "
            "comes first. Free beds in receiving sites: confirm with each operator.</p>")

with order:
    core.group([(f"<b>{r}</b>", f"{w}. {h}.", "") for r, w, h in CHAIN[cc]], f"Who does what in {CC[cc]}")
    st.html("<p class='asof'>Team summary of the national crisis rules, not challenge data. In 2021 the warning reached "
            "few of the people who give these orders in time: check this against the municipality's emergency plan and "
            "fill in names and deputies there.</p>")

# message: the two biggest shelters within 1.5 km for walkers (else the nearest), the biggest farther one for the bus
near = (plan[plan.km <= 1.5].head(2) if (plan.km <= 1.5).any() else plan.nsmallest(2, "km")).shelter.tolist()
far_ = plan[plan.km > 1.5].sort_values("people", ascending=False).shelter.head(1).tolist() or plan.shelter.tail(1).tolist()
fill = dict(town=t["name"], near=near or ["[shelter]"], far=far_[0] if far_ else "[shelter]",
            line="[help line]")
with msg:
    line = st.text_input("Help line for people who cannot leave alone", placeholder="e.g. the municipal crisis number",
                         key="ev_line").strip()
    fill["line"] = line or "[help line]"
    langs = [LOCAL_LANG[cc], "English"]
    lang = st.segmented_control("Language", langs, default=langs[0], key=f"ev_lang_{cc}", label_visibility="collapsed")
    lang = lang or langs[0]
    text = MSG[lang].format(**{**fill, "near": OR[lang].join(fill["near"])})
    st.code(text, language=None, wrap_lines=True)
    st.html("<p class='asof'>Draft for BE-Alert, NL-Alert or cell broadcast; copy with the icon. AI-assisted wording, "
            "checked by the team; have a native speaker and the communication officer approve it before use."
            " Walkers: the two largest shelters within 1.5 km. Bus: the largest one farther away.</p>")

with prep:
    core.group([(p, "") for p in PREPARE], "Before the flood season")
    rows = "".join(f"<tr><td>{r.n}</td><td>{escape(r.shelter)}</td><td>{r.km:.1f}</td><td>{r.people:.0f}</td>"
                   f"<td>{r.places:.0f}</td><td>{r.shared}</td></tr>" for r in plan.itertuples())
    who = "".join(f"<tr><td><b>{r}</b></td><td>{escape(w)}</td><td>{escape(h)}</td></tr>" for r, w, h in CHAIN[cc])
    first_rows = "".join(f"<li>{escape(r.name)} ({r.type}, {r.share_of_site_flooded:.0%} under water)</li>"
                         for r in weak.itertuples()) or "<li>None in the 2021 water</li>"
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Evacuation plan · {escape(t['name'])}</title>
<style>body{{font:14px/1.45 -apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#1d1d1f;max-width:800px;margin:2rem auto;
padding:0 1rem}}h1{{font-size:1.6rem;margin:0}}h2{{font-size:1.1rem;margin:1.6rem 0 .4rem}}table{{border-collapse:collapse;
width:100%}}td,th{{border-bottom:1px solid #ddd;padding:.3rem .4rem;text-align:left;vertical-align:top}}
.n{{color:#6e6e73;font-size:.85rem}}.box{{border:1px solid #ccc;border-radius:8px;padding:.6rem .8rem}}</style></head><body>
<h1>Evacuation plan · {escape(t['name'])}</h1>
<p class="n">Draft from the July 2021 flood data, {date.today():%d %b %Y}. {escape(note)}</p>
<h2>Who leaves</h2><p>About {about(t.people)} residents lived in the 2021 water. {about(walk)} can walk to a shelter
within 1.5 km; {about(ride)} need transport (up to 10 km); {about(left)} have no place within 10 km.</p>
<h2>Evacuate first</h2><ul>{first_rows}</ul>
<h2>Where they go</h2><table><tr><th>#</th><th>Dry shelter</th><th>km from centre</th><th>People sent</th>
<th>Places in all</th><th>Other towns sent here</th></tr>{rows}</table>
<h2>Who gives the order ({CC[cc]})</h2><table>{who}</table>
<p class="n">Team summary of national rules, not challenge data. Fill in names, deputies and phone numbers from the
municipality's emergency plan.</p>
<h2>Warning message</h2><div class="box">{escape(text)}</div>
<h2>Before the flood season</h2><ul>{''.join(f'<li>{escape(p)}</li>' for p in PREPARE)}</ul>
<h2>Limits</h2><p class="n">Residents: GHS-POP 2020 spread over homes, an order of magnitude. Shelters: OpenStreetMap
candidates, dry in 2021 and in the EFAS 100-year model, not official; capacity = floor area × 50 % ÷ 4 m². Distances are
straight lines from the town centre. No data on age, income or disability.</p></body></html>"""
    st.download_button("Download the town plan (print it or save as PDF)", doc,
                       file_name=f"evacuation_plan_{t['name'].replace(' ', '_')}.html", mime="text/html",
                       icon=":material/download:", type="primary")
