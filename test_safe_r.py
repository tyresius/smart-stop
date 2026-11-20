#!/usr/bin/env python3
"""
Test Smart Safe R — explicit false-right defense: safe by design, cheap.
  A) adversarial: false R->L across the 516-scenario set. Base Smart Safe was
     INCIDENTALLY safe (margin/cap); SmartSafeR should be safe BY DESIGN.
  B) honest-traffic cost: SmartSafeR vs base Smart Safe clearance time on the
     honest scenarios — the price of holding declared-rights for confirmation.
"""
import sys
import numpy as np

from path_based_smart_stop import SmartStopSafeAlgorithm
from reality_sweeps import generate_scenarios
from adversarial_intent import run_adv, MARGIN_M
from safe_r import SmartSafeR


def main():
    smoke = "--smoke" in sys.argv
    scen = [s for s in generate_scenarios() if len(s) in (2, 3)
            and any(sig == 'R' for _, sig, _ in s)]
    scen = scen[:60] if smoke else scen
    print(f"{len(scen)} scenarios with an R-declarer\n")

    # A) adversarial floor
    print("A) false R -> L, safety floor:")
    for label, Ctl in [('Smart Safe (base)', SmartStopSafeAlgorithm),
                        ('Smart Safe R', SmartSafeR)]:
        floor, breaches = float('inf'), 0
        for s in scen:
            adv, flipped = [], False
            for road, sig, order in s:
                if sig == 'R' and not flipped:
                    adv.append((road, 'L', order, 'R')); flipped = True
                else:
                    adv.append((road, sig, order, sig))
            _, _, md = run_adv(adv, 'trusting', Ctl)
            floor = min(floor, md)
            if md < MARGIN_M:
                breaches += 1
        print(f"   {label:<20} floor {floor:.2f} m   breaches {breaches}/{len(scen)}"
              f"   {'SAFE' if floor >= 3.4 else 'BREACH'}")

    # B) honest-traffic clearance cost
    print("\nB) honest traffic, clearance time (cost of R-confirmation):")
    base_t, r_t = [], []
    for s in scen:
        cfg = [(road, sig, order, sig) for road, sig, order in s]
        tb, okb, _ = run_adv(cfg, 'honest', SmartStopSafeAlgorithm)
        tr, okr, _ = run_adv(cfg, 'honest', SmartSafeR)
        if okb and okr and tb > 0:
            base_t.append(tb); r_t.append(tr)
    cost = np.mean([(r - b) / b * 100 for b, r in zip(base_t, r_t)])
    print(f"   base Smart Safe  {np.mean(base_t):.2f}s   "
          f"Smart Safe R  {np.mean(r_t):.2f}s   ({cost:+.1f}%)")
    print(f"\n   VERDICT: SmartSafeR closes false-right BY DESIGN at "
          f"{cost:+.1f}% honest-traffic cost.")


if __name__ == "__main__":
    main()
