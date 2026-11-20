# Smart Stop: Releasing Non-Conflicting Cars at an All-Way Stop

### A simulation study of a camera-and-flash controller for drivers whose intent is unknown

**Technical report — version 0.1 (draft for review) — 15 November 2026**

**Author:** [Author name]. Prepared in a personal capacity.

> **Status.** Every result here comes from simulation. The results are
> relative to *modelled* comparators, not to field measurements. Nothing
> here establishes real-world safety, legality, deployability or cost.
>
> The supporting code, results and tests are in this repository.

---

## Abstract

The all-way stop is cheap and common. But it makes every driver stop and
serves conflicting movements one at a time, so delay rises steeply with
traffic.

*Smart Stop* keeps the stop sign and adds a camera and a green flash for each
approach. The flash tells a driver they may go:
- a car that is flashed as it arrives may roll through without stopping;
- cars whose paths do not conflict are released together.

The controller is designed for drivers whose intentions are unknown. It needs
no communication from vehicles. In its *blind* form it ignores turn signals
entirely: every car is treated as possibly turning any way until its first
4 m of motion show which way it is going.

We compared two designs, blind and *signal-reading*, with three alternatives
in a simulation of one isolated single-lane intersection:
- a modelled all-way stop;
- a mini-roundabout;
- an actuated signal.

Differences are paired 95% intervals on matched arrival streams, and an
independent collision checker monitored every run.

**Delay.** We assumed 25% of drivers do not signal and none signal falsely.
On that assumption, at 600–800 veh/h:
- The signal-reading design had about a third of the modelled all-way stop's
  mean delay: 2.6 vs 7.4 s per car at 600 veh/h, and 4.4 vs 13.3 s at 800.
- The blind design gave 40–65% of that improvement: 4.4 and 8.8 s.
- A mini-roundabout had the lowest delay, at 2.2–3.6 s.

**False signals.** In a stress scenario where 2% of drivers signal falsely,
the raw contact counts were:

| controller | contacts |
|---|---|
| Stop sign | 61 |
| Signal-reading Smart Stop | 47 |
| Blind Smart Stop | 0 |

**Hesitation.** The gains depend on drivers acting promptly on the flash.
Half a second of hesitation removes the blind design's advantage except in
light traffic.

We report the study's audit history, including retracted claims. We also
propose field-data validation.

---

## 1. Introduction

### 1.1 The problem

At an all-way stop every car stops, and drivers take turns. The rule needs no
power, no detection and no maintenance beyond the signs. That makes it the
default control for low- and moderate-volume intersections.

Its costs grow with traffic:
- every car pays the time to brake and pull away again, even when the box is
  empty;
- conflicting movements are served largely one at a time, so queues build
  quickly as volume rises.

The usual upgrades are a roundabout or a traffic signal. A roundabout means
reconstructing the intersection. A signal is expensive, and in this model it
performed worse than the stop sign at most of the volumes studied (§5.6).

### 1.2 The idea

Smart Stop leaves the stop sign in place and adds a camera and a green flash
for each approach. The controller watches the intersection and flashes an
approach when its car can go without conflicting with anyone already moving.
Two things follow:
- **Rolling.** A car that is flashed as it reaches the line need not stop.
- **Multi-car release.** Cars whose paths do not conflict are flashed
  together: for example, two opposing straight-through cars, or a right turn
  alongside a crossing movement.

If the camera or controller fails, no flash is shown and the intersection is
an ordinary all-way stop. This is a design intent, not something modelled.

The code and earlier project documents call the controller "Smart Safe".

### 1.3 The question that turned out to matter

To release cars together, the controller has to know where they are going.
Human drivers at a stop sign infer this from turn signals, which are often
missing and occasionally wrong.

We evaluate two answers to that question:

| design | what it uses | consequence |
|---|---|---|
| **Blind** | Camera-observable motion only. Every car is "could be any movement" until it has moved 4 m | Its decisions do not depend on anyone signalling honestly |
| **Signal-reading** | Believes turn signals, as human drivers do. A car that doesn't signal is treated as "any movement" until 4 m | More efficient; exposed to false signals, like a stop sign |

### 1.4 Contributions

