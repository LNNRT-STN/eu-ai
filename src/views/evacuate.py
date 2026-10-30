"""Evacuation plan, one town at a time, for the scenario the crisis room switched on (the rarest EFAS return period
on: 10-, 100- or 500-year river flood; the 100-year zone, for planning, when none is): who leaves, which dry shelter
they go to, who gives the order, the message that tells them and what fire crews tell each home. Answers the 2021
failures the team listed: unclear roles across levels, warnings that never became instructions, missing local plans
and drills, people who could not leave alone.
Page layout: the verdict (first action), the three key numbers, the town across return periods and the plan map,
then five tabs (Getting out, Evacuate first, Shelters with views/shelters.py, Orders & message, 3D with
views/view3d.py), then the region call order folded in an expander. Numbers: outputs/rp/ (app_towns: walking plan;
bus_plan: the 10 km max-flow plan, per shelter; critical_sites; receiving_sites; evac_towns / evac_edges: road
simulation; each per variant rp10 / rp100 / rp500). The roles and the message are team text, not data: labelled on
the page and in the download."""
from datetime import date
from html import escape

import pandas as pd
import pydeck as pdk
import streamlit as st

import anna
import core
import forecast
import live
from core import about, fmt
from views import checkin, host, shelters as shelter_list, view3d

head, towns, crit, shel, flood, *_ = anna.load()
recv, bus = anna.load_moves()
B3D = view3d.B3D                                             # every OBAT building in the 500-year zone, flags in_rp*
EVAC = pd.read_csv(core.DATA / "evac_towns.csv")             # notebooks/evac_sim.py: road simulation, towns >= 300 people
feats = lambda g, m: {"type": "FeatureCollection", "features": [f for f in g["features"]
                                                                 if f["properties"]["municipality"] == m]}
