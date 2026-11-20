#!/usr/bin/env python3
"""
Starvation Probe — does dominant-flow lockout appear under realistic
(platooned) arrivals, and does Smart Stop prevent it?
=====================================================================
Block 4's one_heavy result showed NO minor-approach starvation on the
roundabout — but under Poisson arrivals, which smooth the dominant flow
into exactly the spaced stream a yield entry can penetrate. Real dominant
flows on arterials arrive PLATOONED (released by upstream signals): a
dense wall of ~2 s headways passes the victim merge for tens of seconds
(every headway below the 4.5 s critical gap → zero entry opportunities),
followed by empty road. This is the documented lockout mechanism the
Smart Stop concept was designed against.

Design:
  - Dominant approach: Main E at 45% of demand, through-heavy turn mix
    (L/T/R = 10/80/10). Its through-stream (ring 205.5°→334.5°) passes
    directly over Green S's merge (295.5°) — the worst-placed victim.
  - Victim minor: Green S at 25% of demand (raised toward its gap
    capacity so denial can actually bind, unlike Block 4's 15% minors).
  - Other approaches: 15% each, Poisson, standard mix.
  - Arrival modes: 'poisson' (Block 4 conditions) vs 'bursty' (upstream
    signal: cycle 60 s, platoon at 2.0 s saturation headways). Same
    demand either way — only the arrival pattern changes.
  - Algorithms: RealisticRoundabout vs SmartStopReal (full Block 3
    realism), SmartStopPlatoon as ideal ceiling.

The starvation signature: victim mean/p95 delay exploding under bursty
arrivals for the roundabout while remaining bounded for Smart Stop
(whose fairness rotation guarantees service regardless of the ring
state). If instead both stay bounded, the single-lane self-throttling
argument survives even platooned traffic.

Usage:
    python starvation_probe.py            # full probe -> CSV + tables
    python starvation_probe.py --smoke    # 1 cell sanity check
"""

import csv
import random
import sys
import time

import numpy as np

from capacity_curves import (
    run_stream, ROADS, TURN_MIX, SEED, T_WARMUP, T_MEASURE,
)

DOMINANT = 'Main E'
VICTIM   = 'Green S'
#          Main E  Main W  Green N  Green S
SPLIT   = [0.45,   0.15,   0.15,    0.25]
DOM_MIX = [("L", 0.10), ("NS/S", 0.80), ("R", 0.10)]   # through-dominant

CYCLE_S      = 60.0   # upstream signal cycle feeding the dominant approach
SAT_HEADWAY  = 2.0    # s between vehicles inside a platoon

LAM_POINTS = [1600, 2000, 2400]
MODES      = ['poisson', 'bursty']
ALGS       = ['Roundabout', 'SmartStopPlatoon', 'SmartStopReal']
REPS       = 5   # multi-seed: single-seed (REPS=1) was a knife-edge tail draw
                 # for the CLAIMS §4 victim numbers — audit 2026-07-08.


def _pick_signal(rng, mix):
    u, acc = rng.random(), 0.0
    for s, p in mix:
        acc += p
        if u < acc:
            return s
    return mix[-1][0]


def make_probe_schedule(lam_total, rep, mode):
    """Split arrivals: dominant approach either Poisson or upstream-signal
    platoons; all other approaches Poisson with the standard mix."""
    rng = random.Random(f"{SEED}-probe-{lam_total}-{rep}-{mode}")
    horizon = T_WARMUP + T_MEASURE
    events = []
    for road, frac in zip(ROADS, SPLIT):
        lam = lam_total * frac / 3600.0
        mix = DOM_MIX if road == DOMINANT else TURN_MIX
        if road == DOMINANT and mode == 'bursty':
            n_per_cycle = lam * CYCLE_S
            t_cycle = rng.uniform(0.0, CYCLE_S)
            while t_cycle < horizon:
                n = int(n_per_cycle)
                if rng.random() < (n_per_cycle - n):
                    n += 1
                for k in range(n):
                    t = t_cycle + k * SAT_HEADWAY
                    if t < horizon:
                        events.append((t, road, _pick_signal(rng, mix)))
                t_cycle += CYCLE_S
        else:
            t = rng.expovariate(lam) if lam > 0 else horizon
            while t < horizon:
                events.append((t, road, _pick_signal(rng, mix)))
                t += rng.expovariate(lam)
    events.sort()
    return [(t, road, sig, i + 1) for i, (t, road, sig) in enumerate(events)]