1. **A controller design for permission at a stop sign under uncertain human
   intent.** It needs no communication from vehicles and no declared route.
   In its blind form, its decisions do not rely on drivers' signals.
2. **A comparison under symmetric information** against the modelled
   all-way stop, a mini-roundabout and an actuated signal. Its drivers and
   both Smart Stop designs face identical arrival streams and identical
   signalling behaviour.
3. **A diagnosis:** information, not the controller's release capacity, is
   what limits the blind design (§5.3).
4. **An audited, reproducible process:**
   - four external audits, with every finding and response recorded;
   - an independent collision checker;
   - 29 tests;
   - a published repository with a verification log;
   - corrections and retractions reported, not hidden (§8).

---

## 2. Design principles

### 2.1 Intent is unknown at the start

Each arriving car is treated as possibly turning left, going straight or
turning right. The controller holds all three possibilities until the car's
own motion rules out the others, which happens after 4 m of movement (the
parameter `REVEAL_M`).

A release is granted only if the car's predicted footprint stays clear under
every remaining possibility:
- the check uses oriented boxes with a 1.0 m clearance buffer;
- it covers three hypotheses about how long the driver takes to launch:
  0, 1.2 and 2.5 s;
- it allows for rolling and full-stop starts.

The cost of not knowing is measured directly in §5.3. The main lever for
recovering it is how early real first movements reveal a turn, which is
untested (§9).

### 2.2 Local decisions, no communication

The controller decides using only the vehicles near its own intersection, as
seen by its camera:
- no vehicle-to-infrastructure messaging;
- no routes or destinations;
- no coordination with other intersections.

That makes its workload a property of one intersection rather than of a
fleet or a network. This is a structural property; we did not test scaling.

### 2.3 Human in the loop

The flash grants permission. It never takes control.

Each driver still decides whether and when to go, and can decline. The design
deliberately does not require drivers to declare anything or to behave
honestly.

Two consequences, both measured:
- the delay benefit depends on drivers trusting the flash (§5.4);
- the blind design's decisions must remain safe when drivers deviate (§5.5).

---

## 3. Related work

**Reservation-based intersection management.** Dresner and Stone's
Autonomous Intersection Management (AIM) [1] has each vehicle:
- request a reservation by transmitting its arrival time, speed and intended
  path;
- follow the trajectory it is granted.

Human-driven vehicles are accommodated through conventional light phases
rather than individual reservations. Smart Stop addresses the case AIM
leaves to signals: vehicles that cannot or will not communicate.

**Multi-agent path finding and robot fleet management.** These plan whole
routes for agents whose goals are known and who report their state, for
example:
- MAPF benchmarks such as the League of Robot Runners [2];
- the VDA 5050 fleet-control interface [3];
- Open-RMF [4].

They solve a different problem: cooperative agents with declared goals.

**Conventional control.** All-way stops, roundabouts and signals are
characterised in the Highway Capacity Manual (HCM) [5]. We use the HCM to
sanity-check both comparators (§5.7).

**Intent from early motion.** Predicting a vehicle's manoeuvre from its early
trajectory is an active research area in automated driving. We have not yet
surveyed it systematically, and we make no claim of novelty for reading
intent from motion.

**Regulation.** A flashing green is not a standard indication in the
*Manual on Uniform Traffic Control Devices*. Using it on public roads would
need FHWA approval to experiment [6].

---

## 4. Simulation model

### 4.1 World

**Intersection**
- One isolated four-way intersection, one lane per approach.
- The box is ±6.1 m.
- No pedestrians, cyclists or heavy vehicles.

**Cars**
- 4.5 × 2.0 m.
- Launch acceleration 1.5 m/s²; cruise 6 m/s (13 mph).
- Speed caps in the box: straight 6.0, left 4.4, right 3.2 m/s.

**Driver timing**
- Reaction delay U(0.5, 2.0) s for every car starting from rest.
- Platoon followers are capped at 0.6 s.

**Arrivals**
- Poisson.
- Turning mix: 15% left, 70% straight, 15% right.
- Splits:
  - *balanced*: equal on all four approaches;
  - *arterial*: 40/40/10/10;
  - *dominant*: 55/15/15/15.
