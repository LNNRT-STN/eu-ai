"""Data-quality report: indicators with thresholds, status, likely root cause and who can fix it
(Fraud Analytics, Baesens et al., ch.7 p.345-347: indicators with high detection power and few false alarms,
then root cause and data owner). Reads outputs/data/qc_and_validation.json written by pipeline.py.
Run from eu-ai/:  .venv/Scripts/python.exe -I notebooks/dq_report.py
"""
import json
from pathlib import Path
import pandas as pd

QC = json.load(open("outputs/data/qc_and_validation.json"))
# indicator: (how to compute from one area's qc, WARN threshold, cause, owner)
IND = {
    "Residents not placed on any home (%)": (lambda q: q.get("population_not_on_any_home_pct"), 10,
        "Population cells with no residential building: border cells (other country's buildings not loaded) or OBAT undercount",
        "JRC (GHS-OBAT / GHS-POP)"),
    "Exposed buildings with no height (%)": (lambda q: 100 * q.get("exposed_height_missing", 0) / max(1, q.get("exposed_buildings", 0)), 5,
        "Height raster has no value at the footprint", "JRC (GHS-BUILT-H)"),
    "Exposed buildings outside built-up domain (use=0) (%)": (lambda q: 100 * q.get("exposed_use0_outside_builtup", 0) / max(1, q.get("exposed_buildings", 0)), 5,
        "Building not covered by the 10 m functional classification", "JRC (GHS-BUILT-C)"),
    "Unusually crowded exposed buildings (count)": (lambda q: q.get("exposed_buildings_people_density_outliers"), 0,
        "One small home holds a whole population cell (few residential buildings in the cell)", "Team (method choice)"),
    "OSM candidates without a name (%)": (lambda q: 100 * q.get("osm_unnamed", 0) / max(1, q.get("osm_in_scope", 0)), 40,
        "Volunteer mapping incomplete", "OpenStreetMap community / official lists"),
    "Shelter sites with no matching building (%)": (lambda q: 100 * q.get("sites_no_building", 0) / max(1, q.get("sites_after_dedup", 0)), 20,
        "Outdoor sports grounds, or OSM point far from any OBAT footprint", "Team / OSM"),
    "Shelter buildings with height at the 2.5 m floor (%)": (lambda q: 100 * q.get("shelter_buildings_height_at_2.5m_floor", 0) / max(1, q.get("shelter_buildings_matched", 0)), 30,
        "Height floored by design (GHS-OBAT doc p.19): storeys unknown, counted as 1", "JRC (GHS-BUILT-H)"),
    "Shelter capacity outliers capped (count)": (lambda q: len(q.get("capacity_outliers_capped", [])), 0,
        "Site matched to an unusually large building (possible wrong match)", "Team: check names in qc file"),
    "Shelters excluded only by the EFAS 100-year model (count)": (lambda q: q.get("shelter_sites_excluded_by_efas100_only"), 0,
        "Satellite map did not cover the spot, model says it floods: unmapped is not safe", "Info (expected)"),
}
rows = []
for area, q in QC["qc"].items():
    for name, (fn, thr, cause, owner) in IND.items():
        try: v = fn(q)
        except Exception: v = None
        status = "n/a" if v is None else ("WARN" if v > thr else "PASS")
        rows.append(dict(area=area, indicator=name, value=None if v is None else round(float(v), 1), warn_above=thr,
                         status=status, likely_cause=cause, who_can_fix=owner))
for area, val in QC.get("efas_validation", {}).items():
    for rp, d in val.items():
        rows.append(dict(area=area, indicator=f"EFAS {rp} recall vs observed flood (share of flooded buildings the model also floods)",
                         value=d["recall"], warn_above=None, status="INFO", likely_cause="Model vs satellite agreement", who_can_fix="JRC (EFAS)"))
df = pd.DataFrame(rows)
df.to_csv("outputs/data/dq_report.csv", index=False, encoding="utf-8-sig")
print(df.pivot_table(index="indicator", columns="area", values="value", aggfunc="first").round(1).to_string())
print("\nWARN count by area:", df[df.status == "WARN"].groupby("area").size().to_dict())
