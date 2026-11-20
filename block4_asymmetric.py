#!/usr/bin/env python3
"""
Block 4 — The Decisive Experiment: Asymmetric Demand
=====================================================
Blocks 1-3 established, under symmetric (balanced) demand with human
realism on both sides: Smart Stop wins light traffic (rolling green),
the roundabout wins balanced heavy traffic. But balanced demand is the
roundabout's best case: every entry sees the same circulating stream.
The known failure mode of yield-based merging is DOMINANT-FLOW
STARVATION — a heavy circulating stream from a major road denies gaps
to minor-road entries, whose delay explodes even while the major road
flows freely. A scheduler meters explicitly and cannot starve anyone
(Smart Stop additionally carries the M3 wait-time fairness bonus).

This is therefore the regime that decides whether Smart Stop has a
real-world performance case beyond light traffic:

  Demand patterns (per-approach fractions of total λ):
    balanced   25/25/25/25  — reference (roundabout's best case)
    arterial   40/40/10/10  — two-way major street + minor cross street
    one_heavy  55/15/15/15  — single dominant approach

  Metrics per (λ, pattern, algorithm):
    - overall mean control delay + served fraction
    - MINOR-approach mean and p95 delay (the starvation signature)
    - dominant-approach mean delay (what the major street pays for
      fairness under scheduling)

Algorithms: RealisticRoundabout vs SmartStopReal (both fully
human-realistic, Block 3), with the idealized SmartStopPlatoon as
ceiling reference. Traditional is omitted: it is fully collapsed at
every demand level tested here (Block 3: ~400 veh/h capacity).

Usage:
    python block4_asymmetric.py            # full run -> CSV + PNG + tables
    python block4_asymmetric.py --quick    # 1 λ x 2 patterns smoke test
"""

import csv
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from capacity_curves import make_schedule, run_stream, ROADS

SPLITS = {
    'balanced':  [0.25, 0.25, 0.25, 0.25],
    'arterial':  [0.40, 0.40, 0.10, 0.10],   # Main E/W dominant
    'one_heavy': [0.55, 0.15, 0.15, 0.15],   # Main E dominant
}
LAM_POINTS = [1200, 1600, 2000, 2400]
REPS = 2
ALGS = ['Roundabout', 'SmartStopPlatoon', 'SmartStopReal']


def minor_roads(split):
    mx = max(split)
    return {r for r, f in zip(ROADS, split) if f < mx}


def aggregate(vehicles, minors):
    served = [v for v in vehicles if v['served']]
    out = dict(
        demand=len(vehicles),
        served=len(served),
        served_frac=round(len(served) / len(vehicles), 4) if vehicles else 1.0,
        mean_delay=round(np.mean([v['control_delay'] for v in served]), 2)
        if served else None,
    )
    if minors:
        m = [v['control_delay'] for v in served if v['road'] in minors]
        d = [v['control_delay'] for v in served if v['road'] not in minors]
        m_all = sum(1 for v in vehicles if v['road'] in minors)
        out.update(
            minor_mean=round(np.mean(m), 2) if m else None,
            minor_p95=round(np.percentile(m, 95), 2) if m else None,
            minor_served_frac=round(len(m) / m_all, 4) if m_all else 1.0,
            dom_mean=round(np.mean(d), 2) if d else None,
        )
    else:
        out.update(minor_mean=None, minor_p95=None,
                   minor_served_frac=None, dom_mean=None)
    return out


def main():
    quick = "--quick" in sys.argv
    lam_points = [2000] if quick else LAM_POINTS
    splits = (['arterial', 'one_heavy'] if quick else list(SPLITS))
    reps = 1 if quick else REPS

    rows = []
    t0 = time.time()
    for pattern in splits:
        split = SPLITS[pattern]
        minors = minor_roads(split)
        for lam in lam_points:
            for rep in range(reps):
                schedule = make_schedule(lam, rep, split=split)
                for alg in ALGS:
                    res = run_stream(alg, schedule, fair=True)
                    agg = aggregate(res['vehicles'], minors)
                    rows.append(dict(pattern=pattern, lam_vph=lam, rep=rep,
                                     algorithm=alg,
                                     min_dist_m=(round(res['min_dist'], 2)
                                                 if res['min_dist'] != float('inf')
                                                 else ''),
                                     **agg))
                print(f"  {pattern:>9} λ={lam:>5} rep {rep}: done "
                      f"({time.time()-t0:.0f}s)", flush=True)

    out_csv = "block4_asymmetric_quick.csv" if quick else "block4_asymmetric.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out_csv}")

    # ── Console summary ──────────────────────────────────────────────────
    def cell(pattern, lam, alg, field):
        vals = [r[field] for r in rows
                if r['pattern'] == pattern and r['lam_vph'] == lam
                and r['algorithm'] == alg and r[field] is not None]
        return float(np.mean(vals)) if vals else None

    for pattern in splits:
        minors = minor_roads(SPLITS[pattern])
        print("\n" + "=" * 76)
        print(f"PATTERN: {pattern}  (splits {SPLITS[pattern]}, "
              f"minor approaches: {sorted(minors) if minors else '—'})")
        print("=" * 76)
        hdr = f"{'λ':>6} |"
        for alg in ALGS:
            hdr += f" {alg:>32} |"
        print(hdr)
        sub = f"{'':>6} |" + (" {:>15} {:>16} |".format('overall', 'minor(p95)')
                              * len(ALGS))
        print(sub)
        print("-" * len(hdr))
        for lam in lam_points:
            line = f"{lam:>6} |"
            for alg in ALGS:
                d = cell(pattern, lam, alg, 'mean_delay')
                m = cell(pattern, lam, alg, 'minor_mean')
                p = cell(pattern, lam, alg, 'minor_p95')
                sf = cell(pattern, lam, alg, 'served_frac')
                ds = f"{d:.1f}s" if d is not None else "—"
                if sf is not None and sf < 0.98:
                    ds += f"({sf*100:.0f}%)"
                ms = (f"{m:.1f}s(p95 {p:.0f})" if m is not None else "—")
                line += f" {ds:>15} {ms:>16} |"
            print(line)

    # ── Chart ────────────────────────────────────────────────────────────
    if not quick:
        colors = {'Roundabout': '#3498DB', 'SmartStopPlatoon': '#9B59B6',
                  'SmartStopReal': '#F39C12'}
        fig, axes = plt.subplots(2, len(splits), figsize=(5 * len(splits), 9),
                                 sharex=True)
        for ci, pattern in enumerate(splits):
            ax_o, ax_m = axes[0][ci], axes[1][ci]
            for alg in ALGS:
                ax_o.plot(lam_points,
                          [cell(pattern, l, alg, 'mean_delay') for l in lam_points],
                          'o-', color=colors[alg], label=alg)
                mv = [cell(pattern, l, alg, 'minor_mean') for l in lam_points]
                if any(v is not None for v in mv):
                    ax_m.plot(lam_points, mv, 'o-', color=colors[alg], label=alg)
            ax_o.set_title(f"{pattern} — overall delay")
            ax_m.set_title(f"{pattern} — minor-approach delay")
            for ax in (ax_o, ax_m):
                ax.grid(alpha=0.3)
                ax.set_ylabel("mean control delay (s/veh)")
            ax_m.set_xlabel("Demand λ (veh/h)")
        axes[0][0].legend()
        fig.tight_layout()
        fig.savefig("block4_asymmetric.png", dpi=110)
        print("\nWrote block4_asymmetric.png")


if __name__ == "__main__":
    main()
