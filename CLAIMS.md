# Smart Stop — Current Claims

**Updated 2026-11-15** (after audit 4). These are the only claims to quote.
Evidence, conditions and history: `FINAL_AUDIT.md`. Withdrawn claims and the
old ledger: `CLAIMS_ARCHIVE.md`.

**Conditions on every claim:** a simulation of one isolated, single-lane
4-way intersection, with:
- no pedestrians, cyclists or heavy vehicles;
- no camera errors;
- no evasive braking;
- delay measured with every stop charged;
- paired 95% intervals on matched seeds;
- results relative to the **modeled** comparators, not to field
  measurements.

## Quotable

1. **Against the modeled all-way stop, under a 25% non-signalling,
   no-deception scenario, Smart Stop cut mean delay at 600–800 veh/h.**
   - Signal-reading design: 2.6 vs 7.4 s per car at 600 veh/h; 4.4 vs
     13.3 s at 800 (balanced). About 3x lower.
   - Blind design (never reads turn signals): 4.4 and 8.8 s.
   - All resolved.
   - Caveat: the modeled stop sign is 12–66% slower than HCM at saturation,
     which can exaggerate the gain, most at 800 veh/h.
   - Source: `fair_signalling_test.txt`.
2. **A mini-roundabout did better still.**
   - It averaged 2.2–3.6 s per car at 600–800 veh/h on balanced, arterial
     and dominant traffic.
   - Signal-reading Smart Stop was nearly indistinguishable from it at
     600 veh/h on arterial and dominant traffic (+0.1 s, unresolved) and
     0.4 s behind on balanced.
   - At 800 veh/h its mean delay was 23–47% higher than the roundabout's
     (+0.8 to +1.6 s, resolved).
   - The blind design was 1.3–6.2 s behind the roundabout.
   - The roundabout was sanity-checked against two HCM-style entry-capacity
     curves; it is pessimistic at heavy circulating flow.
   - Sources: `roundabout_rerun.txt`, `roundabout_calibration.txt`.
3. **Where the gain over the stop sign comes from:**
   - cars flashed on arrival don't have to stop;
   - non-conflicting cars are released together.

   The second needs to know where cars are going: ignoring turn signals gives
   up most of it (`dominance_check.txt`).
4. **The gain depends on drivers trusting the flash.** With 0.5 s of
   hesitation the blind design keeps its edge over the stop sign only in
   light traffic (400 veh/h; 600 balanced); with 1 s, only at 400
   (`rolling_hesitation_test.txt`). Not tested for the signal-reading design.
5. **Observed contacts.**
   - The independent checker flagged 0 footprint overlaps in 1,736 model
     executions under honest-driver assumptions. Many share scenarios and
     seeds, so these are not independent trials and give no failure-rate
     bound.
   - In a 2% false-signal stress scenario (279 lying drivers) the raw
     contact counts were: stop sign 61, signal-reading 47, blind 0.
   - These are descriptive only: no relative risk or crash rate can be
     inferred.
   - The 1.0 m clearance buffer is a decision parameter, not a guaranteed
     separation. Realized closest approaches were 0.21–1.24 m by controller.

## Not claimed / not established

- **Safety:** real-world collision-freedom, or any safety advantage.
- **Deployment:**
  - that it needs no civil works: it is *intended* to avoid roadway
    reconstruction, but installation, power, sight lines and maintenance
    are not evaluated;
  - regulatory approval: a flashing green is not a standard MUTCD
    indication, and use needs FHWA experimentation (MUTCD 11th Ed., Rev. 1);
  - that rolling through on a flash would be legal.
- **Behaviour and other road users:** driver adaptation to a novel
  indication; pedestrians and other vulnerable road users.
- **Money:** costs, and commercial viability.
- **Other sites:** any result above 800 veh/h as a headline; multi-lane
  sites; other roundabout geometries.
