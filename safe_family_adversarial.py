#!/usr/bin/env python3
"""
Step 1 — does the Smart Safe family absorb the false-signal attack?
===================================================================
Smart Safe already treats a declared STRAIGHT as a worst-case LEFT (the
NS/S->L rule override). It does NOT override a declared RIGHT — so a false
"right" that turns left should still exploit it. "Super Safe" extends the
worst-case to EVERY declared signal (all -> L): it never trusts any
declaration, so no false signal can be trusted. This measures both against
the same false R/L adversary the vulnerability was found with.

Usage:  python safe_family_adversarial.py [--smoke]
"""
import sys

from path_based_smart_stop import (
    PathBasedSmartStopAlgorithm, SmartStopSafeAlgorithm)
from reality_sweeps import generate_scenarios
from adversarial_intent import run_adv, MARGIN_M


class SuperSafe(SmartStopSafeAlgorithm):
    """All declared intents treated as worst-case left — trusts no signal."""
    def add_vehicle(self, vehicle):
        vehicle.signal = "L"          # controller view only; true path unchanged
        super().add_vehicle(vehicle)


def main():
    smoke = "--smoke" in sys.argv
    scen = [s for s in generate_scenarios() if len(s) in (2, 3)
            and any(sig == 'R' for _, sig, _ in s)]
    scen = scen[:60] if smoke else scen
    print(f"Step 1 — {len(scen)} adversarial scenarios (false R -> L)")

    controllers = [
        ('trusting Smart Stop', PathBasedSmartStopAlgorithm),
        ('Smart Safe',          SmartStopSafeAlgorithm),
        ('Super Safe (all->L)', SuperSafe),
    ]
    print(f"{'controller':<24} | {'floor':>8} | {'< margin':>12} | verdict")
    print("-" * 62)
    for label, Ctl in controllers:
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
        v = 'SAFE' if floor >= 3.4 else 'BREACH'
        print(f"{label:<24} | {floor:>6.2f} m | {breaches:>4}/{len(scen)} "
              f"({breaches/len(scen)*100:>3.0f}%) | {v}")


if __name__ == "__main__":
    main()
