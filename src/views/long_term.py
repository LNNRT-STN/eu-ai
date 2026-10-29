"""Long term: the gaps the 2021 data shows, the measure that closes each one, and the money that exists for it.
Gaps come from outputs/data/ (q4_headline.json, app_towns.csv). Every amount comes from docs/BUDGETS.md (desk research,
external sources, URL per row): copied as published, never summed across rows, 'partly' where the source is secondary."""
import pandas as pd
import streamlit as st

import anna
import core
from core import about

head, towns, crit, *_ = anna.load()
obs, mod = head["worst"]["observed"], head["worst"]["modelled_vesdre"]
T = towns[towns.variant == "worst"]
gap_towns = int((T.no_shelter >= 50).sum())
care = head["worst"]["sites"]["vulnerable"]
schools = head["worst"]["sites"]["schools"]
inf = pd.read_csv(core.DATA / "infra_in_flood.csv")   # notebooks/infra.py: today's network inside the 2021 water
rail_obs = inf[(inf.kind == "rail") & ~inf.area.isin(anna.MODELLED)].km_in_flood.sum()
rail_mod = inf[(inf.kind == "rail") & inf.area.isin(anna.MODELLED)].km_in_flood.sum()
br = inf[inf.kind.isin(["bridge_road", "bridge_rail"])].groupby(inf.area.isin(anna.MODELLED))["count"].sum()
b_obs, b_mod = T[~T.area.isin(anna.MODELLED)].buildings.sum(), T[T.area.isin(anna.MODELLED)].buildings.sum()

EC = "https://ec.europa.eu/regional_policy/whats-new/newsroom/15-12-2022-eu-cohesion-policy-eur718-5-million-to-support-seven-member-states-following-devastating-natural-disasters-of-2021_en"
ZDF = "https://www.zdfheute.de/politik/deutschland/ahrtal-flutkatastrophe-hochwasser-wiederaufbau-hilfe-finanzministerium-100.html"
NRW = "https://www.land.nrw/pressemitteilung/2021-bis-2026-fuenf-jahre-nach-der-starkregen-und-hochwasserkatastrophe-viel"
WAL = "https://wallonie.be/fr/actualites/5-ans-apres-les-inondations-de-2021-ou-en-est"
UVCW = "https://uvcw.be/environnement/actus/art-10243"
AHR = "https://www.wochenblatt-reporter.de/c-lokales/absage-fuers-ahrtal-becken-nicht-aus-aufbauhilfefonds_a879494"
KEEP = "https://keep.eu/programmes/311"
CALL = "https://www.hezelburcht.com/en/news/8th-interreg-meuse-rhine-call-for-cross-border-cooperation-opens-in-september-2026/"
UCPM = "https://civil-protection-knowledge-network.europa.eu/2026-kapp-calls-proposals-open"
SIREN = "https://www.bundestag.de/presse/hib/kurzmeldungen-1195188"
BREMEN = "https://www.rathaus.bremen.de/sixcms/media.php/13/20250624_top%2011_Warninfrastruktur_Bund_Laender_Vereinbarung.pdf"
WRL = "https://zoek.officielebekendmakingen.nl/stcrt-2022-19467.pdf"
AUG = "https://augustinum.de/fileadmin/Presse/Presseinfos/Augustinum-260128-BadNeuenahr-Renovierung.pdf"
DB = "https://www.deutschebahn.com/de/presse/pressestart_zentrales_uebersicht/Die-Bahn-ist-zurueck-im-Ahrtal--13699724"
INFRABEL = "https://infrabel.be/sites/default/files/generated/files/report/Rapport%20annuel%20de%20se%CC%81curite%CC%81%202021%20FR.pdf"
BMV = "https://www.bmv.de/SharedDocs/DE/Artikel/K/zuege-fahren-wieder-gerolstein-koeln.html"
WALREP = "https://www.wallonie.be/sites/default/files/2022-11/Inondations%20rapport%20de%20la%20commission%20parlementaire.pdf"

src = lambda url, label, ok=True: f"[{label}]({url})" + ("" if ok else " :orange-badge[partly verified]")

st.title("Long term")
st.caption("What to fix before the next flood, and the money that already exists for it.")
st.info("**Rebuilding money exists; prevention and preparedness are where the gaps are.** "
            f"In the data: {about(obs['no_shelter'])} residents in the 2021 water have no shelter place on foot "
            f"(plus {about(mod['no_shelter'])} modelled in the Vesdre), across {gap_towns} towns; {care} hospitals and "
            f"care homes sat in the water. Five years on, about a fifth of Germany's rebuilding fund is paid out, and "
            f"the Ahr's three priority retention basins (about €300 m) have no funding.", icon=":material/info:")

