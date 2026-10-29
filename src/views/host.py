"""Offer a bed: residents outside the flood zone offer a room or spare bed to people evacuated from it, a solidarity
register next to the official shelters. Prototype: no name, address or phone is stored, only the town, the beds and
who the host can take, under a reference code. A real roll-out is run by the municipality, which collects contacts
under the GDPR. Offers are kept on this machine in data/host_offers.csv (gitignored), never in the repository."""
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


towns = anna.load()[1]
munis = sorted(towns.municipality.unique(), key=anna.town)

st.title("Offer a bed")
st.caption("Live outside the flood zone? Offer a room or a spare bed to someone who has to leave home. Older and ill "
           "people rest better in a home than in a sports hall.")

left, right = st.columns([3, 2], gap="large")
with left, st.form("offer", border=False):
    muni = st.selectbox("Your town", munis, format_func=anna.town)
    beds = st.number_input("Beds you can offer", 1, 10, 1)
    fits = st.pills("You can take", list(FITS), format_func=FITS.get, selection_mode="multi")
    dry = st.checkbox("My home stayed dry in July 2021 and is on higher ground")
    st.caption("No name, address or phone here. You get a reference code: keep it, and give it to the municipality "
               "when it calls to match a guest.")
    sent = st.form_submit_button("Offer", type="primary", icon=":material/volunteer_activism:")
if sent:
    if not dry:
        st.warning("Only homes that stayed dry can host. Thank you: you can still help by checking on neighbours.")
    else:
        code = secrets.token_hex(3).upper()
        row = dict(code=code, when=datetime.now().isoformat(timespec="minutes"), municipality=muni, beds=int(beds),
                   **{k: k in (fits or []) for k in FITS}, outside_2021=True)
        FILE.parent.mkdir(exist_ok=True)
        pd.concat([offers(), pd.DataFrame([row])]).to_csv(FILE, index=False)
        st.success(f"Thank you. Your reference code is **{code}**. Keep it to change or withdraw your offer.")

with right:
    o = offers()
    o = o[o.outside_2021.astype(bool)] if len(o) else o
    n = lambda k, w: f"{k} {w}{'s' if k != 1 else ''}"
    st.metric("Beds offered so far, all towns", int(o.beds.sum()) if len(o) else 0, border=True,
              help=n(len(o), "home"))
    st.markdown("\n".join(f"- {FITS[k]}: {n(int(o.loc[o[k].astype(bool), 'beds'].sum()) if len(o) else 0, 'bed')}"
                          for k in FITS))
    with st.expander("Withdraw an offer"):
        code = st.text_input("Reference code", max_chars=6).strip().upper()
        if st.button("Withdraw", disabled=not code):
            all_ = offers()
            if code in set(all_.code.astype(str)):
                all_[all_.code.astype(str) != code].to_csv(FILE, index=False)
                st.success("Offer withdrawn.")
                st.rerun()
            else:
                st.error("No offer with this code. Check the six characters.")
st.caption("Prototype of a solidarity register, run in practice by the municipality: it checks each "
        "host, collects contacts under the GDPR and matches guests. Offered beds are not shelters and are not counted "
        "in the shelter plan; the Evacuation plan shows them next to it.")
