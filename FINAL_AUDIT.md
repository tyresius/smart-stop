# Smart Stop — Final Audit Package (revision 3)

**Prepared 2026-11-15; revision 3 applies the publication-readiness audit
(audit 4, §8).** Self-contained: you do not need any prior conversation, or
earlier revisions of this file (in git history). Repository: this folder
(`ClaudeStop`). It is also supplied as a frozen archive containing:
- `AUDIT_VERSION.txt`: commit and environment;
- `requirements-lock.txt`: the pinned simulation environment;
- `MANIFEST.sha256`;
- `VERIFY_LOG.txt`: tests and summaries re-run on the archive itself.

Current claims: `CLAIMS.md`.

---

## 0. What we are asking you to do

Since revision 1 (2026-11-09), a third external audit found real defects in
the comparators, the safety observer and the controller's information use.
They were fixed, the key experiments were re-run, and the conclusions changed
substantially (§3). **Audit the current conclusions (§2) in both directions:**

1. **Are they too generous?** Look first at the remaining asymmetries in §6,
   and at any place where a fix might have tilted the comparison toward Smart
   Stop.
2. **Are they too harsh?** Is there a defensible change that would move the
   picture materially?
3. **Check the process:** the audit responses in §8, and whether each fix was
   applied symmetrically.

Posture: try to break the conclusions. Prefer checkable findings with
`file:line` references. Separate "wrong," "unjustified" and "arguable." Say
when you can't verify something, and say which way each of your proposed
changes would move the result.

---

## 1. What Smart Stop is

An ordinary 4-way stop sign plus a camera and a green flash for each approach.
The controller flashes cars whose movements don't conflict, so several can go
at once. A car flashed as it arrives may roll through without stopping.

It is intended to avoid roadway reconstruction. Installation, power, sight
lines, maintenance and regulatory requirements are not evaluated here, and a
flashing green is not a standard MUTCD indication.

Two controller designs are evaluated:

| design | what it knows | safety property |
|---|---|---|
| **Blind** (current Smart Safe) | Ignores turn signals; every car could be making any movement until it has moved 4 m (`REVEAL_M`) | Safe even if drivers signal falsely |
| **Signal-reading** | Believes turn signals, as human drivers at a stop sign do; a car that doesn't signal is "any movement" until it has moved 4 m | Exposed to false signals, like a stop sign |

The blind rule was adopted in July 2026, after a car that signals right but
turns left was shown to break the safety margin of a controller that trusts
signals.

Comparators:
- **The existing all-way stop**, the buyer's real alternative.
- **A mini-roundabout**, the civil-works alternative.
- **An actuated signal**, a secondary comparator.

---

## 2. Conclusions under audit

All figures come from a simulation of one isolated, single-lane, 4-way
intersection (§4). "Delay" is mean control delay per car with every stop
charged (§4.3). Paired 95% intervals on matched arrival seeds.