- 120 s warm-up, 480 s measured, up to 300 s drain.
- The same arrival stream (seed) is used for every controller.

**Rolling.** A car flashed within 0.3 s of reaching the line enters at its
speed cap.

### 4.2 Controllers

| controller | rules |
|---|---|
| **Smart Stop, blind** | As in §2.1. Platoons of up to 4 cars per flash, grouped by lane. No priority by movement |
| **Smart Stop, signal-reading** | As blind, but a signalling car is predicted on its declared movement, and priority and grouping use declared movements |
| **All-way stop** | First come, first served; simultaneous arrivals yield to the right. The car whose turn it is goes once every moving car has cleared its conflict area (a precomputed corridor with a 0.5 m margin). Other cars may go out of turn only if their movement conflicts with no moving car |
| **All-way stop, signal-aware drivers** | As above, but each driver knows only their own movement. Others' movements come from turn signals or, after 4 m, from motion. This is the comparator in all headline results |
| **Mini-roundabout** | Ring radius 6.75 m; ring speed 4.1 m/s. Gap acceptance: 4.5 s critical gap, 2.8 s follow-up. Rolling entry when clear; 1.5 m yield setback; footprint entry check. Needs no turn signals |
| **Actuated signal** (secondary) | Two phases. Green 8–40 s, 3 s passage, 3.5 s yellow, 1.5 s all-red. Permitted lefts |

### 4.3 Information regimes

Each driver's signalling behaviour is fixed by arrival number and seed, so
every controller faces identical drivers.

| regime | non-signallers | false signallers |
|---|---|---|
| Perfect | 0% | 0% |
| **25% non-signalling, no deception** (headline) | 25% | 0% |
| False-signal stress | 25% | 2% |

- The 25% non-signalling share comes from a 12,000-vehicle field study of
  turn-signal use [7].
- The 2% false-signal rate is an assumption, not field data. A false
  signaller signals right (or straight, if actually turning right) and goes
  another way.

### 4.4 Delay metric

Delay is time from arrival to leaving the box, minus the time an unimpeded
car would take crossing the line at its speed cap.

A car that stops also pays its braking loss, v / (2 × 3 m/s²). At the
model's speeds a stop therefore costs 1.6–3.0 s, against the HCM's ≈5 s. A
sensitivity run that charges the HCM's 5 s per stop is reported in §5.6.

### 4.5 Safety measurement

An independent checker, sharing no code with any controller's decision logic:
- tracks every pair of moving cars, and each moving car against the first
  car waiting at each stop line;
- uses exact footprint polygons;
- certifies contact between time steps, using a Lipschitz bound with
  bisection.

Some same-lane "contacts" are artefacts of the queue model: a car pulling
away and the queued car behind it. These are reported separately and not
counted.

The 1.0 m clearance buffer is a *decision* parameter. It is not a guaranteed
separation: realised closest approaches were 0.21–1.24 m, depending on the
controller (§5.5).

### 4.6 Statistics

All comparisons are paired differences on matched seeds, with 95%
t-intervals. Seeds per cell:
- 10 for the headline, roundabout and hesitation results;
- 5 for diagnostics.

A difference is "resolved" when its interval excludes zero.

---

## 5. Results

### 5.1 Against the all-way stop

25% non-signalling, no deception, 10 seeds. Mean delay per car in seconds,
with the share of cars that stopped in brackets.

| | 600 veh/h balanced | 600 arterial | 800 balanced | 800 arterial |
|---|---|---|---|---|
| All-way stop | 7.4 [100%] | 7.2 [100%] | 13.3 [100%] | 13.3 [100%] |
| Smart Stop, blind | 4.4 [53%] | 4.4 [51%] | 8.8 [73%] | 9.8 [72%] |
| Smart Stop, signal-reading | **2.6** [37%] | **2.5** [34%] | **4.4** [48%] | **4.4** [48%] |

Paired differences against the all-way stop, in seconds. Every difference is
resolved.