P = live.plan()                   # the return period the response plans for; None = normal
V = live.variant()                # its data variant (rp100 when normal, for planning)
RP = int(V[2:])
ZONE = f"{RP}-year zone"
EDGES = checkin.edges(V)
T = (towns[(towns.variant == V) & (towns.people >= 10)].sort_values("people", ascending=False).reset_index(drop=True))
CC = {"BE": "Belgium", "NL": "Netherlands", "DE": "Germany"}
BED = "#d9a400"                   # spare beds offered by residents: yellow, clear of shelter green and water blue

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
    "English": ("FLOOD WARNING – {town}. The river may flood the streets near it. Leave now. "
                "Take medicines, ID papers and a phone charger. Go to a shelter on higher ground: {near}. "
                "Cannot leave on your own? Call {line}. A bus will take you to {far}. "
                "Check on neighbours who are old, ill or alone. Never walk or drive through flood water."),
    "Français": ("ALERTE INONDATION – {town}. La rivière risque d'inonder les rues proches. "
                 "Quittez votre domicile maintenant. Prenez vos médicaments, vos papiers d'identité et un chargeur de "
                 "téléphone. Rendez-vous dans un centre d'accueil situé en hauteur : {near}. Vous ne pouvez pas partir "
                 "par vos propres moyens ? Appelez le {line}. Un bus vous conduira à {far}. Prenez des nouvelles de vos "
                 "voisins âgés, malades ou isolés. Ne traversez jamais une zone inondée, ni à pied ni en voiture."),
    "Deutsch": ("HOCHWASSERWARNUNG – {town}. Der Fluss kann die Straßen in seiner Nähe überfluten. "
                "Verlassen Sie jetzt Ihr Haus. Nehmen Sie Medikamente, Ausweis und Handy-Ladegerät mit. "
                "Gehen Sie zu einer höher gelegenen Notunterkunft: {near}. Können Sie nicht selbst gehen? Rufen Sie "
                "{line} an. Ein Bus bringt Sie zu {far}. Sehen Sie nach älteren, kranken oder alleinlebenden "
                "Nachbarn. Gehen oder fahren Sie niemals durch Hochwasser."),
    "Nederlands": ("WAARSCHUWING OVERSTROMING – {town}. De rivier kan de straten in de buurt overstromen. "
                   "Vertrek nu. Neem medicijnen, uw identiteitsbewijs en een oplader mee. Ga naar een hoger "
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



# care sites: in the scenario's zone; share_of_site_flooded is of the 500-year zone (below 5 % only the site's edge)
wet = lambda k: crit[f"in_{k}_flood"].astype(bool) & crit.share_of_site_flooded.ge(.05)
cs_all = crit[wet(V) & crit.type.isin(["hospital", "care home"])]
first_n = cs_all.groupby(["area", "municipality"]).size()
calls = (T.assign(care=[int(first_n.get((a, m), 0)) for a, m in zip(T.area, T.municipality)], call=[live.district(a, m) for a, m in zip(T.area, T.municipality)],
                  short=T["name"])
         .sort_values(["no_shelter", "care"], ascending=False).head(6))


def pick_call():
    rows = st.session_state.ev_calls.selection.rows
    if rows:
        st.session_state.town = st.session_state._town = calls.municipality.iloc[rows[0]]


pick = T[T.municipality == st.session_state.get("town")]
t = (pick if len(pick) else T).iloc[0]
cc = t.municipality[-3:-1]

# ------------------------------------------------------------------ where the people go (10 km max-flow plan)
bus = bus[bus.variant == V]      # only the shelters dry in this zone
plan = bus[(bus.municipality == t.municipality) & (bus.area == t.area)].copy()
plan["km"] = core.km(t.lon, t.lat, plan.s_lon, plan.s_lat).round(1)
others = bus[bus.municipality != t.municipality].groupby(["s_lon", "s_lat"]).municipality.nunique()
plan["shared"] = [int(others.get((a, b), 0)) for a, b in zip(plan.s_lon, plan.s_lat)]
plan = plan[plan.people >= .5].sort_values(["people", "km"], ascending=[False, True]).reset_index(drop=True)  # open the big ones first
plan.insert(0, "n", range(1, len(plan) + 1))
walk = min(t.covered, t.people)
ride = max(t.bus_covered - t.covered, 0) if pd.notna(t.bus_covered) else 0
left = max(t.people - walk - ride, 0)

care = crit[(crit.municipality == t.municipality) & (crit.area == t.area) & wet(V)]
# the most frequent flood that reaches each site (zones are nested)
care = care.assign(rp=[next(int(k[2:]) for k in core.VARIANT if r[f"in_{k}_flood"]) for _, r in care.iterrows()])
care = care.sort_values(["share_of_site_flooded"], ascending=False)
weak = care[care.type.isin(["hospital", "care home"])]

# ------------------------------------------------------------------ spare beds residents offered (views/host.py)
# no address is stored: each offer sits at its host town's centre; kept if that centre is within 10 km of this town
ctr_all = towns.drop_duplicates("municipality").set_index("municipality")[["lon", "lat"]]
beds = host.offers()
beds = beds[beds.outside_2021.astype(bool) & beds.municipality.isin(ctr_all.index)] if len(beds) else beds
beds = (beds.assign(lon=ctr_all.lon.reindex(beds.municipality).values, lat=ctr_all.lat.reindex(beds.municipality).values)
        .assign(km=lambda d: core.km(t.lon, t.lat, d.lon, d.lat).round(1) if len(d) else []))
beds = beds[beds.km <= 10].sort_values(["km", "when"]).reset_index(drop=True) if len(beds) else beds
free = beds[beds.status.isin(host.OPEN)] if len(beds) else beds  # Guest placed and Withdrawn are no longer free
schools = care[care.type == "school"]

# ------------------------------------------------------------------ getting out: road simulation
# OSM falls back to the road class when a road has no name
road = lambda n: f"An unnamed {n} road" if n in {"motorway", "trunk", "primary", "secondary", "tertiary", "residential",
                                                   "unclassified", "service", "living_street", "footway", "path", "track"} else n
ev = EVAC[(EVAC.municipality == t.municipality) & (EVAC.area == t.area) & (EVAC.variant == V)]
verdict = ((f"Move about {about(t.people)} residents of the {ZONE} to {len(plan)} dry shelters" if P else
            f"In a {RP}-year flood, about {about(t.people)} residents live in the zone; {len(plan)} dry shelters "
            "could take them")
           + (f"; {about(left)} still have no place within 10 km" if left >= 5 else ", all of them have a place"))
sub = (f"{about(walk)} can walk to one (within 1.5 km); {about(ride)} need a bus or car (up to 10 km)."
       + (f" Evacuate {len(weak)} hospital{'s' if len(weak) != 1 else ''} or care home{'s' if len(weak) != 1 else ''} "
          "first." if len(weak) else ""))
if len(ev) and ev.reroute_share.iloc[0] >= .5:
    sub += (f" {ev.reroute_share.iloc[0]:.0%} of routes to a shelter cross the {ZONE} again: leave before the river "
            "rises.")
note = (f"Modelled: the EFAS {RP}-year flood zone, all rivers at once and no dikes or flood walls, so towns behind "
        "dikes (the Meuse) are an upper bound. A planning map, not a forecast.")
# the first action for this town: the same steps as the region call list, in the order they take longest
pl = lambda n, one, many: f"{n} {one if n == 1 else many}"
todo = ([f"start moving its {pl(len(weak), 'hospital or care home', 'hospitals and care homes')}"] if len(weak) else []) \
    + ([f"book buses for about {about(ride)} residents who cannot walk to a shelter"] if ride >= 5 else []) \
    + ([f"ask the next municipality to take about {about(left)} more"] if left >= 5 else [])
if not todo and len(plan):
    todo = [f"open shelter 1, {plan.shelter.iloc[0]}"]
first_action = f"call the mayor and {live.district(t.area, t.municipality)}" + (": " + "; ".join(todo) if todo else "")


def river_line():
    """Is a flood coming here? The nearest GloFAS outlook point within 15 km of the town centre, else say there is none."""
    gauges, *_, err = core.outlook()
    pts = pd.DataFrame([(g, la, lo) for g, (la, lo) in forecast.GAUGES.items()], columns=["gauge", "lat", "lon"])
    pts["d"] = core.km(t.lon, t.lat, pts.lon, pts.lat)
    near_g = pts[pts.d <= 15].nsmallest(1, "d")
    if gauges is None:
        txt = f"River outlook unavailable right now. Follow {OFFICIAL[cc]}."
    elif near_g.empty:
        txt = f"No river outlook point near {t['name']} in this tool. Follow {OFFICIAL[cc]}."
    else:
        g = gauges[gauges.gauge == near_g.gauge.iloc[0]].iloc[0]
        name = forecast.LEVELS[g.level][0]
        txt = (f"**{g.gauge}, next {forecast.HORIZON} days: {name.lower()}** · "
               + (f"{g.chance:.0%} of forecast runs, most on {g.peak_day:%a %d %b}" if g.level else
                  f"median peak a {forecast.rp_text(g.rp_peak)} flood")
               + (f"; wettest run: {forecast.LEVELS[g.level_worst][0].lower()}" if g.level_worst > g.level else ""))
        st.caption(f":material/water: {txt}", help="GloFAS ensemble river outlook (Open-Meteo), rated on the point's "
                                                   "own 2-, 5- and 20-year floods: a model heads-up, not a warning. "
                                                   f"Official warnings come from {OFFICIAL[cc]}.")
        return
    st.caption(f":material/water: {txt}")


# ================================================================== verdict, plan map, three numbers
# page-local CSS: keep each row of key numbers side by side on a phone, a little smaller
st.html("<style>@media (max-width:640px){[class*=st-key-kpi] [data-testid=stHorizontalBlock]{flex-wrap:nowrap;gap:.5rem}"
        "[class*=st-key-kpi] [data-testid=stColumn]{min-width:0;flex:1 1 0}"
        "[class*=st-key-kpi] [data-testid=stMetricValue]{font-size:1.5rem}"
        "[class*=st-key-kpi] [data-testid=stMetricLabel] *{white-space:normal!important;text-overflow:clip!important;"
        "overflow:visible!important;line-height:1.25}"
        "[class*=st-key-kpi] [data-testid=stMetric]{padding:.5rem .6rem}}</style>")
st.title(t["name"], anchor=False)
if P:
    st.caption(f"Town plan for a {RP}-year river flood ({100 / RP:g} % chance in any year): who leaves, where they go, "
               "who gives the order.")
    urgent = left >= 5 or len(weak) or (len(ev) and ev.reroute_share.iloc[0] >= .5)
    (st.error if urgent else st.info)(f"**First action: {first_action}.**\n\n{verdict}. {sub}",
                                      icon=":material/warning:" if urgent else ":material/info:")
else:
    st.caption(f"No flood scenario is on: the town as it would be in a {RP}-year flood, for planning.")
    st.info(f"{verdict}.", icon=":material/info:")
river_line()

m1, m2, m3 = st.container(key="kpi_top").columns(3)
m1.metric("Can walk to a shelter", about(walk), border=True,
          help="Walking check: a free shelter place within 1.5 km of home (best possible share-out).")
m2.metric("Need a bus or car", about(ride), border=True,
          help="10 km plan: a free place 1.5–10 km from home. The Shelters tab lists this 10 km plan, so its split "
               "between near and far shelters differs from the walking check.")
m3.metric("No place within 10 km", about(left), help="Ask the next municipality" if left >= 5 else "Everyone fits",
          border=True)
st.caption(note)


def across():
    """The town in the 10-, 100- and 500-year zone: who and what is in the water, and the shelters left."""
    hb = B3D[(B3D.municipality == t.municipality) & (B3D.area == t.area)]
    tw = towns[(towns.municipality == t.municipality) & (towns.area == t.area)].set_index("variant")
    sh = core.load()["shelters"]
    near = sh[core.km(t.lon, t.lat, sh.lon, sh.lat) <= 10]
    here = crit[(crit.municipality == t.municipality) & (crit.area == t.area) & crit.type.isin(["hospital", "care home"])]
    rows = []
    for k in core.VARIANT:
        b = bus_all[(bus_all.variant == k) & (bus_all.municipality == t.municipality) & (bus_all.area == t.area)]
        ppl = int(tw.people.get(k, 0))
        rows.append({"Flood": f"{k[2:]}-year" + (" · plan" if k == V and P else ""), "Residents": ppl,
                     "Homes": int(((hb.use == 1) & hb[f"in_{k}"]).sum()),
                     "Care sites": int((here[f"in_{k}_flood"].astype(bool) & here.share_of_site_flooded.ge(.05)).sum()),
                     "Shelters lost": int(near[f"in_{k}"].astype(bool).sum()),
                     "No place within 10 km": max(ppl - int(round(b.people.sum())), 0) if ppl else 0})
    st.markdown(f":blue[:material/stacked_line_chart:] **{t['name']} as the flood gets rarer**",
                help="Each row is one EFAS flood zone; the zones are nested. Care sites: hospitals and care homes in "
                     "the zone. Shelters lost: candidate sites within 10 km of the centre inside the zone. No place: "
                     "residents the 10 km shelter plan of that flood cannot place.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="localized")
                                for c in ["Residents", "Homes", "No place within 10 km"]})


