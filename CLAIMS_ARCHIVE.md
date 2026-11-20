# Smart Stop — Claims Ledger ARCHIVE (superseded)

**SUPERSEDED. Do not quote anything in this file.** Current claims: `CLAIMS.md` (2026-11-15); evidence: `FINAL_AUDIT.md`. This is the historical ledger (July–November 2026), kept for the audit trail. Many figures below were later withdrawn or corrected; see `FINAL_AUDIT.md` §7.

---

## Original header (July 2026)

The numbers any deck, paper, or pitch may quote, with their conditions and
sources. Anything not on this list is superseded — check REALITY_REPORT.md
before resurrecting an old figure. Last updated July 20, 2026 (bug #8
predictor fix — no claim changed).

**Status 2026-11-09 (historical):** verdict then was "commercially doubtful,
not established, not proven failed"; superseded by the section above.
Claims 1–4 below predate the footprint (OBB) standard and the signal-blind
controller.

## Core claims (historical; superseded by CURRENT CLAIMS above)

1. **vs Traditional 4-way stop: ~4× capacity.** Traditional saturates at
   ~600–800 veh/h (validating against the AWSC literature band); mature
   Smart Stop serves 2,400+ veh/h. Under full realism (reaction jitter,
   25% unsignaled drivers per SAE field data): **+49% clearance advantage
   at real-world signal-usage rates.**
2. **vs the honest human baseline: ~40× at light-to-moderate volumes.**
   Real drivers informally pair opposing straights and perpendicular
   rights (~3× better than strict-serial); mature Smart Stop still posts
   0.5 s vs 21.7 s mean delay at 600 veh/h, 3.7 s vs 240.5 s at 1,200.
3. **Regime map vs a fairly-modeled mini-roundabout** (behavioral gap
   acceptance, follow-up headway, rolling entry, curvature-fair physics):
   **⚠ UNDER REVISION (2026-10-01):** this map compares an OBB-overlapping full
   Smart Stop against a roundabout whose own footprints overlap (146–704 real
   overlaps per cell, claim 5). Not quotable until re-based on OBB.
   - Light traffic (≤ ~1,000 veh/h): **Smart Stop wins** (rolling green).
   - Arterial 40/40/10/10 (the most common real asymmetry): **Smart Stop
     wins the entire range, and with pre-flash nearly HALVES roundabout
     delay at volume**: 5.4 vs 9.1 s (1,600), 37.7 vs 73.3 (2,000),
     107.2 vs 156.4 (2,400).
   - Single-dominant 55/15/15/15: **parity at 2,000 (97.3 vs 93.5 s),
     Smart Stop wins at 2,400** (131.5 vs 141.1 s) with pre-flash (Block 5).
   - Balanced heavy: roundabout leads, 37.5 vs 53.6 s at 2,400 — gap
     narrowed from 2.3× to 1.4× by pre-flash; this remains the roundabout's
     regime. Fair context (qualitative, not a number): sustained perfectly
     balanced heavy demand is also the least common pattern at real
     intersections — most skew asymmetric (the arterial case, which Smart
     Stop wins outright). Concede the regime; note its rarity.
4. **Side-street equity — the busy road waits, not the side street**
   (reframed July 8, 2026 after a 5-seed re-pin; supersedes the single-seed
   "starvation" claim). Hot split (dominant 45%, 80%-through aimed at a
   well-placed minor at 25%). Two things the multi-seed data establishes:
   - **Neither system *starves* the minor** — both serve 100% at
     1,600–2,400 veh/h. The fair single-lane roundabout self-throttles
     enough to always serve the side street; "eliminates lockout" is retired.
   - **What differs is who absorbs the delay, and Smart Stop's advantage is
     removing tail risk, not lowering the mean.** On the roundabout, whether
     the minor is bullied is a lottery of arrival phasing: across 5 seeds at
     2,000 veh/h the minor waited *longer than the dominant stream it yields
     to* in **3 of 5 seeds** (equity ratio up to **5.05**; worst seed 72 s
     victim vs 14 s dominant). Smart Stop's fixed rotation removes that tail:
     in **every seed** the dominant queue absorbs more delay than the minor
     (ratio **0.16–0.47**). This is a moderate-load effect (1,600–2,000; at
     2,400 the dominant self-saturates and pays on both systems).
   Honest bounds (do not overstate): Smart Stop does **not** reliably lower
   the minor's *absolute* mean delay — at 2,000 it is within seed noise
   (38.9 ±19 vs roundabout 50.8 ±28) and at 1,600 / 2,400 the roundabout is
   better for the minor; Smart Stop's within-run p95 tail is heavier. The
   defensible claim is **equity / anti-bullying**, not victim speed. Applies
   to `SmartStopReal` (fixed PLATOON_MAX=4); the pre-flash stack forfeits it
   (see do-not-claim).
