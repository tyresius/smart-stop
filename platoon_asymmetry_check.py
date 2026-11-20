#!/usr/bin/env python3
"""Pre-audit check (2026-11-09): is the October stop-sign verdict partly an
artifact of a comparator asymmetry? The actuated signal discharges a whole
queue on green (PLATOON_MAX = 50, stopsign_vs_signal.py) while signal-blind
Smart Safe releases at most 4 cars per flash (PLATOON_MAX = 4,
block2_platoon.py) — so past 4 cars every new head pays a fresh flash,
reaction jitter and (under hesitation) H again. This runs BlindSafe with the
signal's discharge rule (PLATOON_MAX = 50) at the volumes where the verdict
turned, H = 0 and H = 1, 3 seeds. DIRECTIONAL ONLY. Note: PLATOON_MAX = 50
gives up the fixed-rotation side-street equity property (CLAIMS #4)."""
import csv, statistics as st, sys
from multiprocessing import Pool
import hesitation_sweep as hs
from capacity_curves import ALG_MAP

Blind50 = type("BlindSafe50", (hs.BlindSafe,), {"PLATOON_MAX": 50})
ALG_MAP["HS_Blind50"] = hs._watched(Blind50)
SPLITS = dict(hs.SPLITS)

def job(a):
    sl, lam, rep, key, h = a
    r = hs.job((sl, SPLITS[sl], lam, rep, key, h))
    # hs.job labels hesitation only for its own 'HS_Blind' key; label here
    # (the first run lost H and had to be repeated, 2026-11-09)
    r["alg"] = "Blind PLATOON_MAX=50"
    r["hesitation"] = h
    return r

if __name__ == "__main__":
    jobs = [(sl, lam, rep, key, h) for sl in ("arterial", "balanced") for lam in (800, 1000)
            for rep in range(3) for key, h in (("HS_Blind50", 0.0), ("HS_Blind50", 1.0))]
    out = []
    with Pool(8) as p:
        for r in p.imap_unordered(job, jobs):
            out.append(r); print(r["split"], r["lam"], r["rep"], r["alg"], r["hesitation"],
                                 r["mean_delay"], r["served_pct"], "OBB", r["obb_real"], flush=True)
    with open("platoon_asymmetry_check.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