| | 600 balanced | 600 arterial | 800 balanced | 800 arterial |
|---|---|---|---|---|
| Signal-reading | −4.8 [−5.2, −4.4] | −4.7 [−5.1, −4.4] | −9.0 [−11.6, −6.4] | −8.9 [−10.6, −7.1] |
| Blind | −3.1 [−3.5, −2.7] | −2.9 [−3.3, −2.5] | −4.6 [−6.4, −2.7] | −3.5 [−5.1, −1.9] |

**Caveat.** The modelled all-way stop is slower than the HCM near saturation
(§5.7). That can exaggerate the gain, most at 800 veh/h, which is why
headline results stop at 800. At 1,000 veh/h every difference is also
resolved, but variance is large, so we do not quote it.

**Non-signalling hurts both sides.** Compared with perfect signals, 25%
non-signalling cost:
- signal-reading Smart Stop 0.5–2.5 s per car;
- the all-way stop 0.2–6.6 s per car, rising with volume, because human
  drivers must also wait out cars whose intent they cannot see.

### 5.2 Against a mini-roundabout

25% non-signalling, no deception, 10 seeds. Mean delay per car in seconds.

| split | veh/h | all-way stop | blind | signal-reading | roundabout |
|---|---|---|---|---|---|
| balanced | 600 | 7.4 | 4.4 | 2.6 | **2.2** |
| | 800 | 13.3 | 8.8 | 4.4 | **3.0** |
| arterial | 600 | 7.2 | 4.4 | 2.5 | **2.4** |
| | 800 | 13.3 | 9.8 | 4.4 | **3.6** |
| dominant | 600 | 7.6 | 3.6 | 2.4 | **2.3** |
| | 800 | 13.9 | 8.9 | 4.8 | **3.3** |

**The roundabout is the best performer.** Against it:
- **Signal-reading Smart Stop:**
  - at 600 veh/h: +0.4 s on balanced traffic (resolved), and +0.1 s on
    arterial and dominant (unresolved);
  - at 800 veh/h: +0.8 to +1.6 s, all resolved. That is 23–47% higher mean
    delay: small in seconds, large in relative terms.
- **Blind Smart Stop:** 1.3–2.1 s behind at 600 veh/h and 5.6–6.2 s behind at
  800.

The roundabout model is pessimistic at heavy circulating flow (§5.7), so it
if anything flatters Smart Stop.

### 5.3 Where the gain comes from

Two sources:
1. **Rolling:** flashed cars don't stop.
2. **Multi-car release:** non-conflicting cars go together. This needs to
   know where cars are going.

A diagnostic with perfect signals and 5 seeds tested each suspect:

| suspect | effect |
|---|---|
| A cap of 4 active cars on the controller | Never blocked a release |
| Giving the blind design the same turn-signal knowledge as the stop sign's drivers | Delay fell by 2 s at 600 veh/h, 5–7.5 s at 800 and 12–15 s at 1,000 |

With that knowledge, Smart Stop beat the all-way stop even with full stops
and no rolling. Multi-car release alone wins.

**Ignoring turn signals gives up most of the release gain.** Information, not
release capacity, limits the blind design.

### 5.4 Driver hesitation at the flash

Blind design, 10 seeds, against the all-way stop with perfect signals.
Seconds saved per car, balanced / arterial:

| hesitation | 400 veh/h | 600 veh/h | 800 veh/h |
|---|---|---|---|
| none | 3.1 / 3.6 | 2.9 / 2.6 | 3.1 / 2.1 |
| 0.5 s | 2.2 / 2.5 | 1.0 / tie | tie / −5.3 |
| 1.0 s | 1.0 / tie | −1.7 / −2.5 | −10 / −16 |

Notes:
- In the blind design, full stops never beat the all-way stop. Rolling is
  essential to it.
- Widening the controller's launch-delay hypotheses to cover hesitation
  changed no decision in any of the 720 runs. Hesitation costs only the time
  itself and the lost roll.
- Hesitant rollers are modelled as crossing the line late but still at
  speed.
- We have not tested hesitation for the signal-reading design.

**The benefit depends on drivers trusting the flash.** That is a
human-factors question the simulation cannot answer.

### 5.5 Contacts and false signals

**Honest drivers.** The independent checker flagged no footprint overlaps in
1,736 model executions. Many share scenarios and seeds, so these are not
independent trials, and no failure-rate bound follows.

