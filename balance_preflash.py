#!/usr/bin/env python3
"""
Balance-routed pre-flash — Patrick's fairness/throughput balance principle
===========================================================================
(2026-07-18.) Pre-flash as shipped in Block 5 is throughput-greedy: ANY
stopped candidate gets the min-dwell hypothesis relaxation, so on lopsided
demand the busy road pockets every recovered head-dwell and the side
street's service turns bursty — forfeiting the CLAIMS §4 equity property
(37 -> 74 s victim delay), and feeding the very frustration mechanism that
produces flash-jumpers (patience model).

The fix routes the relaxation through the scheduler's EXISTING wait-aware
priority score (signal_bonus + wait_bonus): only the current priority
leader's candidates get the pre-flash hypothesis set. When waits are
balanced the leader is the deepest queue (throughput preserved); when an
approach's wait sags, its wait_bonus lifts it to leader and it inherits
the early flash. Self-correcting; no new mechanism, no new parameters.

Acceptance criteria (agreed with Patrick before running):
  (a) equity: victim/dominant delay ratio < 1 in EVERY seed on the hot
      split at 2,000 (5 seeds), victim mean ~ SmartStopReal's, not
      SmartStopPreflash's;
  (b) throughput regression: arterial@2,000, balanced@2,400,
      one_heavy@2,400 within noise of the CLAIMS pre-flash references
      (37.7 / 53.6 / 131.5 s);
  (c) [follow-on, Block 7b re-run] hot-split margin >= 3.3 m after
      BRAKE_RANGE calibration on whatever erosion remains.

Usage:  python balance_preflash.py [--smoke]
"""

import csv
import sys
import time

import numpy as np

from block3_reality import DwellRobustDetector, DWELL_HYPOTHESES
from block5_adaptive import PreflashAdaptiveSmartStop
from block7_response import ResponseSmartStop
from capacity_curves import run_stream, make_schedule, ROADS, ALG_MAP
from starvation_probe import make_probe_schedule, road_stats, VICTIM, DOMINANT


class BalanceRoutedDetector(DwellRobustDetector):
    """Grant the pre-flash (min-dwell) hypothesis set only to candidates on
    the current priority-leader approach; every other stopped candidate
    keeps the full conservative set (d=0 included) — i.e. no pre-flash."""

    def __init__(self, inner, min_candidate_dwell, leader_road_fn):
        super().__init__(inner, min_candidate_dwell)
        self._leader_road = leader_road_fn

    def _hyps(self, v):
        hyps = super()._hyps(v)
        if hyps is self.PREFLASH_HYPOTHESES \
                and v.road_name != self._leader_road():
            return DWELL_HYPOTHESES
        return hyps


class _BalanceMixin:
    """Swap in the balance-routed detector after normal construction."""

    def _install_balance_detector(self):
        det = self.collision_detector            # DwellRobustDetector
        self.collision_detector = BalanceRoutedDetector(
            det.inner, self.MIN_CANDIDATE_DWELL, self._priority_leader_road)

    def _priority_leader_road(self):
        """Approach of the highest-priority waiting HEAD, using the exact
        score the scheduler already ranks by (signal_bonus + wait_bonus).
        waiting_vehicles is in arrival order, so the first vehicle seen per
        road is that road's head."""
        best_road, best_score = None, float('-inf')
        seen = set()
        for v in self.waiting_vehicles:
            if v.road_name in seen:
                continue
            seen.add(v.road_name)
            s = self._signal_bonus(v.signal) + self._wait_bonus(v)
            if s > best_score:
                best_score, best_road = s, v.road_name
        return best_road


class BalancedPreflashSmartStop(_BalanceMixin, PreflashAdaptiveSmartStop):
    def __init__(self, geometry):
        super().__init__(geometry)
        self._install_balance_detector()


class BalancedResponseSmartStop(_BalanceMixin, ResponseSmartStop):
    """The mature stack (jumper response) with balance-routed pre-flash —
    the candidate for 'controller complete'."""

    def __init__(self, geometry):
        super().__init__(geometry)
        self._install_balance_detector()


ALG_MAP['SmartStopBalanced'] = BalancedPreflashSmartStop
ALG_MAP['SmartStopBalancedResponse'] = BalancedResponseSmartStop

CLAIMS_REFS = {           # CLAIMS §3 pre-flash references for regression
    'arterial':  37.7,    # @2,000  (SmartStopPreflashOnly)
    'balanced':  53.6,    # @2,400  (SmartStopPreflash)
    'one_heavy': 131.5,   # @2,400  (SmartStopPreflash)
}


