"""Evacuation plan, one town at a time: if the July 2021 water came back, who leaves, which dry shelter they go to,
who gives the order, and the message that tells them. Answers the 2021 failures the team listed: unclear roles across
levels, warnings that never became instructions, missing local plans and drills, people who could not leave alone.
Numbers: outputs/data/ (app_towns: walking plan; bus_plan: the 10 km max-flow plan, per shelter; critical_sites;
receiving_sites). The roles and the message are team text, not data: labelled on the page and in the download."""
import json
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
HOUSE = pd.read_csv(core.DATA / "housing_age.csv")          # notebooks/housing_age.py (GHS-OBAT construction period)
B3D = pd.read_parquet(core.DATA / "buildings_3d.parquet")   # every OBAT building in the 2021 water, with height
EVAC = pd.read_csv(core.DATA / "evac_towns.csv")             # notebooks/evac_sim.py: road simulation, towns >= 300 people
INFRA = pd.read_csv(core.DATA / "infra_in_flood.csv")        # notebooks/infra.py: today's rail and bridges in the 2021 water
EDGES = json.loads((core.DATA / "evac_edges.geojson").read_text())
RAIL = json.loads((core.DATA / "infra_rail.geojson").read_text())
feats = lambda g, m: {"type": "FeatureCollection", "features": [f for f in g["features"]
                                                                 if f["properties"]["municipality"] == m]}
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


st.title("Evacuation plan")
st.caption("If the July 2021 flood came back: who leaves, where they go, who gives the order.")


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
        st.session_state.town = st.session_state._town = calls.municipality.iloc[rows[0]]


st.subheader("First action: call these towns, in this order")
st.dataframe(calls[["short", "call", "no_shelter", "care"]].assign(no_shelter=calls.no_shelter.map(about)),
             hide_index=True, key="ev_calls", on_select=pick_call, selection_mode="single-row",
             column_config={"short": st.column_config.TextColumn("Town (and its mayor)"),
                            "call": st.column_config.TextColumn("Also call"),
                            "no_shelter": st.column_config.TextColumn("No shelter on foot",
                                                                      help="Residents in the 2021 water with no free "
                                                                           "shelter place within 1.5 km"),
                            "care": st.column_config.NumberColumn("Care sites to evacuate", format="%d")})
st.caption("Ordered by residents with no shelter place on foot: they need transport, so these calls take longest to "
           "act on. \\* modelled (Vesdre). Click a town, or pick one in the sidebar, to open its plan below.")
st.divider()
pick = T[T.municipality == st.session_state.get("town")]
t = (pick if len(pick) else T).iloc[0]
st.header(t.label)
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

# ------------------------------------------------------------------ getting out: road simulation + rail in the water
# OSM falls back to the road class when a road has no name
road = lambda n: f"An unnamed {n} road" if n in {"motorway", "trunk", "primary", "secondary", "tertiary", "residential",
                                                   "unclassified", "service", "living_street", "footway", "path", "track"} else n
ev = EVAC[(EVAC.municipality == t.municipality) & (EVAC.area == t.area)]
inf = INFRA[(INFRA.municipality == t.municipality) & (INFRA.area == t.area)]
rail_km = inf.loc[inf.kind == "rail", "km_in_flood"].sum()
stations = int(inf.loc[inf.kind == "station", "count"].sum())
bridges = int(inf.loc[inf.kind.isin(["bridge_road", "bridge_rail"]), "count"].sum())
verdict = (f"{t['name']}: move about {about(t.people)} residents to {len(plan)} dry shelters"
           + (f"; {about(left)} still have no place within 10 km" if left >= 5 else ", all of them have a place"))
sub = (f"{about(walk)} can walk to one (within 1.5 km); {about(ride)} need a bus or car (up to 10 km)."
       + (f" Evacuate {len(weak)} hospital{'s' if len(weak) != 1 else ''} or care home{'s' if len(weak) != 1 else ''} "
          "first." if len(weak) else ""))
if len(ev) and ev.reroute_share.iloc[0] >= .5:
    sub += (f" {ev.reroute_share.iloc[0]:.0%} of routes to a shelter cross the 2021 water again: leave before the river "
            "rises.")
note = ("Modelled: the satellite missed the Vesdre, so the EFAS 500-year flood zone stands in."
        if modelled else "Observed: all Copernicus satellite passes of July 2021, a floor, not the peak.")


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
        txt = (f"**{g.gauge}, next 30 days: {name.lower()}** · peak {g.pct_2021:.0%} of its July 2021 peak on "
               f"{g.peak_day:%a %d %b}" + (f"; wettest run: {forecast.LEVELS[g.level_worst][0].lower()}"
                                           if g.level_worst > g.level else "")
               + f". A model heads-up, not a warning: official warnings come from {OFFICIAL[cc]}.")
    st.caption(f":material/water: {txt}")


