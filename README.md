# Smart Stop

**An all-way stop sign plus a camera and a green flash for each approach:
a simulation study.**

At an all-way stop every car stops, and drivers take turns. Smart Stop keeps
the stop sign and adds a camera and a green flash for each approach. The
flash tells a driver they may go:
- a car flashed as it reaches the line may roll through without stopping;
- cars whose paths don't cross are flashed together.

If the system is off, the intersection is an ordinary all-way stop.

> **Status (November 2026): a simulation study.** All results come from a
> simulated isolated, single-lane, four-way intersection. They are relative
> to *modelled* alternatives, not field measurements. Real-world safety,
> legality, driver response and cost are **not** established.

**Start here**
- [`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md): the study, about 10 pages.
- [`CLAIMS.md`](CLAIMS.md): the only claims to quote, with their conditions.
- [`FINAL_AUDIT.md`](FINAL_AUDIT.md): the model, the full results, the
  limitations, and four rounds of external audit.

---

## Two designs

| design | what it uses | trade-off |
|---|---|---|
| **Blind** | Camera-visible motion only. Every car is "could be turning any way" until it has moved 4 m | Its decisions don't depend on anyone signalling honestly |
| **Signal-reading** | Believes turn signals, as human drivers at a stop sign do | Faster; exposed to false signals, like a stop sign |

Neither design needs any communication from vehicles.

## Results

Mean delay per car in seconds, balanced traffic. The scenario assumes 25%
of drivers don't signal and none signal falsely. Ten matched seeds, with
paired 95% intervals.

| | 600 veh/h | 800 veh/h |
|---|---|---|
| All-way stop (modelled) | 7.4 | 13.3 |
| Smart Stop, blind | 4.4 | 8.8 |
| Smart Stop, signal-reading | 2.6 | 4.4 |
| Mini-roundabout | **2.2** | **3.0** |

- **Against the all-way stop:** the signal-reading design has about a third
  of the delay. The blind design keeps 40–65% of that improvement. Every
  difference is resolved.
  - Caveat: the modelled stop sign is 12–66% slower than the Highway Capacity
    Manual near saturation. That can exaggerate the gain at 800 veh/h.
- **A mini-roundabout is the best performer.**
  - At 600 veh/h the signal-reading design is close: within 0.4 s, and
    statistically indistinguishable on two of three traffic patterns.
  - At 800 veh/h it is 23–47% behind.
  - Smart Stop's case is intersections that won't be rebuilt.
- **Information is the limit.** Ignoring turn signals gives up most of the
  benefit of releasing cars together.
- **The gain depends on drivers trusting the flash.** Half a second of
  hesitation removes the blind design's edge except in light traffic.
- **False signals.** In a stress test, 2% of drivers (279) signal one way
  and turn another. Raw contact counts: all-way stop 61, signal-reading 47,
  blind 0. These counts are descriptive only, because no evasive braking is
  modelled.

## How it was checked

- **Four rounds of external audit.** Corrections and retracted claims are
  kept on the record: `FINAL_AUDIT.md` §3 and §7, and `CLAIMS_ARCHIVE.md`.
  The earliest headline, "~4× capacity", did not survive.
- **An independent collision checker** that shares no code with any
  controller.
- **Symmetric information.** The stop sign's drivers and Smart Stop face the
  same arrivals and the same signalling behaviour.
- **29 tests.** [`VERIFY_LOG.txt`](VERIFY_LOG.txt) records them passing, and
  the six main summaries rebuilding identically from the saved results.

## Reproduce

Python 3.13 and numpy. `requirements-lock.txt` pins the exact environment.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
```

```bash
.venv/bin/python test_independent_checker.py
```

The other four test files run the same way:
- `test_awsc_fcfs.py`
- `test_blind_no_truth.py`
- `test_stop_penalty.py`
- `test_rolling_hesitation.py`

Full experiments, which are long (hours):

| results | command |
|---|---|
| Headline vs the all-way stop; false signals | `python fair_signalling_test.py` |
| Mini-roundabout | `python roundabout_rerun.py` (needs `fair_signalling_test.csv`) |
| Where the gain comes from | `python dominance_check.py` |
| Rolling × hesitation; actuated signal | `python rolling_hesitation_test.py` |
| Calibration and sensitivity | `awsc_calibration.py`, `roundabout_calibration.py`, `stop_penalty_check.py`, `moveup_sensitivity.py` |
| Compute timing | `python compute_timing.py` |

The long runners take `--summarize`, which rebuilds the `.txt` summary from
the saved `.csv` in seconds.

## Repository map

| file | what it is |
|---|---|
| `blind_safe_v2.py` | Smart Stop controller (blind design) |
| `fair_signalling_test.py` | The signal-reading design and the signal-aware stop sign, plus the headline experiment |
| `cs4_human_baseline.py` | The all-way stop (first come, first served) |
| `obb_survival_gate.py`, `roundabout_entry.py` | The mini-roundabout and the footprint checks |
| `stopsign_vs_signal.py` | The actuated signal |
| `independent_checker.py` | The independent collision checker |
| `capacity_curves.py` | Arrival streams, simulation harness and delay metric |
| `path_based_smart_stop.py`, `block2_platoon.py`, `block3_reality.py` | Geometry, vehicle model, platoons, rolling launches |

Other scripts and result files are earlier experiments, kept for the
record. Where they disagree with `CLAIMS.md`, they are superseded.

`app.py` is an interactive Streamlit demo built for earlier versions of the
model (`requirements.txt`).

## About this repository

This is a curated snapshot of a private development repository. Session
notes, run logs, media and superseded documents are left out. The audit
record above documents every change of conclusion.

The code, analyses and report were developed with AI assistance (Anthropic's
Claude), directed and reviewed by the author.

Copyright © 2026 Patrick Tyler. All rights reserved; published for review
and reproduction. See [`LICENSE`](LICENSE).