Realised closest approaches between moving cars:

| controller | closest approach |
|---|---|
| Roundabout | 0.21 m |
| All-way stop | 0.57 m |
| Signal-reading Smart Stop | 0.58 m |
| Blind Smart Stop | 1.24 m |

**False-signal stress scenario.** 279 lying drivers, identical for every
controller, across 60 paired runs. Every contact involved a liar.

| controller | contacts (raw count) |
|---|---|
| All-way stop | 61 |
| Signal-reading Smart Stop | 47 |
| Blind Smart Stop | 0 |

Run by run, signal-reading Smart Stop had fewer contacts than the all-way
stop in 17 runs, more in 9, and the same number in 34.

These counts are descriptive. No evasive braking is modelled, and the
scenarios are not representative crash exposure. No relative risk or crash
rate can be inferred.

What the counts do show: the blind design's decisions do not depend on
signal honesty. Both signal-dependent controllers, including the human stop
sign, are exposed to false signals.

### 5.6 Against an actuated signal (secondary comparator)

In this model the all-way stop itself beats the actuated signal at:
- 400–800 veh/h on balanced traffic;
- 600 veh/h on arterial traffic.

That is the textbook result at these volumes. The signal wins at 800 veh/h
arterial and at 1,200 veh/h.

The blind, rolling design beat the signal at 400–800 veh/h, except at
800 arterial, where the difference was unresolved. We did not run the
signal-reading design against the signal.

### 5.7 Calibration and sensitivity

**All-way stop vs HCM.** Saturation departure headways, in seconds, by HCM
case:

| HCM case | HCM | model |
|---|---|---|
| 1 | 3.84 | 4.30 |
| 2 | 4.64 | 5.90 |
| 3 | 5.74 | 9.50 |
| 5 | 9.54 | 13.56 |

The model is 12–66% slower, because of the slow launch dynamics shared by
every controller.

We did not retune those dynamics, because doing so would move every
controller. Faster launches (2.5 m/s², no reaction delay) match case 3 but
make case 1 too fast.

**Roundabout vs HCM entry capacity.** Simulated entry capacity (veh/h)
against circulating flow v_c, compared with two HCM-style curves:

| v_c | model | HCM 2010 (1130·e^−0.0010 v_c) | HCM 6 (1380·e^−0.00102 v_c) |
|---|---|---|---|
| 0 | 1,196 | 1,130 | 1,380 |
| 252 | 949 | 878 | 1,067 |
| 520 | 634 | 672 | 812 |
| 880 | 270 | 469 | 563 |

Against both curves, the model is:
- within about 10% up to ~250 veh/h circulating;
- 6–22% below at ~520;
- 42–52% below at ~880.

This is a sanity check, not a validation.

**Charging stops at the HCM's 5 s** instead of the model's 1.6–3.0 s
increases rolling's value: roughly −4 to −5 s per car against the all-way
stop, instead of −3 to −3.7 s (earlier controller versions).

**Queue move-up time.** Setting the all-way stop's queue move-up time to zero
improves it by at most 1.0 s. Every Smart Stop win at 600–800 veh/h holds.

### 5.8 Compute

Time per 0.1 s controller step, 800 veh/h balanced, 3 seeds. Plain,
unoptimised Python on a laptop (Apple silicon). The steps include the
model's vehicle physics and bookkeeping, and exclude camera processing.

| | median | slowest 1% | slowest step |
|---|---|---|---|
| Blind | 0.1–0.4 ms | 15–50 ms | 32–158 ms |
| Signal-reading | 0.1–0.4 ms | 6–24 ms | 19–99 ms |

Ranges are across three runs under different machine load: two measured
wall-clock time, one CPU time. The latest (CPU-time) run is in
`compute_timing.txt`.

The typical step is far inside the 100 ms real-time budget. The slowest steps
are not: in unoptimised Python they can approach or exceed it.

A deployed controller would need an optimised implementation and a measured
worst-case bound. Compute is therefore not where Smart Stop differs from
other single-intersection controllers. What distinguishes it is needing no
communication (§2.2).

---

## 6. Discussion