5. **Safety by construction.** The heterogeneous-reaction-jitter failure
   (2.29 m) is closed by dwell-robust gating; pre-flash is implemented as
   hypothesis-tightening (a stopped driver cannot launch in <0.5 s), so it
   inherits the same proof obligation; cross-path minima ≥3.38 m across
   all Block 3–5 experiments (3.5 m margin minus discretization). Exception,
   now fully swept (Block 7b, July 15, 27 runs): `SmartStopResponse` on the
   starvation hot split runs BELOW the 3.3 m Block-7 margin in every cell —
   typically 3.27 m independent of jumper rate (the known evasive-stack
   erosion), worst case **2.84 m at q=10% × 2,000 veh/h**. No collisions in
   any cell, 100% served, delay stable — the v1 mitigation still eliminates
   collisions on the hot split; what it misses there is the *margin
   standard*. Do NOT claim any ≥3.3 m floor for `SmartStopResponse` on
   asymmetric-demand patterns; BRAKE_RANGE recalibration (README backlog)
   is the closing item.
   *Bug #8 (July 20, caught by the cross-path observable): the predictor
   projected car-following-throttled followers at free-path speed, so it
   could clear cross traffic against a follower still in the crossing
   (a 2.26 m realized approach on an experimental controller). Fixed by
   capping a follower's predicted position at its leader's
   (`FollowingVehicle._predicted_arc_meters`). Re-certification: every
   published number above is unchanged; the fair-348 floor holds at 3.46 m
   and one starvation cell's min-distance improved 3.31 → 3.52 m. The fix is
   conservative-only (it can never predict a follower further forward than
   before), so it cannot have loosened any margin.*
   **⚠ OBB FINDING (2026-09-29, external audit + `obb_diag.py`) — THIS CLAIM
   IS UNDER REVISION.** The whole safety metric above is center-to-center
   distance vs a 3.5 m margin, but vehicles are 4.5 m × 2.0 m. For a
   perpendicular crossing two footprints can OVERLAP at center-distances up to
   3.25·√2 = 4.596 m — so "≥3.38 m = safe" is NOT a physical-clearance
   statement. Re-measuring the *realized* oriented-bounding-box (OBB)
   separation from actual per-step (x,y,heading): full Smart Stop's co-activated
   footprints physically overlap in **63%** of multi-vehicle scenarios,
   Smart Safe in **5%**, the roundabout in **0%** (min OBB clearance 3.27 m —
   genuinely safe). **Do NOT claim "safety by construction" or any center-
   distance margin as a physical-safety guarantee until the collision check is
   re-based on OBB.** Caveat: the sim is single-lane centerline point-vehicles,
   which inflates the rate (real lane width would separate some pairs); the
   definitive number needs the OBB check inside the *decision* logic plus lane
   geometry. But the direction is not in doubt, and Smart Stop ≫ Smart Safe ≫
   safe. Consequence for the product story: Smart Safe (already the deception-
   resistant deployable mode) is 12× safer than full Smart Stop under OBB — more
   evidence it, not full Smart Stop, is the product; and full Smart Stop's
   throughput edge likely shrinks once the detector disallows the overlapping
   co-activations (OBB detector re-base in progress). Deflection geometry (the
   false-signal pivot candidate) also physically separates crossing paths and is
   the structural fix for this overlap mode.
   **RE-BASE, first cut (`obb_classify.py`, `obb_rebase.py`, 386 scenarios):**
   decomposing overlaps by path-intersection, full Smart Stop's are **46% REAL
   crossing conflicts** (aimed through the same point — not lane artifacts),
   Smart Safe's **1%**. Fix: raise the margin to the physically-grounded
   **4.596 m** (= 3.25·√2, guarantees no 4.5×2.0 overlap in any orientation) →
   **real overlaps drop to 0% for BOTH**, at **+28% (Stop) / +18% (Safe)
   discrete-clearance cost** (conservative upper bound; a true OBB decision
   check blocks less). The flaw is real but **fixable and bounded**. OPEN: the
   streaming/regime cost — does OBB-margin Smart Safe still clear the roundabout
   bar? (survival gate at 4.6 m, not yet run). Full Smart Stop even OBB-corrected
   stays deception-vulnerable, so Smart Safe remains the product.
   **OBB SURVIVAL GATE RUN (2026-10-01, `obb_survival_gate.py`, 5 seeds × 4
   cells, both controllers held to ONE footprint standard, realized overlaps
   SAT-checked every step).** Three things the discrete re-base missed:
   (a) **a radial 4.596 m margin is invalid as a DECISION rule** — opposing
   lanes are 4.5 m apart, and streaming Smart Safe relabels declared straights
   as L (so Rule 1's parallel-pass exemption never fires): it forbids opposing
   through movement (smoke, arterial: 158 s / 81.7% served vs 52.7 s). Replaced
   by an OBB decision check (predicted footprints inflated by a clearance
   buffer B). Note: streaming Smart Safe ran at 3.5 m, not discrete Safe's 4.0.
   (b) **the 3.5 m Smart Safe also rear-ended**: mixed-signal same-lane pairs
   launched 3.54 m apart (< one car length) — 5–13 real + many "lane-artifact"
   overlaps per cell. (c) **the roundabout bar was physically invalid**: yield
   point at r = 9.3 m vs ring centerline 6.75 m (waiting cars sit in the ring
   lane) and the same < car-length 3.5 m radial entry check (ring rear-ends):
   **146–704 real overlaps per cell**. Corrected roundabout = yield line set
   back 1.5 m + same OBB entry check (residual: ≤1 overlap in ~4 of 20 runs).
   Result (mean delay s, served %; B = 0.5 m / 1.0 m):
   - light 1,000: Safe 3.1 / 3.7 vs RB 2.1 / 2.4 — Safe ~1 s slower (trivial).
   - arterial 2,000: **66.8 vs 63.6 / 82.4 vs 82.6 — PARITY** (was "Safe WINS").
   - balanced 2,400: 120.5 vs 78.2 / 145.5 vs 98.9 — Safe loses (~1.5×).
   - dominant 2,400: **Safe serves only 84% / 81% vs RB 99%** — Safe LOSES on
     capacity (its lower mean delay is over fewer served cars).
   Smart Safe: **0 real overlaps in all 40 runs** (min footprint gap 0.06 m at
   B = 0.5 — the buffer is nearly consumed by launch-timing spread; 0.58–1.8 m
   at B = 1.0). The OBB fix costs Smart Safe +13% to +115% delay — 3–6× the
   discrete +18% estimate. The roundabout's honest correction costs it too
   (balanced 37 → 78–99 s), so the gap moved less than either cost alone.
   **Verdict: survival gate now passes only at parity on the arterial, and
   the result depends on B** (not yet grounded in sensor/timing precision).
   Do NOT claim Smart Safe beats the roundabout anywhere. Defensible claim:
   "matches a physically-corrected single-lane roundabout on arterial traffic
   at a fraction of the construction cost; the roundabout wins balanced-heavy
   and single-dominant." OPEN: (1) ground B; (2) the real retrofit comparator
   is the all-way stop (Traditional) — re-run it under the same OBB standard;
   (3) the regime map in claim 3 is against the same invalid roundabout and an
   overlapping full Smart Stop — re-base it.
   **⚠ CORRECTED same day (hesitation_sweep.py) — the vs-signal numbers in
   the next block were measured on a controller that is NOT signal-blind:
   streaming Smart Safe trusted declared L/R and its geometric check walked
   each car's TRUE path (oracle a camera lacks before motion). Do NOT quote
   "3–10× vs signal". Honest numbers are in the HESITATION block below.**
   ~~STOP-SIGN REPLACEMENT GATE~~ (2026-10-03, `stopsign_vs_signal.py`, 5 seeds,
   balanced + arterial, 400–1,600 veh/h, all under the same OBB standard;
   0 real overlaps in all 300 runs).** Comparators = the two options a city
   with a failing all-way stop actually has: keep it (HumanFourWay, honest
   folk-pairing baseline) or buy a signal (`SignalActuated`: two-phase
   actuated, permitted lefts via the same OBB check, same vehicles/jitter/
   car-following as Smart Safe). Mean control delay (s), B = 0.5 / 1.0 m:
   - balanced 600: AWSC 17.1 · Safe 0.9 / 1.1 · Signal 8.3 / 8.7
   - balanced 1,000: AWSC 110.1 · Safe 3.1 / 3.7 · Signal 12.7 / 13.2
   - balanced 1,600: AWSC 315.7 (96% served) · Safe 23.6 / 30.9 · Signal 71.3 / 90.1
   - arterial 1,200: AWSC 206.7 · Safe 7.6 / 8.6 · Signal 27.3 / 29.8
   Smart Safe beats the actuated signal at every volume and split (~3–10×
   lower delay) and the all-way stop by ~10–40× above 600 veh/h; robust to B.
   Claim as: "under one physical-clearance standard, Smart Safe delivers lower
   delay than the traffic signal a city would otherwise install, with no
   civil works." CONDITIONS (must travel with the claim): idealized-driver
   model for BOTH Smart Safe and the signal (no novel-device hesitation /
   MUTCD expectancy cost on the flash); honest turn signals (unsignaled-driver
   share not applied here); **no pedestrians** (a signal serves them
   explicitly — Smart Safe pedestrian handling is an open design question);
   the signal omits ped minimums (favours signal) and protected lefts
   (disfavours it at high left volume). Our AWSC likely saturates earlier than
   HCM capacity — quote the vs-signal result, treat vs-AWSC as order-of-
   magnitude.
   **SIGNAL-BLIND + HESITATION (2026-10-03, `hesitation_sweep.py`, OBB B=1.0,
   0 real overlaps in every run).** `BlindSafe` = motion-confirmed intent on
   the streaming controller: every unrevealed car checked against all three
   paths until REVEAL_M; turn signals never read. Hesitation H = extra launch
   delay for flash-responding drivers + no rolling launches; controller
   calibrated to the slower population; signal gets none. Mean delay (s),
   5 seeds unless noted (balanced / arterial):
   - Signal: 400: 6.1/4.6 · 600: 8.7/6.6 · 800: 10.9/10.1 · 1,000: 13.2/12.4
     · 1,200: 31.8/29.8
   - Blind, H=0: 400: 1.2/1.1 · 600: 2.4/2.4 · 800: 5.9/9.6 ·
     1,000: 15.8/16.7 (5/4 seeds) · 1,200: 65.8/75.3 (3 seeds)
     [corrected 2026-11-09 from the committed hesitation_sweep.csv; the
     earlier "13.5/19.1 (2–3 seeds)" and "1,200 arterial 75 (1 seed)" were
     recorded mid-run. Fuller data: Safe loses at 1,000 on BOTH splits.]
   - Blind, full stop H=0 (no rolling only): 400: 3.3/3.0 · 600: 4.4/5.1 ·
     800: 8.6/11.7  [corrected 2026-11-09 from the CSV; was 3.2/2.6 ·
     4.5/5.7 · 8.4/11.2]
   - Blind, H=0.5: 4.4/4.2 · 6.4/7.4 · 14.7/22.5 (400/600/800)
   - Blind, H=1: 5.6/5.3 · 9.2/10.3 · 27.7/37.9;  H=2: 8.7/8.3 · 18.4/25.4 ·
     71.9/71.0
   ~~**Verdict (Oct):** signal-blind Smart Safe beats an actuated signal only
   below ~800–1,000 veh/h AND only if drivers neither hesitate nor stop.~~
   **Withdrawn 2026-11-09 after two external audits: overstated.** Full stops
   keep the win, and the 1,000 veh/h losses are not statistically resolved.
   **Verdict (restated 2026-11-09, `FINAL_AUDIT.md` §2):** commercially
   doubtful, not established as a product, not proven failed. Paired 95%
   intervals on matched seeds (`paired_ci_check.txt`, 5 seeds/cell):
   - **Safe wins:** 400–600 veh/h both splits at H=0 AND with full stops;
     800 balanced at H=0 and full stop; 400 balanced at H=0.5.
   - **Safe loses:** H=1 at 600 arterial and 800 balanced; H=2 nearly
     everywhere; 1,200 arterial at H=0.
   - **Not resolved:** all of 1,000 veh/h; 800 arterial at H≤1; most H=0.5
     cells.
   The established wins sit where all-way stops are not failing (AWSC 17.1 s
   at 600 balanced, HCM LOS C). Main commercial barriers: the MUTCD gives a
   flashing green no meaning, so deployment needs FHWA experimentation; there
   is no data on driver response to the indication (1 s of hesitation erases
   the win almost everywhere); there is no pedestrian design. "No buyer pays
   where it wins" is an unanalysed economic claim. Do not quote it.
   Uncapping the platoon (4 → 50) changes nothing at 800–1,000
   (`platoon_asymmetry_check.txt`, 15/18 matched seeds identical).
   Claimable: "at 400–600 veh/h, a camera-only, signal-blind controller beat
   an actuated signal in simulation, with full stops and no footprint
   overlaps observed, if drivers don't hesitate at the novel indication."
   Not claimable: any result at 1,000+ veh/h either way, "collision-free," or
   any vs-signal result without the hesitation caveat.
6. **Fail-safe:** a dead Smart Stop is exactly today's stop sign.
7. **Discrete-scenario win rates under fair physics** (July 17; derived
   from the committed `reality_fair_results.csv` — 348 stratified 2–4-vehicle
   scenarios, curvature-fair physics, clearance-time metric, paired):
   **Smart Stop fastest in 267/348 (77%), roundabout in 81/348 (23%),
   Traditional in 0.** This is the honest replacement for the retired
   "83% of 2,712 scenarios" figure — same question, fair physics.
8. **Smart Safe (the conservative bridge mode)** — fair physics, same 348
   paired scenarios (`smart_safe_fair.py`, July 17): **+42.4% vs
   Traditional (wins 336/348 = 97%)**; −6.5% vs the roundabout (wins 31%);
   −31.7% vs full Smart Stop (never meaningfully beats it: 6 wins, 128
   ties). Safety floor **3.99 m** — the largest of any controller tested.
   Claim as: a deployment on-ramp running at **82% of full Smart Stop's
   speed** (mean of per-scenario ratios, 348 paired) with extra-conservative
   margins; full Smart Stop is the destination. Reference: full Smart Stop
   saves +53.4% vs Traditional on these discrete scenarios, Smart Safe
   +42.4%. Do not present Smart Safe as competitive with the roundabout or
   full Smart Stop.
9. **Violation camera (product design element — NOT simulated).** The sign
   controller photographs flash-jumpers, like a red-light camera. Two
   claimable statements only: (a) red-light-camera literature documents
   large violation-rate reductions (order ~40%, IIHS) — cite as precedent,
   not our result; (b) our compliance sweep validated safety at q = 10%
   jumpers *without* any deterrence, so enforcement pushes real-world
   non-compliance below the tested bound — the tested case is conservative.
   Do NOT quote a crash-reduction number (RLC crash literature is mixed).

## Do NOT claim (with why)

- ~~"58% faster, beats everything"~~ — pre-audit scenario framing; retired.
- ~~"+20% vs roundabout"~~ — died with the ring-speed fairness audit.
- Any throughput claim at balanced-heavy demand vs a roundabout.
- Fairness (p95) superiority at saturation: worst-approach p95 under Smart
  Stop (300–500 s) exceeds the roundabout's (158–307 s) in collapse
  regimes — wait-bonus retuning is an open backlog item.
- ~~"Smart Stop eliminates side-street starvation / dominant-flow lockout"~~
  — no lockout occurs on the fair model (both systems serve 100%); the real
  property is equity, see §4.
- ~~"5× fairness inversion" / "holds the victim to 37 s" as the typical
  case~~ — single-seed (rep 0) tail draw; 5× is the *worst* of 5 seeds, and
  the 37 s "protection" is within seed noise. Quote 5× only as worst-case.
- Side-street equity under the pre-flash / mature (`SmartStopResponse`)
  stack. Audit 2026-07-08: pre-flash is throughput-greedy and forfeits the
  §4 equity property — on the hot split it doubles the minor's delay
  (37→74 s) vs `SmartStopReal`, ending *worse than the roundabout*. Claim
  §4 equity ONLY for `SmartStopReal` (fixed PLATOON_MAX=4, which forces the
  rotation that keeps the dominant paying). Fix is backlog #2.
- Anything about pedestrians, cyclists, or multi-lane approaches (unmodeled).
- **Safety against DECEPTIVE or mistaken intent** — a driver who signals one
  movement and performs another (worst case: signal "right", the trusted
  low-conflict co-activation, then turn "left", maximum conflict).
  CHARACTERIZED (2026-07-21, `adversarial_intent.py`, 516 two/three-car
  scenarios with an R-declarer): **the current trusting controller is
  exposed** — a false right/left drops the cross-path floor from the honest
  3.46 m baseline to **2.56 m**, breaching the 3.5 m margin in **32% (164/516)**
  of adversarial scenarios (the EXIT_ARM co-activation shortcut green-lights
  against the declared right, not the true left). A **motion-confirmed-intent
  defense** (extend the phantom/`REVEAL_M` net to ALL declared intent, not
  just unreadable) **fully closes it**: floor back to 3.48 m = the honest
  baseline, zero real residual breaches, so a false signal costs only
  throughput. **Integrated into the controller** (`motion_confirmed_intent.py`,
  `ConfirmedSmartStop`) and validated by construction — given a false-signaler
  with NO harness help it holds the 3.48 m floor and rescues all 164 exposed
  scenarios (`validate_confirmed_controller.py`). Cost: **+45.7% clearance on
  the discrete scenarios** (the price of not trusting intent-dependent
  co-activations; topologically-safe pairs are unaffected). **Still do NOT
  claim adversarial-intent safety as a shipped property:** `ConfirmedSmartStop`
  is not yet the default controller. STREAMING COST MEASURED (2026-07-21,
  `confirmed_streaming.py`): the universal version costs **+242% at arterial
  2,000** (56.9 → 194.6 s, worse than the roundabout's 73.3 s) — the intent-
  dependent co-activation that wins the arterial is exactly what it disables.
  **NOT viable as the shipped controller.** Evasive braking is not an
  alternative — a false co-activation risks an in-box jam (conflict inside the
  intersection, worse than a stop sign). **Deciding experiment DONE**
  (`reveal_sweep.py`, 2026-07-21): **no reveal distance is both safe and
  affordable.** Safety needs reveal >= 2.0 m (at 1.0 m the floor is 2.36 m —
  breaches *worse* than no defense); every safe setting costs +200%+ on the
  arterial (2.0 m: 180.6 s / +218%; 4.0 m: 194.6 s / +242%) — losing to the
  roundabout's 73.3 s at every one. The arterial win requires co-activating
  opposing platoons on trust the instant they arrive; any confirmation
  staggers them and the cost compounds. **VERDICT: at single-lane 4-way
  stops, trust-the-signal throughput and false-signal safety are mutually
  exclusive.** The "any 4-way stop, safe" framing does not survive. Pivot
  candidates: (a) turn-lane/multi-lane intersections where intent is physical
  (lane position, forge-resistant); (b) V2X intent; (c) **roundabout-style
  deflection geometry** so a false co-activation degrades to a yield/merge
  rather than a center collapse — removes the catastrophic failure mode
  instead of confirming intent, so it may keep the throughput (model already
  carries roundabout pathing). **RESOLVED for deployment (2026-07-21):
  Smart Safe absorbs the attack by construction** — across all 516 adversarial
  scenarios it holds a 3.99 m floor with ZERO breaches (`safe_family_adversarial.py`),
  because its conservative co-activation never over-trusts intent. Note: base
  Smart Safe only relabels NO-SIGNAL as worst-case left — it *trusts* a
  declared right, so its false-right safety is incidental (margin + true-path
  distance check), not by design. **`SmartSafeR` (`safe_r.py`) closes that
  explicitly**: a declared right is treated as a potential left until motion
  confirms the turn (fast — a right diverges early in the arc; a false right
  reveals as left and is never trusted). By-construction guarantee at ~0 cost
  (−1.6% honest clearance vs base, 0/516 breaches). Recommended over base for
  any safety claim. The trusting
  full-throughput controller has essentially NO tolerable cheat rate — the
  streaming floor cliffs to contact (~0 m) at just q=1% false-signalers
  (`cheat_rate_sweep.py`; served stays 100%, so it's a collision, not a jam).
  So: **Smart Safe is the deception-resistant deployment mode**; full Smart
  Stop is the speed-optimized upper bound that requires trusted intent
  (turn-lane/V2X) or the deflection-geometry pivot. **⚠ SUPERSEDED 2026-10-01
  by the OBB survival gate (claim 5): both controllers below physically
  overlapped; under one footprint standard Smart Safe reaches only arterial
  parity and loses dominant on capacity.** ~~Survival gate PASSED,
  5-seed confirmed (2026-07-21, `multiseed_safe_vs_rb.py`):** streaming Smart
  Safe (straight treated as worst-case left) clears parity-or-better with the
  roundabout in 3/4 regime cells (mean ± std over 5 seeds):
  - arterial 2,000: **44.0 ±15.5 vs 55.5 ±21.3 — Safe WINS** (on average;
    distributions partly overlap, so claim "wins across seeds", not point
    precision).
  - single-dominant 2,400: 135.4 ±7.6 vs 129.0 ±11.5 — **parity** (roundabout
    edges it within noise; do NOT claim a win here — single-seed said win, the
    seed sweep corrected it).
  - light 1,000: 1.9 vs 1.8 — parity (both trivial).
  - balanced-heavy 2,400: 67.6 vs 37.1 — **Safe loses** (the roundabout's
    regime, conceded as always).
  Smart Safe runs within seed noise of full Smart Stop in every cell, so the
  deception-resistant mode costs essentially no throughput vs the trusting one
  (NOT "faster" — that single-seed artifact did not survive). Caveats: streaming
  Smart Safe is an adaptation of the discrete algorithm (relabel straight->L);
  variance is large (~35-40% of the mean at saturation) — cite ranges, never
  single-seed precision.~~
- ~~Compliance as an open hazard~~ — CLOSED at v1 (Block 7): raw
  flash-jumper hazard confirmed under physically-honest jumps (1.97 m at
  q=5%, 0.02 m at q=10%, unmitigated); the mitigation stack (reactive
  evasive braking + unauthorized-motion flash hold) eliminates collisions
  — worst case 3.24 m across all balanced cells, ~5% delay cost, 100%
  served. Residual: evasive dynamics erode the design margin by up to
  0.26 m even at q=0, and on the hot split the erosion is deeper (typical
  3.27 m; worst 2.84 m at q=10% × 2,000 — Block 7b, July 15). BRAKE_RANGE
  tightening is a next-phase calibration item. Claim as: "collisions
  eliminated in v1 mitigation; margin tuning ongoing." 

## Pinned constants (sources in REALITY_REPORT.md)

25% unsignaled turns (SAE 2012-01-0261); 1.9 s saturation headway / 2.2 s
start-up lost time (HCM); 2.0 s queue move-up and ~2.9 s emergent platoon
discharge headway in-sim (conservative vs the 1.9 s saturation standard);
roundabout critical gap 4.5 s within the 3.86-field / ~5.0-HCM band,
follow-up 2.8 s (HCM 2.6–3.1). **Critical-gap sensitivity (±0.6 s, July 15):
no regime-map verdict changes across the field-to-HCM band** — the arterial
win holds at every gap (margin narrows to ~20–25% at the aggressive 3.9 s
bound); the balanced-heavy concession stands at the pinned calibration
(details in REALITY_REPORT).
