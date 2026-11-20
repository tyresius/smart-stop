#!/usr/bin/env python3
"""
Step 4 — cheat-rate dose-response: at what q does the system break vs stutter?
==============================================================================
Sweep the fraction q of false-signalers (declare "R", drive "L") through the
streaming arterial cell and watch the failure shape:
  - STUTTER: safety floor dips, served-fraction stays ~100%, delay rises a
    little — the activation system absorbs the abuse.
  - BREAK:   served-fraction collapses / cars fail to clear (an in-box jam),
    or the floor cliffs toward contact.

The knee (if any) is the tolerable cheat rate — converts "there is a
vulnerability" into "tolerates X% false signals with graceful degradation."
Run on SmartStopReal (the trusting streaming controller — today's activation
system, up-front platoon claim).

Usage:  python cheat_rate_sweep.py [--smoke]
"""
import sys
import time

import numpy as np

from capacity_curves import run_stream, make_schedule

QS = [0.0, 0.01, 0.02, 0.05, 0.10, 0.20]
ARTERIAL = dict(lam=2000, split=[0.40, 0.40, 0.10, 0.10])


def main():
    smoke = "--smoke" in sys.argv
    qs = [0.0, 0.10] if smoke else QS
    sched = make_schedule(ARTERIAL['lam'], 0, split=ARTERIAL['split'])

    rows = []
    t0 = time.time()
    for q in qs:
        res = run_stream('SmartStopReal', sched, fair=True, false_q=q)
        vs = res['vehicles']
        served = [v for v in vs if v['served']]
        mean = float(np.mean([v['control_delay'] for v in served])) if served else None
        sf = len(served) / len(vs) if vs else None
        rows.append(dict(q=q, mean=mean, served=sf,
                         floor=(res['min_dist'] if res['min_dist'] != float('inf') else None),
                         unreached=res['n_unreached']))
        r = rows[-1]
        print(f"  q={q:>5.0%}: floor {r['floor']:.2f}m  served {sf*100:.1f}%  "
              f"delay {mean:.1f}s  unreached {r['unreached']}  "
              f"({time.time()-t0:.0f}s)", flush=True)

    import csv
    with open("cheat_rate_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("\n" + "=" * 66)
    print("CHEAT-RATE DOSE-RESPONSE — false 'right' that turns 'left', arterial 2,000")
    print("=" * 66)
    print(f"{'cheat q':>8} | {'safety floor':>12} | {'served':>8} | {'delay':>8} | {'unreached':>9}")
    print("-" * 66)
    for r in rows:
        print(f"{r['q']:>7.0%} | {r['floor']:>10.2f} m | {r['served']*100:>6.1f}% | "
              f"{r['mean']:>6.1f}s | {r['unreached']:>9}")
    print("-" * 66)
    # crude knee read: does served collapse or floor cliff?
    base_sf = rows[0]['served']
    breaks = [r for r in rows if r['served'] < base_sf - 0.05 or (r['floor'] and r['floor'] < 2.0)]
    if breaks:
        print(f"BREAK onset near q={breaks[0]['q']:.0%} "
              f"(served/floor collapse)")
    else:
        print("No break across the swept range — degradation is a STUTTER "
              "(served holds, floor dips but bounded).")
    print("=" * 66)


if __name__ == "__main__":
    main()
