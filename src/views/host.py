"""Offer a bed: residents outside the flood zone offer a room or spare bed to people evacuated from it, a solidarity
register next to the official shelters. Prototype: no name, address or phone is stored, only the town, the beds and
who the host can take, under a reference code. A real roll-out is run by the municipality, which collects contacts
under the GDPR. Offers are kept on this machine in data/host_offers.csv (gitignored), never in the repository.

A tab of the resident page (views/resident.py): render() draws it."""
import secrets
from datetime import datetime

import pandas as pd
import streamlit as st

import anna
import core

FILE = core.DATA.parents[1] / "data" / "host_offers.csv"
COLS = ["code", "when", "municipality", "beds", "step_free", "older", "family", "pets", "outside_2021"]
FITS = {"step_free": "Step-free access", "older": "Older or less mobile person", "family": "Family with children",
        "pets": "Pets welcome"}


def offers():
    try:
        return pd.read_csv(FILE, dtype={"code": str})
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=COLS)


def render(muni=None):
    """The offer form and the running count. muni: the town to preselect (from the address typed on the page)."""
    towns = anna.load()[1]
    munis = sorted(towns.municipality.unique(), key=anna.town)
    st.markdown("**Live outside the flood zone? Offer a room or a spare bed to someone who has to leave home.**",
                help="Older and ill people rest better in a home than in a sports hall.")

    left, right = st.columns([3, 2], gap="large")
    with left, st.form("offer", border=False):
        town = st.selectbox("Your town", munis, format_func=anna.town, key=f"host_town_{muni}",
                            index=munis.index(muni) if muni in munis else None, placeholder="Pick your town")
        beds = st.number_input("Beds you can offer", 1, 10, 1, key="host_beds")
        fits = st.pills("You can take", list(FITS), format_func=FITS.get, selection_mode="multi", key="host_fits")
        dry = st.checkbox("My home stayed dry in July 2021 and is on higher ground", key="host_dry")
        st.caption("No name, address or phone: you get a reference code.",
                   help="Keep the code: the municipality asks for it to match a guest, and you need it to withdraw "
                        "the offer.")
        sent = st.form_submit_button("Offer", type="primary", icon=":material/volunteer_activism:")
    if sent:
        if town is None:
            left.warning("Pick your town first.")
        elif not dry:
            left.warning("Only homes that stayed dry can host. Thank you: you can still help by checking on "
                         "neighbours.")
        else:
            code = secrets.token_hex(3).upper()
            row = dict(code=code, when=datetime.now().isoformat(timespec="minutes"), municipality=town, beds=int(beds),
                       **{k: k in (fits or []) for k in FITS}, outside_2021=True)
            FILE.parent.mkdir(exist_ok=True)
            pd.concat([offers(), pd.DataFrame([row])]).to_csv(FILE, index=False)
            left.success(f"Thank you. Your reference code is **{code}**. Keep it to change or withdraw your offer.")

    with right:
        o = offers()
        o = o[o.outside_2021.astype(bool)] if len(o) else o
        n = lambda k, w: f"{k} {w}{'s' if k != 1 else ''}"
        st.metric(":green[:material/bed:] Beds offered so far, all towns", int(o.beds.sum()) if len(o) else 0,
                  border=True, help=n(len(o), "home"))
        st.markdown("\n".join(f"- {FITS[k]}: {n(int(o.loc[o[k].astype(bool), 'beds'].sum()) if len(o) else 0, 'bed')}"
                              for k in FITS))
        with st.expander("Withdraw an offer", icon=":material/undo:"):
            code = st.text_input("Reference code", max_chars=6, key="host_code").strip().upper()
            if st.button("Withdraw", disabled=not code, key="host_withdraw"):
                all_ = offers()
                if code in set(all_.code.astype(str)):
                    all_[all_.code.astype(str) != code].to_csv(FILE, index=False)
                    st.success("Offer withdrawn.")
                    st.rerun()
                else:
                    st.error("No offer with this code. Check the six characters.")
    st.caption("Offered beds are not shelters and are not counted in the shelter plan.",
               help="Prototype of a solidarity register. In practice the municipality runs it: it checks each host, "
                    "collects contacts under the GDPR and matches guests. The Town plan shows offered beds next to the "
                    "shelter plan.")