| # | claim | evidence |
|---|---|---|
| C1 | **Against the modeled stop-sign baseline, under a 25% non-signalling, no-deception scenario,** both designs cut delay at 600-800 veh/h. Signal-reading: about 3x lower (2.6 vs 7.4 s at 600; 4.4 vs 13.3 s at 800, balanced). Blind: 4.4 and 8.8 s. Every difference resolved. The modeled stop sign is slower than HCM (§5.6), which can exaggerate the gain at 800 | §5.1, `fair_signalling_test.txt` |
| C2 | **Observed contacts.** The independent checker flagged **0 footprint overlaps in 1,736 model executions** under honest-driver assumptions. Many share scenarios and seeds, so these are not 1,736 independent trials, and no failure-rate bound follows. In a stress scenario with 2% false signals (279 drivers), the raw counts were: stop sign 61, signal-reading Smart Safe 47, blind 0. These counts are descriptive; no relative risk or crash rate can be inferred | §5.2 |
| C3 | **Where the advantage comes from:** (a) rolling: cars flashed on arrival don't stop; (b) releasing non-conflicting cars together, which needs to know where cars are going. The blind rule gives up most of (b): with the same information as the stop sign's drivers, Smart Safe's delay is 3-4x lower | §5.3, §5.4 |
| C4 | **Fragility to driver hesitation** at the novel flash (blind design): 0.5 s of hesitation keeps the edge only in light traffic (400 veh/h; 600 balanced); 1 s erases it above 400. Not yet tested for the signal-reading design | §5.4 |
| C5 | **Against an actuated signal** (secondary comparator; a city wouldn't install one at these volumes): in this model the stop sign itself beats the signal at 400-800 veh/h balanced and at 600 arterial. Blind rolling Smart Safe beats the signal at 400-800 veh/h, except 800 arterial (unresolved). The signal-reading design was not run against the signal | §5.5, `rolling_hesitation_test.txt` |
| C6 | **Against a mini-roundabout**, re-run under the same standards. **The roundabout is the best performer at 600-800 veh/h** on all three splits: 2.2-3.6 s per car, against the stop sign's 7.2-13.9. Signal-reading Smart Safe: at 600 veh/h it is nearly indistinguishable on arterial and dominant traffic (+0.1 s, unresolved) and 0.4 s behind on balanced; at 800 veh/h its mean delay is **23-47% higher** (+0.8 to +1.6 s, resolved). Blind Smart Safe: 1.3-6.2 s behind | §5.7, `roundabout_rerun.txt` |

**Not claimed:** real-world collision-freedom; any result above 800 veh/h as
a headline (the stop-sign and roundabout models are both too slow near
saturation, §6); commercial viability (no economic analysis, including no
construction-cost comparison with a roundabout); regulatory approval.

**Verdict under audit:** *a bounded simulation result; commercially and
regulatorily open.*
- Against the modeled all-way stop, both designs cut delay at 600-800 veh/h.
- Signal-reading Smart Stop comes close to a mini-roundabout at 600 veh/h but
  falls clearly behind it at 800.
- The blind design gives about half of the signal-reading improvement over
  the stop sign.

Smart Stop is intended to avoid the roadway reconstruction a roundabout
needs; whether it can be installed, approved and paid for is not evaluated.

**What can be said publicly** (adapted from audit 4):

> In a simulated isolated, single-lane four-way intersection without
> pedestrians, under a 25% non-signalling, no-deception scenario, the
> signal-reading Smart Stop controller had lower mean control delay than the
> modeled all-way-stop baseline at 600 and 800 veh/h. The blind version also
> had lower delays, with a smaller improvement. Both results depend on
> particular stopping, geometry and perception assumptions. In the same
> model, a corrected mini-roundabout generally had lower delays than either,
> especially at 800 veh/h. An independent monitor flagged no footprint
> overlaps in the honest-driver runs; this is not a real-world safety claim.
> Whether the system can be deployed safely, legally and economically is
> unresolved.

The October 2026 verdict ("commercially doubtful, wins only where stop signs
aren't failing") rested largely on modelling artifacts (§7). The open
questions are now outside the throughput model:
- federal approval of a flashing-green indication (MUTCD/FHWA);
- whether drivers trust the flash enough not to hesitate;
- pedestrians;
- the policy choice between the blind and signal-reading designs.

---

## 3. How the conclusions changed

| date | step | effect |
|---|---|---|
| Jul 2026 | Original claims (~4x capacity vs all-way stop); deceptive-signal tests | Blind ("motion-confirmed") Smart Safe becomes the product |
| Sep-Oct | External audit 0: centre-distance safety metric hid footprint overlaps → oriented-box (OBB) checks; roundabout benchmark corrected | Smart Safe reaches only parity with the roundabout |
| 3 Oct | Signal comparator built; an oracle leak (Smart Safe walking true paths) found and removed; hesitation sweep | Verdict: "beats a signal only below ~800-1,000 veh/h, no buyer pays" |
| 9 Nov | Audits 1 and 2 (rev 1) | Verdict overstated; paired intervals: 1,000 veh/h unresolved; platoon cap not the cause |
| 11 Nov | **Audit 3** (code-level). Fixed: all-way-stop baseline (F1, F2), independent continuous-time checker (F3), tangent headings (F4), three more information leaks and prediction errors in the blind controller | Rebuilt stop sign 17.1 → 4.5 s at 600 veh/h (old metric). Smart Safe appeared to tie a full-stop stop sign |
| 11 Nov | Stop penalty: stopping now costs its braking and acceleration time | Rolling's value roughly doubles |
| 11 Nov | Rolling × hesitation × widening factorial (720 runs) | Hesitation's cost is the delay and the lost roll; widening never mattered |
| 12 Nov | **Patrick's objection** ("rolling + multi-car release must beat a stop sign"): dominance diagnostic | Cause found: blind Smart Safe was compared against human drivers who read honest signals. With equal information: 3-4x |
| 12 Nov | Fair signalling test: non-signalling and lying drivers on both sides | C1, C2 |
| 15 Nov | Zero move-up-time sensitivity (audit 3 F7) | The 600-800 wins survive that one queue lever (§5.6) |
| 15 Nov | Roundabout re-run under current standards. Its gap check ignored cars still on an entry arc (4 contacts in 90 runs); fixed. Sanity-checked against two HCM-style entry-capacity curves | C6: the roundabout is the strongest comparator |
| 15 Nov | **Audit 4** (publication readiness): conditional go as a labelled simulation study | Wording corrected throughout; frozen archive supplied (§8) |

---

## 4. The model

### 4.1 World

- **Intersection:** one isolated 4-way, single lane per approach. The box is
  ±6.1 m; opposing lanes are 4.5 m apart (`path_based_smart_stop.py`
  `FourWayGeometry`).
- **Cars:** 4.5 × 2.0 m. Launch acceleration 1.5 m/s². Cruise 6 m/s
  (13 mph). Curvature speed caps in the box: straight 6.0, left 4.4,
  right 3.2 m/s (`reality_sweeps.py:152`).
- **Reaction delay:** U(0.5, 2.0) s for every car starting from rest
  (`capacity_curves.py` `JITTER`). Platoon followers are capped at 0.6 s
  (`block3_reality.py` `FOLLOWER_MAX_DWELL`).
- **Arrivals:** Poisson. Turn mix 15% left / 70% straight / 15% right.
  "Balanced" splits demand equally over four approaches; "arterial" is
  40/40/10/10. Windows: 120 s warm-up, 480 s measured, up to 300 s drain.
  Seed-matched across controllers (`make_schedule`).
- **Rolling:** a car flashed within 0.3 s of reaching the line enters at its
  speed cap (`block3_reality.py` `RollingVehicle`).

### 4.2 Controllers (current versions; legacy versions kept so old results reproduce)

| controller | class | key rules |
|---|---|---|
| Smart Safe, blind | `BlindSafeV2` / `BlindSafeV2Hes` (`blind_safe_v2.py`) | Each unrevealed car is checked against all three possible paths until 4 m. Release needs a footprint (OBB) check with a 1.0 m clearance buffer (0.5 m a side), under launch-delay hypotheses of 0 / 1.2 / 2.5 s, with tangent headings (`obb_survival_gate.HEADING_MODE`). Platoons of up to 4 per flash, grouped by lane. No priority by movement |
| Smart Safe, signal-reading | `SafeReadsSignals` (`fair_signalling_test.py`) | As blind, but a signalling car is predicted on its declared movement; priority and grouping use declared movements |
| Stop sign | `HumanFourWayFCFS` (`cs4_human_baseline.py`) | First-come-first-served; simultaneous arrivals yield to the right. The car whose turn it is goes once every moving car has passed its conflict area (a precomputed corridor with a 0.5 m margin) or is ahead in its lane, same movement, ≥ 5.5 m. Other cars go out of turn only if their movement never conflicts with any moving car |
| Stop sign, signal-aware drivers | `StopSignSignals` (`fair_signalling_test.py`) | As above, but drivers know only their own movement; others' come from signals or, after 4 m, from motion |
| Mini-roundabout | `RoundaboutOBB` (`obb_survival_gate.py`), as run in `roundabout_rerun.py` | Ring radius 6.75 m, ring speed 4.1 m/s (same curvature rule as 4-way turns). Gap acceptance: 4.5 s critical gap, 2.8 s follow-up (`roundabout_entry.py`, `block3_reality.RealisticRoundabout`). A car that has passed its entry arc is gap-checked like a circulating car (`GAP_INCLUDES_ENTERING`, 15 Nov fix). Rolling entry when clear. No extra reaction dwell (the gap already includes decision time). 1.5 m yield-line setback; footprint entry check, B = 1.0 m. Needs no turn signals, so it is the same in every regime |
| Actuated signal | `SignalActuated` (`stopsign_vs_signal.py`) | Two phases. Min/max green 8/40 s, passage 3 s, yellow 3.5 s, all-red 1.5 s. Permitted lefts use the OBB check. Platoons up to 50 |

### 4.3 Delay metric

`control_delay_sp` (`capacity_curves.py`, "Stop penalty"): time from arrival
to leaving the box, minus the time an unimpeded car takes when it crosses the
line at its speed cap without stopping. A car that stops also pays its braking
loss, v/(2 × 3 m/s²).

At the model's speeds a stop therefore costs 1.6-3.0 s. HCM allows about 5 s
per stop at typical approach speeds; `control_delay_hcm` is that sensitivity.
The legacy `control_delay` (stops free) is still reported, so old results
reproduce.

### 4.4 Information regimes (fair signalling test)

| regime (code label) | non-signallers | false signals |
|---|---|---|
| perfect | 0% | 0% |
| realistic: in headlines, "25% non-signalling, no deception" | 25% (the SAE field share used elsewhere in this project) | 0% |
| liars: a stress scenario, reported separately | 25% | 2% signal right (or straight, if really turning right) and go another way. An assumption, not field data |

"Realistic" here means only this signalling assumption. Misclassification,
hesitation, occlusion, pedestrians and evasive braking are not in any regime.

Each driver's behaviour is fixed by arrival number and seed, so every
controller faces the identical drivers.

### 4.5 Safety measurement

`independent_checker.py` shares no code with the decision checks:
- It uses its own footprint and exact polygon distance.
- It checks every pair of moving cars, including same-lane pairs.
- It checks moving cars against the front car waiting at each stop line.
- It certifies contact between 0.1 s steps (Lipschitz bound plus bisection).

Same-lane "contacts" between a car pulling away and the next queued car are a
known queue-model artifact: the model draws queued cars at the line. They are
reported separately and not counted. 12 unit and staged-collision tests:
`test_independent_checker.py`.

**The 1.0 m clearance buffer is a decision parameter, not a guaranteed
separation.** It is applied to predicted footprints when a release is
decided. Realized closest approaches between moving cars go down to:

| controller | closest approach |
|---|---|
| Roundabout | 0.21 m |
| Stop sign | 0.57 m |
| Signal-reading Smart Safe | 0.58 m |
| Blind Smart Safe | 1.24 m |

Some pairs are never constrained by a decision check at all.

---

## 5. Results

### 5.1 Headline: 25% non-signalling, no deception, on both sides (`fair_signalling_test.txt`, 10 seeds)

Mean delay per car (s), balanced / arterial. These are relative to the
**modeled** stop-sign baseline, whose saturation headways are 12-66% slower
than HCM's (§5.6). That can exaggerate the improvement, most at 800 veh/h.

| | 600 veh/h | 800 veh/h | 1,000 veh/h (directional) |
|---|---|---|---|
| Stop sign | 7.4 / 7.2 | 13.3 / 13.3 | 40.6 / 39.4 |
| Smart Safe, blind | 4.4 / 4.4 | 8.8 / 9.8 | 26.6 / 30.6 |
| Smart Safe, signal-reading | **2.6 / 2.5** | **4.4 / 4.4** | 8.0 / 7.9 |

Paired differences against the stop sign (25% non-signalling, no deception):

| | 600 veh/h | 800 veh/h | 1,000 veh/h |
|---|---|---|---|
| Signal-reading | −4.8 [−5.2, −4.4] / −4.7 [−5.1, −4.4] | −9.0 [−11.6, −6.4] / −8.9 [−10.6, −7.1] | −32.6 / −31.6 |
| Blind | −3.1 / −2.9 | −4.6 / −3.5 | −14.0 / −8.8 |

Every difference against the stop sign is resolved in the non-signalling and liar
regimes. Under perfect signals, blind at 1,000 veh/h is not resolved.

Two effects of 25% non-signalling (vs perfect signals):
- **Cost to Smart Safe:** 0.5-2.5 s per car.
- **Cost to the stop sign:** 0.2-6.6 s per car, rising with volume. Human
  drivers at a stop sign have to wait out non-signallers too.

Share of cars that had to stop: stop sign 100%; signal-reading 34-48% at
600-800; blind 51-73%.

### 5.2 Safety across all experiments

| experiment | runs (honest drivers) | contacts | closest moving pair |
|---|---|---|---|
| `checker_validation` (legacy committed cells, V2 smoke, stop sign) | 76 | 0 | legacy Smart Safe 0.58 m, signal 0.77 m |
| `awsc_rebaseline` (stop sign, 400-1,200) | 100 | 0 | n/a |
| `rolling_hesitation_test` | 720 | 0 | blind V2 1.24 m, signal 0.69 m, stop sign 0.57 m |
| `dominance_check` | 240 | 0 | n/a |
| `fair_signalling_test` (perfect, realistic) | 300 | 0 | signal-reading 0.58 m, blind 1.24 m, stop sign 0.57 m |
| `moveup_sensitivity` | 120 | 0 | n/a |
| `roundabout_rerun` (fixed roundabout, all splits; dominant split for the others) | 180 | 0 | roundabout 0.21 m |
| **Total** | **1,736 model executions** | **0 flagged** | |

Many executions share scenarios and seeds, so the total is useful for
catching implementation contacts. It is not independent exposure, and no
failure-rate bound follows from it.

The unfixed (October-rules) roundabout had 4 contacts in 90 runs. That is the
defect fixed on 15 Nov (§3); those runs are not in the total.

**False-signal stress scenario** (`liars` regime, 279 lying drivers, the same
drivers for everyone). Every contact involved a liar.

| controller | contacts (raw count) |
|---|---|
| Stop sign | 61 |
| Signal-reading Smart Safe | 47 |
| Blind Smart Safe | 0 |

Run by run (60 paired runs), signal-reading Smart Safe had fewer contacts than
the stop sign in 17 runs, more in 9, and the same number in 34.

These counts are descriptive. No evasive braking is modelled, and the
scenarios are not representative crash exposure, so neither relative risk nor
a crash rate can be inferred. Do not quote a percentage safety gain.

### 5.3 Information is the limit on the blind design (`dominance_check.txt`, 5 seeds, perfect signals)

| suspect | effect |
|---|---|
| The legacy 4-active-car cap on Smart Safe (`MAX_ACTIVE`) | Never blocked a release: no effect |
| Restricting stop-sign drivers to the classic pairings | +0 to +3 s for the stop sign: small |
| Giving Smart Safe the drivers' turn-signal knowledge | −2 s at 600 veh/h, −5 to −7.5 s at 800, −12 to −15 s at 1,000 |

With that knowledge, Smart Safe beats the stop sign even with full stops (no
rolling). Multi-car release alone wins.

### 5.4 Rolling × hesitation (`rolling_hesitation_test.txt`, blind V2, 10 seeds, vs perfect-signal stop sign)

Seconds saved per car, balanced / arterial:

| hesitation | 400 veh/h | 600 veh/h | 800 veh/h |
|---|---|---|---|
| none | 3.1 / 3.6 | 2.9 / 2.6 | 3.1 / 2.1 |
| 0.5 s | 2.2 / 2.5 | 1.0 / tie | tie / −5.3 |
| 1 s | 1.0 / tie | −1.7 / −2.5 | −10 / −16 |

- **Full stops (no rolling) never beat the stop sign** in the blind design.
- **Widening the controller's launch-delay hypotheses changed no decision in
  any of the 720 runs.** It is neither a safety requirement nor a capacity
  cost. Hesitation costs only the delay itself and the lost roll.
- **A hesitant roller is modelled as crossing the line H seconds late,
  still at speed.**

### 5.5 Stop penalty and the signal (`stop_penalty_check.txt`, legacy controllers, 5 seeds)

- **Charging for stops roughly doubles rolling's value:** rolling vs the
  stop sign goes from about −2 s to −3 to −3.7 s per car at 400-800 veh/h
  (−4 to −5 s HCM-scaled).
- **The stop sign beats the actuated signal at 400-800 veh/h** (balanced),
  the textbook result at low volume. The signal wins at 800 arterial and
  1,200 veh/h.

### 5.6 Calibration and sensitivities

**Stop sign vs HCM** (`awsc_calibration.txt`): saturation departure headways
(s) by HCM case.

| case | HCM | model |
|---|---|---|
| 1 | 3.84 | 4.30 |
| 2 | 4.64 | 5.90 |
| 3 | 5.74 | 9.50 |
| 5 | 9.54 | 13.56 |

The model is 12-65% slower than HCM because of the shared launch dynamics.
With 2.5 m/s² launches and no reaction delay, case 3 matches HCM, but case 1
becomes too fast. The dynamics were not retuned, because that would move
every controller.

**Zero move-up-time sensitivity** (`moveup_sensitivity.txt`): setting the
stop sign's queue move-up time from 2 s to 0 improves it by at most 1.0 s.
Every Smart Safe win at 600-800 holds; blind arterial at 1,000 becomes
unresolved.

This changes one queue lever. It does not make the two queue models
identical: car-following, stopping positions and reaction timing still
differ.

**Predicted headings** (`heading_error_check.txt`): the legacy chord method
was off by up to 47° on rights and 59° on lefts. That moves a box corner up to
2.4 m. Fixed with tangent headings.

**Roundabout vs HCM** (`roundabout_calibration.txt`): simulated entry
capacity (veh/h) against circulating flow v_c.

| v_c | model | HCM 2010 (1130·e^−0.0010 v_c) | HCM 6 (1380·e^−0.00102 v_c) |
|---|---|---|---|
| 0 | 1,196 | 1,130 | 1,380 |
| 252 | 949 | 878 | 1,067 |
| 520 | 634 | 672 | 812 |
| 880 | 270 | 469 | 563 |

This is a sanity check against two HCM-style curves (2 seeds, one entry,
circulating flow approximated as 85% of one approach's departures), not a
validation. Against the curves, the model is:
- within about 10% of both up to ~250 veh/h circulating;
- 6-22% below at ~520;
- 42-52% below at ~880.

The roundabout is therefore pessimistic at heavy circulating flow, which
flatters Smart Stop above 800 veh/h. HCM coefficients are as commonly cited;
verify them against the HCM roundabout chapter.

**Legacy reproduction:** every switch added since 9 Nov defaults to legacy
behaviour. The committed hesitation-sweep delays reproduce exactly
(`checker_validation.txt`, `stop_penalty_check.txt`).

### 5.7 The roundabout (`roundabout_rerun.txt`, 25% non-signalling, no deception, 10 seeds)

Mean delay per car (s):

| split | veh/h | stop sign | Smart Safe, blind | Smart Safe, signal-reading | roundabout |
|---|---|---|---|---|---|
| balanced | 600 | 7.4 | 4.4 | 2.6 | **2.2** |
| | 800 | 13.3 | 8.8 | 4.4 | **3.0** |
| arterial | 600 | 7.2 | 4.4 | 2.5 | **2.4** |
| | 800 | 13.3 | 9.8 | 4.4 | **3.6** |
| dominant (55/15/15/15) | 600 | 7.6 | 3.6 | 2.4 | **2.3** |
| | 800 | 13.9 | 8.9 | 4.8 | **3.3** |

Paired differences against the roundabout:

| | 600 veh/h | 800 veh/h |
|---|---|---|
| Signal-reading Smart Safe | +0.4 s balanced (resolved); +0.1 s arterial and dominant (unresolved) | +0.8 to +1.6 s, all resolved (**23-47% higher** mean delay: balanced +46%, arterial +23%, dominant +47%) |
| Blind Smart Safe | +1.3 to +2.1 s | +5.6 to +6.2 s |

At 800 veh/h the roundabout's advantage over signal-reading Smart Safe is
small in seconds but large in relative terms. Present both.

The roundabout beats the stop sign by 5-11 s per car. At 1,000 veh/h
(directional) it stays at 4-5 s while every other option rises.

The 15 Nov entry fix cost the roundabout 0.1-0.2 s and removed its 4
contacts. The October comparison ("Smart Safe reaches parity only on
arterial") ran at 1,000-2,400 veh/h with the old metric; it is superseded.

---

## 6. Remaining limitations and asymmetries (and which way each cuts)

| item | direction |
|---|---|
| The stop-sign model is 12-65% slower than HCM near saturation | Flatters Smart Stop at 800+ veh/h, which is why the headline stops at 800 |
| Shared slow dynamics (13 mph cruise, 1.5 m/s² launches); a stop costs 1.6-3.0 s vs HCM's ~5 s | Understates the value of not stopping (HCM-scaled sensitivity reported) |
| Intent read perfectly and instantly once a car has moved 4 m; no camera errors, latency or occlusion | Flatters both designs; `REVEAL_M` never swept |
| Uniform hesitation, no learning; hesitant rollers cross late at speed | Arguable both ways |
| No evasive braking anywhere | Contact counts overstate crashes; only the comparisons carry weight |
| Waiting cars are drawn with their centre on the stop line (passing cars come within 0.07 m of them; no contacts) | Same for all controllers |
| Signal: permitted lefts accept any OBB-clear gap; timing not tuned | Mixed; the signal is a secondary comparator |
| Stop-sign drivers know the conflict geometry perfectly (0.5 m margin) | Flatters the stop sign |
| Hesitation untested for the signal-reading design | Unknown |
| One isolated single-lane intersection; no pedestrians, cyclists or heavy vehicles | Untested; pedestrians are the largest gap for urban sites |
| 10 seeds (5 in the dominance check); 480 s measurement window | Variance is large at 1,000 veh/h |
| Roundabout: entry capacity within ~10% of two HCM-style curves up to ~250 veh/h circulating, 6-22% below at ~520, 42-52% below at ~880; ring speed 4.1 m/s (curvature rule); one mini-roundabout geometry | Makes the roundabout pessimistic at high volume (flatters Smart Stop above 800) |
| The 1.0 m decision buffer is not a realized separation (closest approaches 0.21-1.24 m by controller) | No guaranteed physical margin can be claimed |
| Zero move-up-time sensitivity changes one queue lever only | Remaining queue-model differences unquantified |
| Rolling legality, driver adaptation to a novel indication, pedestrians and vulnerable road users | **Not modeled / not established** |
| Roundabout drivers judge gaps from positions only; they don't use circulating cars' exit signals | Slightly pessimistic for the roundabout |

---

## 7. Retracted or superseded claims

| claim | status |
|---|---|
| "~4x capacity vs an all-way stop" (July) | Superseded: predates the footprint standard, the oracle-leak fix and the rebuilt stop sign |
| "Smart Safe 3-10x better than a signal" (3 Oct) | Retracted the same day (oracle leak) |
| October verdict: "beats a signal only below ~800-1,000 veh/h; no buyer pays where it wins" | Withdrawn 9 Nov (overstated) |
| Legacy all-way-stop delays (17.1 s at 600 veh/h; 110 s at 1,000) | Artifacts of audit 3 F1/F2 (priority scoring; held for the whole path) |
| "The rebuilt stop sign ties Smart Safe; its only edge is rolling" (11 Nov) | Withdrawn 12 Nov: a blind controller was being compared with sighted drivers |
| "Collision-free" | Never claimable; "no contacts observed in the model" |
| Roundabout parity and regime map (Oct): "Smart Safe reaches parity on arterial, loses balanced and dominant" | Superseded by `roundabout_rerun` (15 Nov). Its direction held: the roundabout beats blind Smart Safe on every split. But it was measured at 1,000-2,400 veh/h, with stops free, and with an entry-rule defect |

---

## 8. External audits and responses

- **Audit 0 (Sep, Gemini):** the centre-distance safety metric hid footprint
  overlaps. Accepted; OBB standard adopted.
- **Audit 1 (9 Nov, document-level):** headline overstated; hesitation
  confounded three factors; statistics thin; economics unanalysed; MUTCD
  barrier. All accepted. The hesitation confound is now separated (§5.4).
- **Audit 2 (9 Nov):** "verdict is a modelling artifact." Its specific
  claims were mostly wrong when checked against the code:
  - the box is 5.5 × 3.0 m, not 6.5 × 4.0;
  - the roundabout already has a 4.5 s gap;
  - the platoon cap is not the cause.

  Its conclusion turned out partly right, for different reasons (§7).
- **Audit 3 (11 Nov, code-level):** findings F1-F12. Code-verified and
  fixed:
  - F1/F2: the stop-sign baseline;
  - F3: the safety observer;
  - F4: predicted headings;
  - F5: information leaks.

  Also fixed in the same pass, beyond what audit 3 reported: priority by true
  movement, stand-in cars at the wrong speed cap, and stand-ins ignoring
  car-following. Its objection to the plan's "ceiling screen" (F9) was
  accepted. F7 (queue model) was bounded (§5.6). F6 (perfect classifier) and
  F10 (comparator calibration) remain open (§6).
- **Audit 4 (15 Nov, publication readiness):** conditional go as a clearly
  labelled simulation study; no-go for engineering-design, physical-safety
  or commercial claims. No modelling bugs found. It confirmed the roundabout
  fix and its effect from the raw CSV.

  Findings, all accepted:

  | finding | change |
  |---|---|
  | F1: the archive lacked the current source | Frozen archive with commit, environment, checksums and a verification log |
  | F2: "roughly matches the roundabout" hid 23-47% at 800 | C6 and the verdict reworded |
  | F3: "realistic" is only a signalling assumption | Relabelled "25% non-signalling, no deception" |
  | F4: roundabout "calibrated" overstated | Now "sanity-checked", with the deviations stated |
  | F5: stop-sign calibration caveat | Placed beside the headline table |
  | F6: the 1 m buffer is not a realized separation | Stated, with the closest approaches |
  | F7: zero move-up is one lever, not identical queues | Reworded |
  | F8: liar contacts are descriptive only | Raw counts plus run-by-run split; no relative risk |
  | F9: 1,736 are not independent trials | Reworded |
  | F10: "no civil works" is a hypothesis | Now "intended to avoid roadway reconstruction; not evaluated" |
  | F12: stale CLAIMS header | `CLAIMS.md` is now a dated one-pager; history moved to `CLAIMS_ARCHIVE.md` |

---

## 9. Questions for this audit

1. Is the **fair signalling test** (`fair_signalling_test.py`) symmetric?
   Do the stop sign's drivers and signal-reading Smart Safe really use the
   same information, the same reveal rule and the same treatment of
   non-signallers?
2. Is the rebuilt **stop sign** (`cs4_human_baseline.HumanFourWayFCFS`) a
   fair human baseline? Is its conflict-area rule too generous or too strict
   relative to field behaviour, given the HCM calibration in §5.6?
3. Is the **stop penalty** (`capacity_curves.py`) correct, and is
   charging braking loss only to stopped cars right?
4. Does the **independent checker** have gaps: categories excluded,
   interpolation, or the waiting-car rule?
5. Are the **blind V2 fixes** (`blind_safe_v2.py`) complete? Does any
   remaining controller path read a car's true movement before 4 m?
   (`test_blind_no_truth.py` traces `.signal`, but not `true_signal` after
   reveal, or speed caps.)
6. Do the conclusions survive the **limitations in §6**? Which would you test
   before presenting?
7. Is the **roundabout** a fair comparator?
   - its gap parameters, the 15 Nov entry fix and the calibration in §5.6;
   - the ring speed and geometry;
   - whether the entry fix is symmetric with the fixes made to Smart Safe.
8. Is the **verdict wording** in §2 justified, or still too strong or too
   weak? That includes the publicly quotable paragraph.

---

## 10. Open questions (replaces FALSIFICATION_PLAN.md)

1. **Camera intent reading** at 1-2 m instead of 4 m, with misclassification
   and latency. This is the main route to recovering the signal-reading
   advantage while keeping the blind design's safety.
2. **Driver hesitation** under the signal-reading design.
3. **Pedestrians and cyclists.**
4. **Vehicle dynamics calibrated to HCM** for every controller.
5. **Economics:** installed cost vs time, fuel and emissions saved per site,
   and against the construction cost of a mini-roundabout.
6. **The FHWA experimentation route** for a flashing-green indication. The
   MUTCD is the 11th Edition with Revision 1 (December 2025, effective
   March 5, 2026).
7. **Multi-lane approaches,** and roundabout geometries other than one
   mini-roundabout.

---

## 11. How to reproduce

Python 3.13 with the packages pinned in `requirements-lock.txt` (numpy is the only one
the simulation needs). Runtimes are for an 8-10 core Mac. Run long jobs
detached. In the frozen archive, `VERIFY_LOG.txt` records the 29 tests and
the `--summarize` rebuilds run on the archive itself.

```bash
.venv/bin/python fair_signalling_test.py        # §5.1-5.2 headline, ~1 h
.venv/bin/python dominance_check.py             # §5.3, ~1 h
.venv/bin/python rolling_hesitation_test.py     # §5.4, ~3 h
.venv/bin/python stop_penalty_check.py          # §5.5, ~1 h
.venv/bin/python awsc_calibration.py            # §5.6, seconds
.venv/bin/python moveup_sensitivity.py          # §5.6, ~1 min
.venv/bin/python roundabout_rerun.py            # §5.7, ~40 min (uses fair_signalling_test.csv)
.venv/bin/python roundabout_calibration.py      # §5.6, ~1 min
.venv/bin/python heading_error_check.py         # §5.6, seconds
.venv/bin/python checker_validation.py          # legacy reproduction + checker, ~45 min
.venv/bin/python awsc_rebaseline.py             # stop sign 400-1,200, ~1 min
# the six long runners also accept --summarize to rebuild the .txt from the .csv
```

**Tests (29):**
- `test_independent_checker.py`
- `test_awsc_fcfs.py`
- `test_blind_no_truth.py`
- `test_stop_penalty.py`
- `test_rolling_hesitation.py`

Run each with `.venv/bin/python <file>`.