river_line()
urgent = left >= 5 or len(weak) or (len(ev) and ev.reroute_share.iloc[0] >= .5)
(st.error if urgent else st.info)(f"**{verdict}.** {sub}", icon=":material/warning:" if urgent else ":material/info:")

m1, m2, m3 = st.columns(3)
m1.metric("Walk to a shelter", about(walk), help="Shelter within 1.5 km of home", border=True)
m2.metric("Need a bus or car", about(ride), help="Their shelter is 1.5–10 km from home", border=True)
m3.metric("No place within 10 km", about(left), help="Ask the next municipality" if left >= 5 else "Everyone fits",
          border=True)
st.caption(note)

# ------------------------------------------------------------------ map + shelter list
MAP_H = 470
lm, rm = st.columns([3, 2], gap="small")
with lm:
    a = 70 if modelled else 140
    layers = [pdk.Layer("GeoJsonLayer", flood[(t.area, V)], filled=True, stroked=True, line_width_min_pixels=1,
                        get_fill_color=[0, 113, 227, a], get_line_color=[0, 90, 200, 200])]
    layers += [pdk.Layer("GeoJsonLayer", feats(RAIL, t.municipality), get_line_color=[29, 29, 31, 220],
                         line_width_min_pixels=3),
               pdk.Layer("GeoJsonLayer", feats(EDGES, t.municipality), get_line_color=core.rgb("#c93400", 230),
                         line_width_min_pixels=4)]
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
    st.caption(":green[●] Dry shelter, size = people sent there (the ten largest numbered as in the list)  \n"
               + (":red[●] Hospital, care home or school in the 2021 water · " if len(care) else "")
               + f":blue[■] 2021 water{' (modelled)' if modelled else ''} · "
               ":material/radio_button_unchecked: Town centre · :orange[━] Busiest evacuation roads · "
               ":material/remove: Railway in the 2021 water")