bus_all = anna.load_moves()[1]
across()

layers = [pdk.Layer("GeoJsonLayer", flood[(t.area, V)], filled=True, stroked=True, line_width_min_pixels=1,
                    get_fill_color=core.rgb(core.RP_COL[V], 90), get_line_color=core.rgb(core.RP_COL[V], 200))]
# where people go: a line from the town centre to each shelter of the plan, wider with the people it takes
if len(plan):
    top = plan.nlargest(10, "people")  # the numbered shelters; the long tail would turn the map into a starburst
    flows = top.assign(a=[[t.lon, t.lat]] * len(top), b=[[x, y] for x, y in zip(top.s_lon, top.s_lat)],
                       w=top.people ** .5 * .1 + 1.5)
    layers.append(pdk.Layer("LineLayer", flows, get_source_position="a", get_target_position="b", get_width="w",
                            width_units="'pixels'", get_color=core.rgb(core.SHELTER, 110)))
# the evacuation roads themselves: white casing, blue where dry, orange where inside the zone, red if closed
shut = set(live.closures().osm_id.dropna().astype(str))
ed = feats(EDGES, t.municipality)
for f in ed["features"]:
    q = f["properties"]
    q["c"] = core.rgb("#d70015") if str(q["osm_id"]) in shut else core.rgb("#c93400") if q["in_flood_2021"] else core.rgb("#0071e3")
    q["w"] = 3 + 5 * min(1, (q["people"] or 0) / 3000)
    q["tname"] = (q["name"] if str(q["name"])[:1].isupper() else "Unnamed road") + (
        " · closed" if str(q["osm_id"]) in shut else f" · in the {ZONE}" if q["in_flood_2021"] else "")
    q["tinfo"] = f"Evacuation road for about {about(q['people'] or 0)} people"