def main():
    smoke = "--smoke" in sys.argv
    t0 = time.time()
    alg = 'SmartStopBalanced'

    # ── (a) Equity: hot split, poisson 2,000, 5 seeds ───────────────────────
    seeds = [0] if smoke else [0, 1, 2, 3, 4]
    eq_rows = []
    print("(a) EQUITY — hot split, poisson λ=2,000, SmartStopBalanced")
    for rep in seeds:
        schedule = make_probe_schedule(2000, rep, 'poisson')
        res = run_stream(alg, schedule, fair=True)
        vs = res['vehicles']
        vic = road_stats(vs, VICTIM)
        dom = road_stats(vs, DOMINANT)
        ratio = (vic['mean'] / dom['mean']
                 if vic['mean'] is not None and dom['mean'] else None)
        eq_rows.append(dict(rep=rep, victim_mean=vic['mean'],
                            victim_p95=vic['p95'], dom_mean=dom['mean'],
                            ratio=round(ratio, 2) if ratio else None,
                            min_dist_m=(round(res['min_dist'], 2)
                                        if res['min_dist'] != float('inf')
                                        else '')))
        r = eq_rows[-1]
        print(f"  seed {rep}: victim {r['victim_mean']}s  "
              f"dom {r['dom_mean']}s  ratio {r['ratio']}  "
              f"min_dist {r['min_dist_m']}m  ({time.time()-t0:.0f}s)",
              flush=True)

    # ── (b) Throughput regression: the three CLAIMS pre-flash cells ─────────
    cells = ([] if smoke else [
        ('arterial',  2000, dict(split=[0.4, 0.4, 0.1, 0.1])),
        ('balanced',  2400, dict(split=None)),
        ('one_heavy', 2400, dict(split=[0.55, 0.15, 0.15, 0.15])),
    ])
    reg_rows = []
    if cells:
        print("\n(b) THROUGHPUT REGRESSION — vs CLAIMS pre-flash references")
    for name, lam, kw in cells:
        schedule = make_schedule(lam, 0, **kw)
        res = run_stream(alg, schedule, fair=True)
        vs = res['vehicles']
        served = [v for v in vs if v['served']]
        delays = [v['control_delay'] for v in served]
        worst_p95 = max((float(np.percentile(
            [v['control_delay'] for v in served if v['road'] == road], 95))
            for road in ROADS
            if any(v['road'] == road for v in served)), default=0.0)
        reg_rows.append(dict(cell=name, lam_vph=lam,
                             mean=round(float(np.mean(delays)), 2),
                             worst_p95=round(worst_p95, 2),
                             served=round(len(served) / len(vs), 4),
                             ref=CLAIMS_REFS[name],
                             min_dist_m=(round(res['min_dist'], 2)
                                         if res['min_dist'] != float('inf')
                                         else '')))
        r = reg_rows[-1]
        print(f"  {name:>9} λ={lam}: {r['mean']}s (ref {r['ref']}s)  "
              f"worst-p95 {r['worst_p95']}s  served {r['served']}  "
              f"min_dist {r['min_dist_m']}m  ({time.time()-t0:.0f}s)",
              flush=True)

    out = "balance_preflash_smoke.csv" if smoke else "balance_preflash.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["section", "data"])
        for r in eq_rows:
            w.writerow(["equity", r])
        for r in reg_rows:
            w.writerow(["regression", r])
    print(f"Wrote {out}")

    # ── Verdicts ────────────────────────────────────────────────────────────
    print("\n" + "=" * 76)
    print("BALANCE-ROUTED PRE-FLASH — acceptance verdicts")
    print("=" * 76)
    ratios = [r['ratio'] for r in eq_rows if r['ratio'] is not None]
    vic_means = [r['victim_mean'] for r in eq_rows
                 if r['victim_mean'] is not None]
    ok_a = all(x < 1.0 for x in ratios)
    print(f"(a) equity ratio < 1 every seed: "
          f"{'PASS' if ok_a else 'FAIL'}  (ratios: "
          + ", ".join(f"{x:.2f}" for x in ratios)
          + f";  victim mean {np.mean(vic_means):.1f}s"
          + f" [SmartStopReal ref 38.9, Preflash ref ~74])")
    for r in reg_rows:
        drift = (r['mean'] - r['ref']) / r['ref'] * 100
        ok = abs(drift) <= 15.0     # single-seed noise band
        print(f"(b) {r['cell']:>9}: {r['mean']:6.1f}s vs ref {r['ref']:6.1f}s "
              f"({drift:+.0f}%)  {'PASS' if ok else 'CHECK'}")
    print("=" * 76)


if __name__ == "__main__":
    main()