with rm:
    if len(plan):
        st.dataframe(plan[["n", "shelter", "km", "people", "places", "shared"]], hide_index=True,
                     height=min(35 * len(plan) + 38, MAP_H - 10),
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
st.caption("One plan that fits the most people in (max-flow, 10 km straight line). Shelters are OpenStreetMap "
           "schools, sports halls and civic buildings, dry in 2021 and in the 100-year model: candidates, not official "
           "shelters. Places: floor area × 50 % usable ÷ 4 m² per person.")


def spare_beds():
    """Beds residents offered (Offer a bed page) in this town or a town whose centre is within 10 km."""
    try:
        o = pd.read_csv(core.DATA.parents[1] / "data" / "host_offers.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return
    ctr = towns.drop_duplicates("municipality").set_index("municipality")[["lon", "lat"]]
    o = o[o.outside_2021.astype(bool) & o.municipality.isin(ctr.index)]
    if o.empty:
        return
    d = core.km(t.lon, t.lat, ctr.loc[o.municipality, "lon"].values, ctr.loc[o.municipality, "lat"].values)
    near_o = o[d <= 10]
    if len(near_o):
        n, h, old = int(near_o.beds.sum()), len(near_o), int(near_o.loc[near_o.older.astype(bool), "beds"].sum())
        st.success(f"**{n} spare bed{'s' if n != 1 else ''} offered by residents** within 10 km "
                   f"({h} home{'s' if h != 1 else ''}; {old} suit{'s' if old == 1 else ''} an older or less mobile "
                   "person). Not checked yet, and not counted in the shelter places: use them first for people who "
                   "cannot stay in a hall.", icon=":material/bed:")


spare_beds()

# ------------------------------------------------------------------ the steps that broke in 2021, one tab each

def getting_out():
    """Road simulation (towns with at least 300 residents in the water) and today's rail and bridges in the water."""
    if len(ev):
        e = ev.iloc[0]
        c = st.columns(3)
        c[0].metric("Leave the water on foot", f"{e.exit_p90_min_4kmh:.0f} min", border=True,
                    help=f"9 in 10 residents; half within {e.exit_med_min_4kmh:.0f} min. "
                         f"{e.exit_p90_min_3kmh:.0f} min at an older person's pace (3 km/h).")
        c[1].metric("Reach the shelter", f"{e.route_p90_min:.0f} min", border=True,
                    help=f"9 in 10 residents, on foot or by bus; half within {e.route_med_min:.0f} min. Bus at 30 km/h "
                         "without boarding: a minimum.")
        c[2].metric("Routes back through the water", f"{e.reroute_share:.0%}", border=True,
                    help=f"Share of residents whose route to the shelter crosses the 2021 water again, over "
                         f"{int(e.flood_bridges_used)} bridges in it.")
        st.markdown(f"- **Leave before the river rises:** {e.reroute_share:.0%} of routes go back through the 2021 water.\n"
                    f"- **Busiest road:** {road(e.busiest_road)}, about {about(e.busiest_road_people)} people "
                    f"{'on foot' if e.busiest_road_mode == 'walk' else 'by bus'}. Put a marshal there.")
    else:
        st.caption("Road simulation only for towns with at least 300 residents in the water.")
    st.markdown(f"- **Trains:** {rail_km:.1f} km of track" + (f" and {stations} station{'s' if stations != 1 else ''}"
                                                               if stations else "")
                + f" sat in the 2021 water: no train evacuation from here. {bridges} road and rail bridges in the water."
                if rail_km >= .1 else f"- **Trains:** no railway in the 2021 water here. {bridges} road bridges in it.")
    st.caption("Road simulation on today's OpenStreetMap roads: residents spread evenly over the streets in the 2021 "
               "water, walking 4 km/h, each sent to the shelter in the plan. In the water does not mean damaged.")


out, first, order, msg, prep = st.tabs(["Getting out", "Evacuate first", "Who gives the order", "Warning message",
                                        "Plan and drill"])
with out:
    getting_out()

with first:
    # homes with no upper floor: OBAT height under ~4.5 m; 2.5 m is OBAT's fill-in value, so it counts as unknown
    hb = B3D[(B3D.municipality == t.municipality) & (B3D.area == t.area)]
    homes = hb[hb.use == 1]
    one = homes[(homes.storeys == 1) & (homes.height_m != 2.5)]
    unk = int((homes.height_m == 2.5).sum())
    ha = HOUSE[(HOUSE.municipality == t.municipality) & (HOUSE.area == t.area)]
    old = int(ha.res_pre1980.sum()) if len(ha) else 0
    nonres = int(ha.nonres_in_flood.sum()) if len(ha) else 0
    c = st.columns(3)
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
            layers=[pdk.Layer("GeoJsonLayer", flood[(t.area, V)], filled=True, get_fill_color=[0, 113, 227, 60],
                              stroked=False),
                    pdk.Layer("ColumnLayer", hv, get_position=["lon", "lat"], get_elevation="z", elevation_scale=6,
                              radius=7, get_fill_color="c", pickable=True, extruded=True)],
            initial_view_state=pdk.ViewState(longitude=homes.lon.median(), latitude=homes.lat.median(), zoom=14.2,
                                             pitch=55, bearing=-20),
            map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "<b>{tname}</b><br/>{tinfo}"},
            views=[pdk.View(type="MapView", controller={"scrollZoom": False})]), height=420)
        st.caption(":red[●] Single-storey home · :gray[●] Home with an upper floor "
                   "(column height ∝ building height, ×6) · :blue[■] 2021 water")
    if len(weak):
        nearest = recv.sort_values("km").drop_duplicates("from_name").set_index("from_name")
        st.markdown("**Hospitals and care homes in the 2021 water: evacuate first**")
        st.dataframe(pd.DataFrame({
            "Site": weak.name.values, "Type": weak.type.values, "Under water": weak.share_of_site_flooded.values * 100,
            "Nearest dry site of the same kind": [f"{nearest.to_name[n]} ({nearest.km[n]:.1f} km)" if n in nearest.index
                                                  else "none in reach" for n in weak.name]}),
            hide_index=True, column_config={"Under water": st.column_config.NumberColumn(format="%d%%")})
    else:
        st.markdown("**No hospital or care home in the 2021 water here.** Still check sites at the edge of the flood.")
    if len(schools):
        st.markdown("**Schools in the 2021 water: close them, and do not use them as shelters**")
        st.dataframe(pd.DataFrame({"School": schools.name.values,
                                   "Under water": schools.share_of_site_flooded.values * 100}),
                     hide_index=True, column_config={"Under water": st.column_config.NumberColumn(format="%d%%")})
    st.caption("Not in any dataset: age, income, disability or who lives alone. People without a car and those who "
               "cannot leave alone need the municipality's own list. Free beds in receiving sites: confirm with each "
               "operator.")

with order:
    st.markdown(f"**Who does what in {CC[cc]}**\n\n| Role | Who | What to do |\n|---|---|---|\n"
                + "\n".join(f"| **{r}** | {w} | {h} |" for r, w, h in CHAIN[cc]))
    st.caption("Team summary of the national crisis rules, not challenge data. In 2021 the warning reached few of the "
               "people who give these orders in time: check this against the municipality's emergency plan and fill "
               "in names and deputies there.")

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
    st.caption("Draft for BE-Alert, NL-Alert or cell broadcast; copy with the icon. AI-assisted wording, checked by the "
               "team; have a native speaker and the communication officer approve it before use. Walkers: the two "
               "largest shelters within 1.5 km. Bus: the largest one farther away.")

with prep:
    st.markdown("**Before the flood season**")
    for k, p_ in enumerate(PREPARE):
        st.checkbox(p_, key=f"prep_{cc}_{k}")
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
<p>In the 2021 water: {fmt(len(one))} single-storey homes (no upper floor to escape to; {fmt(unk)} with no reliable
height), {fmt(old)} homes in neighbourhoods built before 1980, {fmt(nonres)} non-residential buildings.</p>
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