**Where Smart Stop fits.** Where a mini-roundabout can be built, the model
says it is the better performer on delay. Smart Stop's case is the
intersection where reconstruction is not feasible or not worth it, and the
stop sign stays.

Smart Stop is *intended* to avoid roadway reconstruction. We have not
evaluated:
- installation, power, sight lines and maintenance;
- regulatory approval;
- cost.

**The design choice is a trade-off.**
- The blind design gives up 35–60% of the signal-reading design's
  improvement over the stop sign.
- In return, its decisions do not depend on anyone signalling honestly.

The lever that could recover much of the gap without trusting signals is
reading intent earlier from motion: at 1–2 m instead of 4 m, with realistic
camera errors and latency. This is untested.

**Beyond road intersections (untested).** The same properties suit crossings
on private industrial sites where human-driven forklifts, pedestrians and
robots meet:
- no communication needed;
- decisions that don't rely on declared intent;
- permission rather than control.

Robots there can report their paths; people can't. A controller could trust
declared intent only where a machine can verify it, and read motion
elsewhere. We have not modelled this.

---

## 7. Limitations

| limitation | effect on the comparison |
|---|---|
| The all-way-stop model is 12–66% slower than the HCM near saturation | Flatters Smart Stop at 800+ veh/h; headline stops at 800 |
| Shared slow dynamics: a stop costs 1.6–3.0 s vs the HCM's ≈5 s | Understates the value of not stopping |
| Intent read perfectly once a car has moved 4 m; no camera errors, latency or occlusion; `REVEAL_M` not swept | Flatters both Smart Stop designs |
| Uniform hesitation, no learning; hesitant rollers cross late at speed | Arguable either way |
| No evasive braking | Contact counts overstate crashes; only the comparisons carry weight |
| The stop sign's drivers know the conflict geometry perfectly (0.5 m margin) | Flatters the all-way stop |
| Hesitation not tested for the signal-reading design | Unknown |
| One isolated single-lane intersection; one mini-roundabout geometry; no pedestrians, cyclists or heavy vehicles | Untested; pedestrians are the largest gap for urban sites |
| Roundabout entry capacity 42–52% below HCM-style curves at heavy circulating flow | Flatters Smart Stop above 800 veh/h |
| The 1.0 m buffer is not a realised separation | No physical margin can be claimed |
| 10 seeds; 480 s measurement window | Wide intervals at 1,000 veh/h |
| Legality of rolling on a flash; driver adaptation; vulnerable road users; cost | Not modelled; not established |

---

## 8. How the conclusions changed

The study was audited four times by external reviewers. The conclusions
moved substantially, and the record is kept in full (`FINAL_AUDIT.md`,
`CLAIMS_ARCHIVE.md`).

**Original claim (July 2026): "~4× capacity vs an all-way stop."**
Superseded. It predates:
- the footprint-based safety standard;
- the removal of an "oracle" information leak;
- the rebuilt all-way stop.

**Audit 0 (September).** A centre-distance safety metric had hidden footprint
overlaps. We replaced it with oriented-box checks, and corrected the
roundabout benchmark.

**3 October.**
- "3–10× better than a signal" was retracted the same day: the controller had
  been reading cars' true paths.
- The subsequent verdict ("commercially doubtful") was withdrawn on
  9 November as overstated.

**Audits 1–2 (9 November).** The headline was overstated, the hesitation
analysis confounded three factors, and the statistics were thin. We
corrected all of this.

**Audit 3 (11 November, code-level).**
- The legacy all-way stop was badly mis-specified. At 600 veh/h it gave
  17.1 s, where the rebuilt model gives 4.5 s on the same old metric.
- We fixed the safety observer, the predicted headings, and three further
  information leaks and prediction errors in the blind controller.
- We briefly concluded that Smart Stop only tied a stop sign.

**12 November.** That tie was traced to an unfair comparison: a blind
controller against human drivers who could read honest signals. The
symmetric-information test (§5.1) replaced it.

**15 November.**
- We found and fixed a roundabout entry defect (4 contacts in 90 runs).
- Rerun under the same standards as the other controllers, the roundabout
  is the strongest comparator.