layers += [pdk.Layer("GeoJsonLayer", ed, get_line_color=[255, 255, 255, 240], get_line_width="properties.w + 4",
                     line_width_units="'pixels'", line_cap_rounded=True),
           pdk.Layer("GeoJsonLayer", ed, get_line_color="properties.c", get_line_width="properties.w",
                     line_width_units="'pixels'", line_cap_rounded=True, pickable=True)]
if len(care):
    cs = care.assign(tname=care.name, tinfo=[f"{k} · flooded from a {r}-year flood" for k, r in zip(care.type, care.rp)])
    layers.append(core.points(cs, core.rgb("#7b3fd1"), 6))
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
if len(free):
    fb = (free.groupby("municipality").agg(lon=("lon", "first"), lat=("lat", "first"), n=("beds", "sum"),
                                           homes=("code", "size"), km=("km", "first")).reset_index())
    fb = fb.assign(tname=[f"{int(n)} spare bed{'s' if n != 1 else ''} in {anna.town(m)}" for n, m in zip(fb.n, fb.municipality)],
                   tinfo=[f"{h} home{'s' if h != 1 else ''} · {k:.1f} km · offered by residents, no address shown"
                          for h, k in zip(fb.homes, fb.km)], r=lambda d: d.n ** .5 * 4 + 6)
    layers.append(pdk.Layer("ScatterplotLayer", fb, get_position=["lon", "lat"], get_radius="r", radius_units="'pixels'",
                            get_fill_color=core.rgb(BED, 220), get_line_color=[255, 255, 255], line_width_min_pixels=2,
                            stroked=True, pickable=True, id="spare-beds"))
ctr = pd.DataFrame([{"lon": t.lon, "lat": t.lat, "tname": f"{t['name']} centre",
                     "tinfo": "distances in the list are straight lines from here"}])
layers.append(pdk.Layer("ScatterplotLayer", ctr, get_position=["lon", "lat"], get_radius=7, radius_units="'pixels'",
                        get_fill_color=[255, 255, 255], get_line_color=[29, 29, 31], line_width_min_pixels=3,
                        stroked=True, pickable=True))
pts = pd.concat([plan.rename(columns={"s_lon": "lon", "s_lat": "lat"})[["lon", "lat"]],
                 pd.DataFrame([{"lon": t.lon, "lat": t.lat}])])
# frame the town and its nearer half of shelters, so its evacuation roads read; the far shelters stay at the edges
spread = core.km(t.lon, t.lat, pts.lon, pts.lat).quantile(.5) * 2
z = 13 if spread < 1.5 else 12.5 if spread < 3 else 12 if spread < 5 else 11.5 if spread < 8 else 11
tip = {"html": "<b>{tname}</b><br/>{tinfo}",
       "style": {"backgroundColor": "#1d1d1f", "color": "#fff", "fontSize": "13px", "borderRadius": "8px"}}
