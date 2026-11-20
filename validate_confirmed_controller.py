#!/usr/bin/env python3
"""
Validate the integrated motion-confirmed-intent controller
===========================================================
(2026-07-21.) `adversarial_intent.py` proved the defense works when the TEST
HARNESS wraps the detector. This proves the defense works when it lives in the
CONTROLLER — `ConfirmedSmartStop` given a false-signaler normally, with NO
harness-side phantom net. If its safety floor matches the harness 'confirmed'
result, the integration is faithful.

Per scenario (all 2/3-car scenarios with an R-declarer):
  A. baseline trusting     — PathBasedSmartStopAlgorithm, false signal (the
                             vulnerability: floor 2.56 m expected)
  B. integrated controller — ConfirmedSmartStop, same false signal, self-
                             defends (expect ~3.48 m = harness 'confirmed')
  C. throughput cost       — ConfirmedSmartStop vs baseline on the HONEST
                             scenario (what the defense costs normal traffic)

Usage:  python validate_confirmed_controller.py [--smoke]
"""

import sys
import time

import numpy as np

from path_based_smart_stop import PathBasedSmartStopAlgorithm
from reality_sweeps import generate_scenarios
from adversarial_intent import run_adv, MARGIN_M
from motion_confirmed_intent import ConfirmedSmartStop


def main():
    smoke = "--smoke" in sys.argv
    scen = [s for s in generate_scenarios() if len(s) in (2, 3)]
    scen = [s for s in scen if any(sig == 'R' for _, sig, _ in s)]
    if smoke:
        scen = scen[:40]
    print(f"Validation: {len(scen)} scenarios with an R-declarer")

    rows = []
    t0 = time.time()
    for sid, s in enumerate(scen):
        honest_cfg = [(road, sig, order, sig) for road, sig, order in s]
        adv_cfg, flipped = [], False
        for road, sig, order in s:
            if sig == 'R' and not flipped:
                adv_cfg.append((road, 'L', order, 'R'))
                flipped = True
            else:
                adv_cfg.append((road, sig, order, sig))

        # A. baseline trusting (the vulnerability)
        _, _, base_md = run_adv(adv_cfg, 'trusting', PathBasedSmartStopAlgorithm)
        # B. integrated controller self-defends (mode 'trusting' = no harness net)
        _, _, ctrl_md = run_adv(adv_cfg, 'trusting', ConfirmedSmartStop)
        # C. throughput cost on HONEST traffic
        h_base_t, _, _ = run_adv(honest_cfg, 'honest', PathBasedSmartStopAlgorithm)
        h_ctrl_t, _, _ = run_adv(honest_cfg, 'honest', ConfirmedSmartStop)
        rows.append(dict(sid=sid, base_md=base_md, ctrl_md=ctrl_md,
                         honest_base_t=h_base_t, honest_ctrl_t=h_ctrl_t))
        if (sid + 1) % 50 == 0:
            print(f"  [{sid+1}/{len(scen)}] {time.time()-t0:.0f}s", flush=True)

    def floor(k):
        v = [r[k] for r in rows if r[k] != float('inf')]
        return min(v) if v else float('inf')

    def viol(k):
        return sum(1 for r in rows if r[k] < MARGIN_M)

    n = len(rows)
    print("\n" + "=" * 78)
    print("INTEGRATED MOTION-CONFIRMED CONTROLLER — validation")
    print("=" * 78)
    print(f"scenarios: {n}   (design margin {MARGIN_M} m)")
    print(f"{'A. baseline trusting':<34} floor {floor('base_md'):.2f} m   "
          f"< margin {viol('base_md')}/{n} ({viol('base_md')/n*100:.0f}%)")
    print(f"{'B. integrated ConfirmedSmartStop':<34} floor {floor('ctrl_md'):.2f} m   "
          f"< margin {viol('ctrl_md')}/{n} ({viol('ctrl_md')/n*100:.0f}%)")
    rescued = sum(1 for r in rows if r['base_md'] < MARGIN_M <= r['ctrl_md'])
    residual = sum(1 for r in rows if r['ctrl_md'] < MARGIN_M)
    print(f"{'  rescued (base<margin -> ctrl safe)':<34} {rescued}/{n}")
    print(f"{'  residual < margin with controller':<34} {residual}/{n}")
    # honest throughput cost
    safe = [r for r in rows if r['honest_base_t'] > 0]
    cost = np.mean([(r['honest_ctrl_t'] - r['honest_base_t']) / r['honest_base_t'] * 100
                    for r in safe]) if safe else float('nan')
    print(f"{'C. honest-traffic clearance cost':<34} {cost:+.1f}% mean "
          f"(controller vs baseline)")
    print("=" * 78)
    verdict = ("INTEGRATION FAITHFUL — controller closes the exposure by construction"
               if floor('ctrl_md') >= 3.4 and rescued > 0 else
               "CHECK — controller floor below expected; investigate")
    print(verdict)


if __name__ == "__main__":
    main()