def road_stats(vehicles, road):
    all_r  = [v for v in vehicles if v['road'] == road]
    served = [v for v in all_r if v['served']]
    d = [v['control_delay'] for v in served]
    return dict(
        mean=round(np.mean(d), 2) if d else None,
        p95=round(np.percentile(d, 95), 2) if d else None,
        served_frac=round(len(served) / len(all_r), 4) if all_r else None,
    )


def main():
    smoke = "--smoke" in sys.argv
    lam_points = [2000] if smoke else LAM_POINTS
    modes = ['bursty'] if smoke else MODES
    algs = ['Roundabout'] if smoke else ALGS

    rows = []
    t0 = time.time()
    for mode in modes:
        for lam in lam_points:
            for rep in range(REPS):
                schedule = make_probe_schedule(lam, rep, mode)
                for alg in algs:
                    res = run_stream(alg, schedule, fair=True)
                    vs = res['vehicles']
                    served = [v for v in vs if v['served']]
                    vic = road_stats(vs, VICTIM)
                    dom = road_stats(vs, DOMINANT)
                    rows.append(dict(
                        mode=mode, lam_vph=lam, rep=rep, algorithm=alg,
                        overall_mean=round(np.mean(
                            [v['control_delay'] for v in served]), 2)
                        if served else None,
                        served_frac=round(len(served) / len(vs), 4)
                        if vs else None,
                        victim_mean=vic['mean'], victim_p95=vic['p95'],
                        victim_served=vic['served_frac'],
                        dom_mean=dom['mean'], dom_p95=dom['p95'],
                        min_dist_m=(round(res['min_dist'], 2)
                                    if res['min_dist'] != float('inf') else ''),
                    ))
                    print(f"  {mode:>7} λ={lam:>5} rep {rep} {alg:<17}"
                          f"({time.time()-t0:.0f}s)", flush=True)

    out_csv = "starvation_probe_smoke.csv" if smoke else "starvation_probe.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Wrote {out_csv}")

    # ── Console summary ──────────────────────────────────────────────────
    def cell(mode, lam, alg, field):
        vals = [r[field] for r in rows
                if r['mode'] == mode and r['lam_vph'] == lam
                and r['algorithm'] == alg and r[field] is not None]
        return float(np.mean(vals)) if vals else None

    print("\n" + "=" * 88)
    print(f"STARVATION PROBE — dominant {DOMINANT} 45% (through 80%), "
          f"victim {VICTIM} 25% (merge in dominant through-stream)")
    print("=" * 88)
    for mode in modes:
        print(f"\nARRIVALS: {mode.upper()}"
              + ("  (upstream signal: 60 s cycle, 2.0 s platoon headways)"
                 if mode == 'bursty' else ""))
        hdr = (f"{'λ':>6} | {'alg':<17} | {'overall':>8} | "
               f"{'victim mean':>11} | {'victim p95':>10} | "
               f"{'victim served':>13} | {'dominant':>8}")
        print(hdr)
        print("-" * len(hdr))
        for lam in lam_points:
            for alg in algs:
                o = cell(mode, lam, alg, 'overall_mean')
                vm = cell(mode, lam, alg, 'victim_mean')
                vp = cell(mode, lam, alg, 'victim_p95')
                vs_ = cell(mode, lam, alg, 'victim_served')
                dm = cell(mode, lam, alg, 'dom_mean')
                fmt = lambda x, s='s': f"{x:.1f}{s}" if x is not None else "—"
                print(f"{lam:>6} | {alg:<17} | {fmt(o):>8} | {fmt(vm):>11} | "
                      f"{fmt(vp):>10} | "
                      f"{(f'{vs_*100:.0f}%' if vs_ is not None else '—'):>13} | "
                      f"{fmt(dm):>8}")


if __name__ == "__main__":
    main()