st.pydeck_chart(pdk.Deck(layers=layers, map_style=pdk.map_styles.CARTO_LIGHT, tooltip=tip,
                         initial_view_state=pdk.ViewState(longitude=t.lon, latitude=t.lat, zoom=z),
                         views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=480)
st.caption(":green[●] Dry candidate shelter, size = people sent there (numbered as in the Shelters tab) · "
           + (f":violet[●] Hospital, care home or school in the {ZONE} · " if len(care) else "")
           + f":blue[■] {RP}-year flood zone (EFAS model) · "
           + (":yellow[●] Spare beds offered by residents (at their town centre) · " if len(free) else "")
           + ":material/radio_button_unchecked: Town centre · :green[━] To the 10 largest shelters · "
           f":blue[━] Evacuation road · :orange[━] Evacuation road in the {ZONE} · :red[━] Closed",
           help="Map © OpenStreetMap contributors, © CARTO. Shelters and roads: OpenStreetMap; flood zone: EFAS "
                "(Copernicus Emergency Management Service), modelled.")


def save_beds(key):
    """Persist the manager's edits (status, beds) by reference code, then show a fresh editor."""
    ed = st.session_state[key]["edited_rows"]
    host.update({beds.code[r]: kv for r, kv in ed.items()})
    st.session_state.beds_v = st.session_state.get("beds_v", 0) + 1


def spare_beds():
    """Beds residents offered (Offer a bed tab of the resident page) within 10 km: the manager checks each home and
    records the guest placed. Only Offered and Checked beds count and show on the map."""
    if beds.empty:
        return
    n, h = int(free.beds.sum()), len(free)
    st.markdown(f":orange[:material/bed:] **{n} spare bed{'s' if n != 1 else ''} still free with residents within "
                f"10 km** ({h} home{'s' if h != 1 else ''})",
                help="Offered on the resident page: no name or address, only the town and a reference code. Not "
                     "counted in the shelter places. Use them first for people who cannot stay in a hall. Check the "
                     "home, then record the guest placed: placed beds leave the count and the map.")
    fit = lambda r: ", ".join(v for k, v in {"step_free": "step-free", "older": "older", "family": "family",
                                             "pets": "pets"}.items() if bool(r[k])) or "anyone"
    key = f"beds_{st.session_state.get('beds_v', 0)}"
    st.data_editor(pd.DataFrame({"code": beds.code, "town": beds.municipality.map(anna.town), "km": beds.km,
                                 "beds": beds.beds.astype(int), "fits": beds.apply(fit, axis=1),
                                 "status": beds.status}),
                   key=key, on_change=save_beds, args=(key,), hide_index=True, disabled=["code", "town", "km", "fits"],
                   column_config={"code": st.column_config.TextColumn("Code", width="small",
                                                                      help="The host's reference code: ask for it to match a guest"),
                                  "town": "Host town",
                                  "km": st.column_config.NumberColumn("km", format="%.1f", width="small",
                                                                      help="Straight line between town centres"),
                                  "beds": st.column_config.NumberColumn("Beds", min_value=0, max_value=10, step=1,
                                                                        width="small"),
                                  "fits": st.column_config.TextColumn("Can take"),
                                  "status": st.column_config.SelectboxColumn("Status", options=host.STATUS,
                                                                             required=True,
                                                                             help="Offered → Checked (home visited) → "
                                                                                  "Guest placed")})


def crews():
    """Fire brigade: the doors to knock in this zone, help requests then single-storey homes first, the shelter to send
    each street to (views/checkin.py builds the same list, home by home) and the closed roads."""
    st.markdown(":red[:material/door_front:] **Fire brigade: door to door**",
                help="For homes the alert does not reach. The Door-knock list has every home, the shelter to send it "
                     "to, and lets crews mark it done.")
    D = checkin.doors(V)
    D = D[D.municipality == t.municipality]
    if D.empty:
        st.caption(f"No home of {t['name']} in the {ZONE}.")
        return
    ck = live.checkins(t.municipality)
    last = live.latest(ck).set_index("door").status if len(ck) else pd.Series(dtype=str)
    D = anna.destinations(t.municipality, D.assign(status=D.door.map(last).fillna("no news")), V)
    todo = D[D.status != "safe"]
    helpn = int((todo.status == "needs help").sum())
    c = st.container(key="kpi_doors").columns(3)
    c[0].metric("Doors to knock", fmt(len(todo)), border=True, help=f"Homes in the {ZONE} not yet reported gone")
    c[1].metric("Asked for help", fmt(helpn), border=True, help="Residents who reported 'I need help': go there first")
    c[2].metric("Single-storey", fmt(int(todo.single.sum())), border=True,
                help="No upper floor to escape to: knock on these next")
    by = (todo.assign(h=todo.status == "needs help").groupby("street", dropna=False)
          .agg(homes=("door", "size"), help=("h", "sum"), single=("single", "sum"),
               go=("go", lambda x: x.mode().iat[0] if len(x.mode()) else ""),
               addr=("go_address", lambda x: x.mode().iat[0] if len(x.mode()) else ""), km=("go_km", "median"))
          .reset_index().sort_values(["help", "single", "homes"], ascending=False))
    by["street"] = by.street.fillna("(no street name)")
    st.caption("Street by street: tell each home to leave now and go to its shelter. Help requests first, then "
               "single-storey homes.")
    st.dataframe(by, hide_index=True, height=min(35 * len(by) + 38, 320), column_config={
        "street": "Street", "homes": st.column_config.NumberColumn("Homes", format="%d", width="small"),
        "help": st.column_config.NumberColumn("Help", format="%d", width="small", help="Asked for help"),
        "single": st.column_config.NumberColumn("1 storey", format="%d", width="small"),
        "go": st.column_config.TextColumn("Send them to", help="The shelter nearest most homes of the street in the "
                                                               "10 km plan: a candidate site, not an official one"),
        "addr": "Shelter address",
        "km": st.column_config.NumberColumn("km", format="%.1f", width="small", help="By road, about: straight line × 1.3")})
    cl = live.closures()
    cl = cl[cl.municipality == t.municipality]
    st.markdown("**Roads closed:** " + (", ".join(cl.name.fillna(cl.osm_id).astype(str)) + ". Send people round them."
                                         if len(cl) else "none in this town."))
    st.page_link("views/checkin.py", label="Open the Door-knock list, home by home", icon=":material/door_front:")


def how(text):
    """One collapsed method note at the end of a tab."""
    with st.expander("How this is computed", icon=":material/info:"):
        st.caption(text)


# ================================================================== the detail, one tab per step that broke in 2021
out, first, shel_tab, order, v3d = st.tabs([":orange[:material/route:] Getting out",
                                            ":violet[:material/elderly:] Evacuate first",
                                            ":green[:material/home_health:] Shelters",
                                            ":red[:material/campaign:] Orders & message",
                                            ":blue[:material/landscape:] 3D"])

with out:
    if len(ev):
        e = ev.iloc[0]
        c = st.container(key="kpi_out").columns(3)
        c[0].metric("Leave the water on foot", f"{e.exit_p90_min_4kmh:.0f} min", border=True,
                    help=f"9 in 10 residents; half within {e.exit_med_min_4kmh:.0f} min. "
                         f"{e.exit_p90_min_3kmh:.0f} min at an older person's pace (3 km/h).")
        c[1].metric("Reach the shelter", f"{e.route_p90_min:.0f} min", border=True,
                    help=f"9 in 10 residents, on foot or by bus; half within {e.route_med_min:.0f} min. Bus at 30 km/h "
                         "without boarding: a minimum.")
        c[2].metric("Routes back through the water", f"{e.reroute_share:.0%}", border=True,
                    help=f"Share of residents whose route to the shelter crosses the {ZONE} again, over "
                         f"{int(e.flood_bridges_used)} bridges in it.")
        st.caption("Road times are a minimum: buses at 30 km/h, no boarding, no traffic.")
        st.markdown(f"- **Leave before the river rises:** {e.reroute_share:.0%} of routes go back through the {ZONE}.\n"
                    f"- **Busiest road** (the widest line on the map): {road(e.busiest_road)}, about "
                    f"{about(e.busiest_road_people)} people {'on foot' if e.busiest_road_mode == 'walk' else 'by bus'}. "
                    "Put a marshal there.")
    else:
        st.caption(f"Road simulation only for towns with at least 300 residents in the {ZONE}.")
    how(f"Road simulation on today's OpenStreetMap roads: residents spread evenly over the streets in the {ZONE}, "
        "walking 4 km/h, each sent to the shelter in the plan for this flood; buses at 30 km/h without boarding. "
        "Bridges: OpenStreetMap bridges inside the zone that a route uses. In the zone does not mean damaged.")

with first:
    if len(weak):
        nearest = recv.sort_values("km").drop_duplicates("from_name").set_index("from_name")
        st.markdown(f":violet[:material/local_hospital:] **{pl(len(weak), 'hospital or care home', 'hospitals and care homes')} "
                    f"in the {ZONE}: evacuate first**",
                    help="Receiving sites lie outside the 500-year zone, so they hold for every flood. Free beds there "
                         "are not in the data: confirm with each operator.")
        st.dataframe(pd.DataFrame({
            "Site": weak.name.values, "Type": weak.type.values,
            "Flooded from": [f"{r}-year flood" for r in weak.rp],
            "Nearest dry site of the same kind": [f"{nearest.to_name[n]} ({nearest.km[n]:.1f} km)" if n in nearest.index
                                                  else "none in reach" for n in weak.name]}),
            hide_index=True, column_config={"Flooded from": st.column_config.TextColumn(
                help="The most frequent flood whose zone reaches the site: a 10-year site floods first")})
    else:
        st.markdown(f":violet[:material/local_hospital:] **No hospital or care home in the {ZONE} here.** "
                    "Still check sites at the edge of the zone.")
    if len(schools):
        st.markdown(f":violet[:material/school:] **{pl(len(schools), 'school', 'schools')} in the {ZONE}: close "
                    "them, and do not use them as shelters**")
        st.dataframe(pd.DataFrame({"School": schools.name.values, "Flooded from": [f"{r}-year flood" for r in schools.rp]}),
                     hide_index=True)

    # homes with no upper floor: OBAT height under ~4.5 m; 2.5 m is OBAT's fill-in value, so it counts as unknown
    hb = B3D[(B3D.municipality == t.municipality) & (B3D.area == t.area) & B3D[f"in_{V}"]]
    homes = hb[hb.use == 1]
    one = homes[(homes.storeys == 1) & (homes.height_m != 2.5)]
    unk = int((homes.height_m == 2.5).sum())
    old = int((homes.epoch == 1).sum())       # GHS-OBAT construction period of the 100 m area: before 1980
    nonres = int((hb.use == 2).sum())
    st.markdown(":red[:material/house:] **Homes to knock on first**",
                help="People without a car and those who cannot leave alone are in no dataset: they need the "
                     "municipality's own list.")
    c = st.container(key="homes_row").columns(3)
    c[0].metric("Single-storey homes", fmt(len(one)), border=True,
                help=f"No upper floor to escape to if the water comes fast: knock on these doors first. {fmt(unk)} more "
                     "homes have no reliable height.")
    c[1].metric("Homes in old neighbourhoods", f"{fmt(old)} of {fmt(len(homes))}", border=True,
                help="Neighbourhood first built up before 1980 (100 m area), not the age of each house.")
    c[2].metric("Shops and workshops", fmt(nonres), border=True,
                help="Non-residential buildings: warn small businesses too, and tell them where to move stock and "
                     "vehicles.")
    if len(homes):
        hv = homes.assign(single=(homes.storeys == 1) & (homes.height_m != 2.5),
                          tname=lambda d: d.single.map({True: "Single-storey home", False: "Home with an upper floor"}),
                          tinfo=lambda d: [f"about {h:.0f} m high" if h != 2.5 else "height unknown" for h in d.height_m])
        hv["c"] = [core.rgb(core.EVACUATE) if x else [142, 142, 147, 200] for x in hv.single]
        hv["z"] = hv.height_m.clip(lower=3)
        st.pydeck_chart(pdk.Deck(
            layers=[pdk.Layer("GeoJsonLayer", flood[(t.area, V)], filled=True,
                              get_fill_color=core.rgb(core.RP_COL[V], 60), stroked=False),
                    pdk.Layer("ColumnLayer", hv, get_position=["lon", "lat"], get_elevation="z", elevation_scale=6,
                              radius=7, get_fill_color="c", pickable=True, extruded=True)],
            initial_view_state=pdk.ViewState(longitude=homes.lon.median(), latitude=homes.lat.median(), zoom=14.2,
                                             pitch=55, bearing=-20),
            map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "<b>{tname}</b><br/>{tinfo}"},
            views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=420)
        st.caption(f":red[●] Single-storey home · :gray[●] Home with an upper floor · :blue[■] {RP}-year flood zone")
    how(f"Care sites: OpenStreetMap hospitals, care homes and schools inside the {ZONE} (at least 5 % of the site in "
        "the 500-year zone); the nearest dry site of the same kind is a straight line, outside the 500-year zone. "
        f"Homes: GHS-OBAT buildings in the {ZONE}; "
        "single-storey = under about 4.5 m high; 2.5 m is OBAT's fill-in value, so those count as unknown. Column "
        "height on the map is the building height ×6. Old neighbourhoods: GHS-OBAT construction period of the 100 m "
        "area. Not in any dataset: age, income, disability or who lives alone.")

with shel_tab:
    st.markdown(f":green[:material/home_health:] **Where {t['name']} goes: {pl(len(plan), 'dry shelter', 'dry shelters')}**",
                help=f"One plan that fits the most people in (max-flow, 10 km straight line from each home), the "
                     f"biggest first, using only sites outside the {ZONE}. Numbers match the plan map.")
    st.caption("Candidates, not official shelters: confirm keys, staff and access with each owner.")
    if len(plan):
        st.dataframe(plan[["n", "shelter", "km", "people", "places", "shared"]], hide_index=True,
                     height=min(35 * len(plan) + 38, 420),
                     column_config={
                         "n": st.column_config.NumberColumn("#", width=36),
                         "shelter": st.column_config.TextColumn("Dry shelter", width="large"),
                         "km": st.column_config.NumberColumn("Centre km", format="%.1f", width="small",
                                                             help="Straight line from the town centre. The 10 km "
                                                                  "limit is from each home, so some shelters are "
                                                                  "further from the centre."),
                         "people": st.column_config.NumberColumn("Send", format="%d", width="small",
                                                                 help="People from this town sent here"),
                         "places": st.column_config.NumberColumn("Places", format="%d", width="small",
                                                                 help="All places, rough estimate"),
                         "shared": st.column_config.NumberColumn("Shared", format="%d", width="small",
                                                                 help="Number of other towns sent here too: agree who uses it")})
    else:
        st.info("No dry candidate shelter within 10 km in the data. Ask the neighbouring municipalities.")
    spare_beds()
    st.markdown(f":green[:material/search:] **All candidate sites near {t['name']}**",
                help=f"Every candidate site outside the {ZONE}, not only those in the plan: the 25 nearest to the town "
                     "centre, or all of them by size. Select a row to see it on the map.")
    shelter_list.render(t, V)
    how("Shelters are OpenStreetMap schools, sports halls and civic buildings with at least 200 m² of floor, outside "
        f"the EFAS {RP}-year zone (a site inside a zone is not used in that flood): candidates, not official shelters. "
        "Places: floor area × 50 % "
        "usable ÷ 4 m² per person, an order of magnitude. The plan is one max-flow share-out that fits the most "
        f"people within 10 km (straight line). Source: {core.AS_OF['osm']}. Map © OpenStreetMap contributors, © CARTO.")

# message: the two biggest shelters within 1.5 km for walkers (else the nearest), the biggest farther one for the bus
near = (plan[plan.km <= 1.5].head(2) if (plan.km <= 1.5).any() else plan.nsmallest(2, "km")).shelter.tolist()
far_ = plan[plan.km > 1.5].sort_values("people", ascending=False).shelter.head(1).tolist() or plan.shelter.tail(1).tolist()
fill = dict(town=t["name"], near=near or ["[shelter]"], far=far_[0] if far_ else "[shelter]",
            line="[help line]")
with order:
    st.markdown(f":red[:material/gavel:] **Who does what in {CC[cc]}**",
                help="Team summary of the national crisis rules, not challenge data. In 2021 the warning reached few "
                     "of the people who give these orders in time: check this against the municipality's emergency "
                     "plan and fill in names and deputies there.")
    st.markdown("| Role | Who | What to do |\n|---|---|---|\n"
                + "\n".join(f"| **{r}** | {w} | {h} |" for r, w, h in CHAIN[cc]))

    st.markdown(":red[:material/campaign:] **Warning message**",
                help="Draft for BE-Alert, NL-Alert or cell broadcast; copy with the icon. Walkers are sent to the two "
                     "largest shelters within 1.5 km, the bus to the largest one farther away.")
    line = st.text_input("Help line for people who cannot leave alone", placeholder="e.g. the municipal crisis number",
                         key="ev_line").strip()
    fill["line"] = line or "[help line]"
    langs = [LOCAL_LANG[cc], "English"]
    lang = st.segmented_control("Language", langs, default=langs[0], key=f"ev_lang_{cc}", label_visibility="collapsed")
    lang = lang or langs[0]
    text = MSG[lang].format(**{**fill, "near": OR[lang].join(fill["near"])})
    st.code(text, language=None, wrap_lines=True)
    st.caption("Draft, AI-assisted and checked by the team: a native speaker and the communication officer approve it "
               "before use.")
    crews()

    st.markdown(":red[:material/checklist:] **Plan and drill: before the flood season**")
    for k, p_ in enumerate(PREPARE):
        st.checkbox(p_, key=f"prep_{cc}_{k}")
    rows = "".join(f"<tr><td>{r.n}</td><td>{escape(r.shelter)}</td><td>{r.km:.1f}</td><td>{r.people:.0f}</td>"
                   f"<td>{r.places:.0f}</td><td>{r.shared}</td></tr>" for r in plan.itertuples())
    who = "".join(f"<tr><td><b>{r}</b></td><td>{escape(w)}</td><td>{escape(h)}</td></tr>" for r, w, h in CHAIN[cc])
    first_rows = "".join(f"<li>{escape(r.name)} ({r.type}, flooded from a {r.rp}-year flood)</li>"
                         for r in weak.itertuples()) or f"<li>None in the {ZONE}</li>"
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Evacuation plan · {escape(t['name'])}</title>
<style>body{{font:14px/1.45 -apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#1d1d1f;max-width:800px;margin:2rem auto;
padding:0 1rem}}h1{{font-size:1.6rem;margin:0}}h2{{font-size:1.1rem;margin:1.6rem 0 .4rem}}table{{border-collapse:collapse;
width:100%}}td,th{{border-bottom:1px solid #ddd;padding:.3rem .4rem;text-align:left;vertical-align:top}}
.n{{color:#4f6580;font-size:.85rem}}.box{{border:1px solid #ccc;border-radius:8px;padding:.6rem .8rem}}</style></head><body>
<h1>Evacuation plan · {escape(t['name'])}</h1>
<p class="n">Draft for a {RP}-year river flood, {date.today():%d %b %Y}. {escape(note)}</p>
<h2>Who leaves</h2><p>About {about(t.people)} residents live in the {ZONE}. {about(walk)} can walk to a shelter
within 1.5 km; {about(ride)} need transport (up to 10 km); {about(left)} have no place within 10 km.</p>
<h2>Evacuate first</h2><ul>{first_rows}</ul>
<p>In the {ZONE}: {fmt(len(one))} single-storey homes (no upper floor to escape to; {fmt(unk)} with no reliable
height), {fmt(old)} homes in neighbourhoods built before 1980, {fmt(nonres)} non-residential buildings.</p>
<h2>Where they go</h2><table><tr><th>#</th><th>Dry shelter</th><th>km from centre</th><th>People sent</th>
<th>Places in all</th><th>Other towns sent here</th></tr>{rows}</table>
<h2>Who gives the order ({CC[cc]})</h2><table>{who}</table>
<p class="n">Team summary of national rules, not challenge data. Fill in names, deputies and phone numbers from the
municipality's emergency plan.</p>
<h2>Warning message</h2><div class="box">{escape(text)}</div>
<h2>Before the flood season</h2><ul>{''.join(f'<li>{escape(p)}</li>' for p in PREPARE)}</ul>
<h2>Limits</h2><p class="n">Residents: GHS-POP 2020 spread over homes, an order of magnitude. Shelters: OpenStreetMap
candidates outside the {ZONE}, not official; capacity = floor area × 50 % ÷ 4 m². Distances are
straight lines from the town centre. No data on age, income or disability.</p></body></html>"""
    st.download_button("Download the town plan (print it or save as PDF)", doc,
                       file_name=f"evacuation_plan_{t['name'].replace(' ', '_')}.html", mime="text/html",
                       icon=":material/download:", type="primary")
    how("Roles: a team summary of each country's crisis rules (BE, NL, DE), not challenge data. Message: a "
        "team-written template, AI-assisted (ai_log.md 15), filled with this town's shelters from the plan. The "
        "download holds the whole town plan on one printable page.")

with v3d:
    view3d.render(t, V)

# ================================================================== the region call order (also in the Crisis room)
st.divider()
with st.expander("First action across the region: call these towns, in this order" if P else
                 f"Across the region in a {RP}-year flood: the towns that would need help first", icon=":material/call:"):
    top = calls.iloc[0]
    st.markdown(f"Start with {top.short} and {top.call}: book buses for about {about(top.no_shelter)} "
                "residents who cannot walk to a shelter"
                + (f", and start moving its {top.care} hospitals and care homes" if top.care else "") + ".")
    st.dataframe(calls[["short", "call", "no_shelter", "care"]].assign(no_shelter=calls.no_shelter.map(about)),
                 hide_index=True, key="ev_calls", on_select=pick_call, selection_mode="single-row",
                 column_config={"short": st.column_config.TextColumn("Town (and its mayor)"),
                                "call": st.column_config.TextColumn("Also call"),
                                "no_shelter": st.column_config.TextColumn("No shelter on foot",
                                                                          help=f"Residents in the {ZONE} with no free "
                                                                               "shelter place within 1.5 km"),
                                "care": st.column_config.NumberColumn("Care sites to evacuate", format="%d")})
    st.caption("Ordered by residents with no shelter place on foot: they need transport, so these calls take longest "
               f"to act on. {RP}-year flood zone. Click a town to open its plan above.")

core.next_steps("plan")