ROWS = [
    ("Shelter places out of walking reach",
     f"{about(obs['no_shelter'])} residents observed, {about(mod['no_shelter'])} modelled (Vesdre). Most have a place "
     "within 10 km by bus.",
     "Sign shelter and bus agreements between neighbouring municipalities, across the border where the nearest "
     "shelter is.",
     f"Interreg Meuse-Rhine 2021-27: €176.0 m programme, objective “climate adaptation, disaster risk prevention” "
     f"({src(KEEP, 'keep.eu')}); next call 21 Sep–16 Dec 2026 ({src(CALL, 'call notice', False)}). EU civil "
     f"protection prevention call: €10.6 m in 2026, next round early 2027 ({src(UCPM, 'UCPM', False)})."),
    ("Hospitals and care homes in the water",
     f"{care} sites, at least 5 % of the site in the 2021 water; {schools} schools as well.",
     "A move-out plan per site (beds, transport, receiving site), then flood-proofing or relocation.",
     "No published unit cost for flood-proofing a care home. For scale only: restoring the Augustinum care home in "
     f"Bad Neuenahr costs about €40 m (restoration, not flood-proofing; {src(AUG, 'Augustinum', False)})."),
    ("Warnings that did not become instructions",
     "Wallonia's inquiry found the warning chain from the met office to citizens failed "
     f"({src(WALREP, 'parliament report, 2022', False)}).",
     "Sirens and cell broadcast in every flood zone; the message templates on the Evacuation plan, drilled once a year.",
     f"German siren programme: €88 m for about 5,000 sirens ({src(SIREN, 'Bundestag', False)}); about €10,850 per "
     f"siren in Bremen ({src(BREMEN, 'Bremen Senate', False)})."),
    ("Homes that will flood again",
     f"{about(b_obs)} buildings in the observed 2021 water, {about(b_mod)} in the modelled Vesdre zone.",
     "Buy out and demolish the most exposed homes; no rebuilding in the flow path.",
     f"Wallonia: €25 m for 9 communes (Verviers, Pepinster, Trooz, Chaudfontaine…) until July 2028 "
     f"({src(WAL, 'wallonie.be')})."),
    ("Railways and bridges in the flow path",
     f"Today's network: {rail_obs:.0f} km of track and {int(br.get(False, 0))} road and rail bridges in the observed "
     f"2021 water; {rail_mod:.0f} km and {int(br.get(True, 0))} bridges in the modelled Vesdre zone.",
     "Rebuild bridges with a wider span and higher deck; plan road evacuation, since trains will not run.",
     f"Ahr valley line: 22 bridges, 5 tunnels and 10 stations rebuilt for about €590 m, open again 14 Dec 2025 "
     f"({src(DB, 'Deutsche Bahn')}). Belgium: over 200 km of track on 13 lines damaged, about €60 m in three "
     f"months ({src(INFRABEL, 'Infrabel')}). Eifel line Gerolstein–Kall back in 2025, 20 bridges renewed "
     f"({src(BMV, 'transport ministry')})."),
    ("Too much water, too fast",
     "Stalled rain over steep, sealed valleys; models underestimated it.",
     "Retention basins upstream, and space for the river.",
     f"Ahr: 3 priority basins about €300 m, unfunded; not eligible under Germany's rebuilding fund "
     f"({src(AHR, 'Wochenblatt', False)}). Wallonia: €13 m for retention basins in 2026 ({src(WAL, 'wallonie.be')}). "
     f"Limburg (NL): €600 m regional water-system agreement, 2022 ({src(WRL, 'Staatscourant', False)})."),
]
for g, e, m, f in ROWS:
    with st.container(border=True):
        c = st.columns([1.1, 1.2, 1.4])
        c[0].markdown(f"**{g}**  \n{e}")
        c[1].markdown(f":gray[Measure]  \n{m}")
        c[2].markdown(f":gray[Money that exists]  \n{f}")

st.subheader("Money already committed since 2021")
st.markdown(f"""| Fund | Amount | For |
|---|---|---|
| **EU Solidarity Fund** | Germany €612.6 m, Belgium €87.7 m, Netherlands €4.7 m, agreed Dec 2022 · {src(EC, 'European Commission')} | Repair |
| **Germany: rebuilding fund (Aufbauhilfe 2021)** | Up to €30 bn; about €6.2 bn paid out by July 2026 (NRW €2.6 bn, RLP €2.5 bn) · {src(ZDF, 'ZDF, citing the finance ministry')} | Repair |
| **North Rhine-Westphalia** | About €4.7 bn approved of about €12.3 bn available · {src(NRW, 'Land NRW')} | Repair |
| **Wallonia** | €2.8 bn direct cost to the regional budget; losses over €5 bn · {src(UVCW, 'UVCW')} | Repair |""")
st.caption("External sources, not challenge data: desk research of 29 Oct 2026, every row in "
        "docs/BUDGETS.md with its URL. Amounts are copied as published and never added up across rows (different "
        "scopes and dates). “Partly verified” means a secondary source or a search snippet: re-check before citing.")