- **Audit 4** judged the study a conditional go as a clearly labelled
  simulation study, and a no-go for engineering, physical-safety or
  commercial claims. It found no modelling bugs. Its wording corrections are
  applied here.

---

## 9. Proposed further work

Each item addresses a limitation in §7.

1. **Calibrate the comparators against field data.**
   - Fit the all-way stop's headways, service times and rolling-stop rates
     against observed US all-way stops.
   - Fit the roundabout's critical gap and follow-up headway against observed
     roundabouts.
   - Candidate data:
     - INTERACTION (US all-way stops; licensed);
     - rounD (licensed);
     - the Swiss roundabouts drone dataset (open, CC BY 4.0) [8].
2. **Measure how early first motion reveals a turn.** On real trajectories,
   find the distance after pulling away from the stop line at which left,
   straight and right become reliably distinguishable, then rerun the blind
   design at that distance.
   - Candidate data: FHWA TGSIM Foggy Bottom, which has stop-controlled and
     signalised intersections in Washington, DC, and is open [9];
     INTERACTION.
3. **Model camera reading with misclassification and latency.**
4. **Driver response to the flash.** Measure hesitation and compliance in a
   driving simulator or on a closed course, for both designs.
5. **Pedestrians and cyclists.**
6. **Economics.**
   - Installed cost, against time, fuel and emissions saved.
   - Against the construction cost of a mini-roundabout.
7. **A regulatory pathway.** Requirements for an FHWA request to experiment
   with a flashing-green permission indication.
8. **Optional: mixed human/robot industrial crossings** (§6).

---

## 10. Reproducibility

This repository contains:
- the source;
- the result files (`.csv`, `.txt`);
- `requirements-lock.txt`, the pinned environment;
- `VERIFY_LOG.txt`, which records all 29 tests passing and the six long
  runs' summaries rebuilt identically from their saved results.

The only package the simulation needs is numpy (Python 3.13).

| section | command |
|---|---|
| §5.1, §5.5 | `python fair_signalling_test.py` (~1 h) |
| §5.2 | `python roundabout_rerun.py` (~40 min) |
| §5.3 | `python dominance_check.py` (~1 h) |
| §5.4, §5.6 | `python rolling_hesitation_test.py` (~3 h) |
| §5.7 | `awsc_calibration.py`, `roundabout_calibration.py`, `stop_penalty_check.py`, `moveup_sensitivity.py` |
| §5.8 | `python compute_timing.py` |

The audit trail is in `FINAL_AUDIT.md`, and current claims in `CLAIMS.md`.

**Use of AI.** The simulation code, the analyses and this report were
developed with AI assistance (Anthropic's Claude), directed and reviewed by
the author. Audit 0 was performed by Google's Gemini. The findings of
audits 1–4 and the responses to them are recorded in `FINAL_AUDIT.md` §8;
the audit-4 report is in `audits/`.

---

## References

1. K. Dresner and P. Stone. "A multiagent approach to autonomous
   intersection management." *Journal of Artificial Intelligence Research*
   31 (2008): 591–656.
2. S.-H. Chan et al. "The League of Robot Runners: competition goals, designs,
   and implementation." arXiv:2404.16162 (2024).
3. VDA 5050: interface for communication between automated guided vehicles
   and a master control. Verband der Automobilindustrie (VDA).
4. Open-RMF (Robotics Middleware Framework). open-rmf.org.
5. Transportation Research Board. *Highway Capacity Manual, 6th Edition: A
   Guide for Multimodal Mobility Analysis.* 2016. All-way-stop and roundabout
   chapters.
6. FHWA. *Manual on Uniform Traffic Control Devices*, 11th Edition (2023),
   Revision 1 (December 2025; effective 5 March 2026).
7. R. Ponziani. "Turn signal usage rate results: a comprehensive field study
   of 12,000 observed turning vehicles." SAE Technical Paper 2012-01-0261
   (2012).
8. Vehicle trajectory dataset from drone-collected data at three Swiss
   roundabouts. EPFL LUTS. Zenodo, doi:10.5281/zenodo.15077435 (2025).
9. FHWA. Third Generation Simulation Data (TGSIM): Foggy Bottom trajectories.
   data.transportation.gov (2024).
