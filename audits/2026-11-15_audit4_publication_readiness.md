# Smart Stop — Independent Publication-Readiness Audit
**Date:** 2026-11-15  
**Scope:** Current uploads (`CLAIMS.md`, `FINAL_AUDIT.md`, `FALSIFICATION_PLAN.md`, `moveup_sensitivity.py/.txt`, `obb_survival_gate.py`, `roundabout_calibration.py/.txt`, `roundabout_entry.py`, `roundabout_rerun.py/.csv/.txt/.log`). A separate ZIP dated 2026-11-09 was available from an earlier conversation but is **not** the current revision.  
**Posture:** Adversarial; publication readiness, not performance optimization.

## Executive decision
**Conditional GO for publication as a clearly labeled simulation study after documentation corrections and supplying a frozen matching source/data archive; NO-GO for a validated engineering-design, physical safety, or commercial-performance claim.** The new results are credible as *reported model outputs*, but most of the current core implementation cannot be independently inspected from this update. The strongest defensible result is the modeled reduction in control delay vs this particular all-way-stop implementation at 600–800 veh/h; the strongest counter-result is the mini-roundabout's advantage, particularly at 800 veh/h. No further large-scale optimization search is necessary to publish these bounded findings.

## What I actually checked
1. Opened and reviewed all attached documents and five updated Python files. All five Python files pass `python -m py_compile` (syntax only).
2. Parsed all 270 rows in `roundabout_rerun.csv`: exactly 27 controller × split × volume cells, each with 10 repetitions; each row reports 100% served. Recomputed all nine paired differences between corrected and October roundabout implementations from raw values, using t(9)=2.262. Means and intervals match the supplied `.txt` (subject to rounding).
3. Independently counted contacts: corrected roundabout 0/90 runs, October-rules roundabout 4/90 runs; observed corrected-roundabout minimum moving-to-moving gap 0.215 m (two cells). These are simulated contacts/clearances, not independent safety certification.
4. Compared `roundabout_calibration.txt` and `moveup_sensitivity.txt` with their scripts and HCM-shaped published models; verified the formula forms against independent open literature. **Did not reproduce these studies from scratch** because the updated core modules and the raw `fair_signalling_test.csv` are not in the current uploaded set.
5. Reviewed the latest current-claims wording against the revised audit and numerical results. An earlier code archive cannot establish correctness of the new November 11–15 core changes.

## Findings and classification

### F1 — [BLOCKING FOR REPRODUCIBILITY, NOT A PROVEN SIMULATION BUG] No matching frozen current source package
`FINAL_AUDIT.md:3–7` refers to a matching code ZIP and `AUDIT_VERSION.txt`. The attachments contain only five updated `.py` modules and one raw result CSV. They do **not** include the current `blind_safe_v2.py`, `fair_signalling_test.py`, `cs4_human_baseline.py`, `capacity_curves.py`, `independent_checker.py`, `test_blind_no_truth.py`, `test_independent_checker.py`, the headline `fair_signalling_test.csv`, or `AUDIT_VERSION.txt`. The prior ZIP is labeled 2026-11-09 and predates the revised implementations. Therefore I cannot verify whether the current all-way-stop model is truly FCFS, whether signal-reader and stop-sign perceive precisely the same information, whether the independent collision checker is continuous and exhaustive, or whether the stop penalty is implemented as documented. **Direction:** Unknown. **Action:** Export the exact tested Git commit with environment lockfile, test files, raw CSVs and checksums; record command and revision in every table. No new optimization run is required.

### F2 — [WRONG/MISLEADING WORDING] “Roughly mini-roundabout delay” hides sizable relative differences at 800 veh/h
`FINAL_AUDIT.md:78–81`, `CLAIMS.md:35–41`; actual 800-veh/h data in `roundabout_rerun.txt:15–41`: balanced 4.4 vs 3.0 s (+47%), arterial 4.4 vs 3.6 s (+22%), dominant 4.8 vs 3.3 s (+45%), all paired intervals excluding zero in favor of roundabout. At 600 arterial/dominant, Smart Stop is only 0.1 s behind and intervals include zero. **Direction:** Inflates Smart Stop's relative competitiveness. **Action:** Say “nearly indistinguishable in the model at 600 on arterial and dominant splits; 22–47% higher mean delay at 800 across splits.” Distinguish absolute seconds from percentages.

### F3 — [UNJUSTIFIED STRENGTH OF LABEL] “Realistic drivers” only means a specific signaling assumption
`FINAL_AUDIT.md:171–184` models 25% non-signaling and 0% false signals in the “realistic” regime, with no misclassification, hesitation, occlusion, pedestrians or evasive braking. A separate 2%-false-signals regime is explicitly a stress scenario. **Direction:** Could flatter signal-reading Smart Stop in field conditions; real effect unknown. **Action:** Rename “25% signal nonuse, no deception” in headlines; present stress scenario separately.

### F4 — [CALIBRATION NOT VALIDATION] Roundabout capacity becomes substantially lower than the cited benchmarks
`roundabout_calibration.py:29–32,55–82` uses two seeds and four one-entry/one-circulating-flow conditions; empirical 'conflicting flow' is approximated as 85% of Green N departures. `roundabout_calibration.txt:3–7` shows 634 vs 672 (HCM 2010) and 812 (HCM 6) at v_c≈520; 270 vs 469/563 at v_c≈880. Thus the model is already below both HCM curves at 520 and 42–52% below at 880. A two-seed model-vs-formula check is not a comprehensive independent calibration. **Direction:** Pessimistic roundabout at higher circulating volume **flatters Smart Stop**, although its actual low-to-medium-vc comparisons appear comparatively well aligned; do not apply high-vc conclusion to every low-volume result. **Action:** Change “calibrated against HCM” to “sanity-checked against two HCM-style entry-capacity curves; deviations disclosed.” No mandatory retuning to publish a bounded comparison.

### F5 — [UNJUSTIFIED COMPARATOR CALIBRATION] Stop-sign model is materially slower than HCM in several cases
`FINAL_AUDIT.md:269–283` lists 4.30 vs 3.84, 5.90 vs 4.64, 9.50 vs 5.74 and 13.56 vs 9.54 s departure headways. Differences are approximately +12%, +27%, +66% and +42%, and may exaggerate the apparent improvement against the all-way stop. **Direction:** Flatters Smart Stop at higher demand. **Action:** Limit conclusions to “relative to the modeled stop-sign baseline,” present HCM calibration caveat alongside the 800 veh/h table, and do not claim empirically validated field capacity.

### F6 — [UNRESOLVED SAFETY VALIDATION] Sampled minimum clearance can be <1 m despite a 1 m decision buffer
`obb_survival_gate.py:97,154–169` uses a 1 m decision-box inflation, but `roundabout_rerun.csv` contains corrected-roundabout moving-pair minima of 0.215 m (balanced 1000 seed 0; dominant 1000 seed 5). This is not a demonstrated contact or necessarily an error: the policy buffer may be non-invariant under dynamics, and some pairs may never be constrained by that decision check. **Direction:** The observed safety margin is less than a blanket 1 m guarantee. **Action:** Explicitly distinguish prediction clearance *parameter* from guaranteed realized minimum separation. Keep the existing “no observed contacts in these runs” formulation. Do not use the 1 m buffer as a proven physical lower bound.

### F7 — [LIMITED SENSITIVITY, NOT PROVEN SYMMETRY] Setting MOVE_UP_TIME=0 does not equalize entire queue physics
`moveup_sensitivity.py:5–13,30–62` changes only the external stop-sign queue's move-up parameter, then compares with committed Smart Safe values. In the November 9 version of `capacity_curves.py:256–286`, platoon and nonplatoon algorithms are fed through different queue abstractions; only updated core source can establish whether that continues. `MOVE_UP_TIME=0` addresses one lever, not necessarily car-following, stopping positions, reaction timing or supply. **Direction:** Unknown; the provided 600/800 wins are robust to the single tested lever. **Action:** Describe test as “zero move-up-time sensitivity,” not “identical physical queues.” No need for a major new run in a simulation-study paper.

### F8 — [NOT PROVEN AS SAFETY SUPERIORITY] Liar-contact comparison is descriptive only
`CLAIMS.md:23–27` reports 47 signal-reading Smart Stop contacts versus 61 all-way-stop contacts, with 279 lying drivers in the stress simulations, and 0 for blind. Per-seed paired contact counts and uncertainty are not present. Runs use a model without evasive braking, and selected scenarios are not representative crash exposure. **Direction:** Unknown. **Action:** Report the three raw counts and state that neither relative risk nor field crash rates can be inferred. Do not advertise a 23% safety gain.

### F9 — [REPLICABILITY WORDING] “1,736 runs” is not 1,736 independent safety trials
The 1,736 tally (`FINAL_AUDIT.md:219–237`) pools multiple experiments and controller variants with recurring demand traces/seeds. Useful for detecting implementation contacts, but not statistically independent exposure at realistic failure rates. **Action:** Say “0 footprint overlaps were flagged in 1,736 model executions with honest-driver assumptions; many share scenarios and seeds.” Do not compute a rare-failure-rate bound from 1,736 as though independent.

### F10 — [REGULATORY/PHYSICAL] “No civil works” is a deployment hypothesis, not an established advantage
`FINAL_AUDIT.md:33–38,78–81` positions a STOP sign with a flashing-green permission indication and rolling entries as an off-the-shelf, no-construction solution. The FHWA current MUTCD is the 11th Edition Revision 1, and nonstandard devices need an authorized experiment. Flashing green is not a standard permission indication. Power, infrastructure, sight lines, maintenance and legal right-of-way changes remain uncosted. **Action:** Say “intended to avoid roundabout roadway reconstruction; installation and regulatory requirements not evaluated.” No real-world permission or low-cost claim.

### F11 — [CHECKED AND SUPPORTED] The November 15 roundabout entry fix is a defensible correction
`roundabout_entry.py:44–90` adds entering-arc conflict consideration; `roundabout_rerun.py:63–69` runs fixed and October-rules comparators. My independent CSV aggregation confirms the correction's directional effect at all nine cells; delay changes generally +0.05 to +0.22 seconds, with four October-model contacts and zero fixed-model contacts across 90 runs each. This fix makes the roundabout safer and modestly slower, which is transparent. It does not explain the 600–800 ranking.

### F12 — [REPRODUCIBILITY EDIT] Current claims document retains a stale top-line date and long superseded material
`CLAIMS.md:1–8` simultaneously says “Last updated July 20, 2026” and “CURRENT CLAIMS (2026-11-15).” Historic incompatible claims persist in the same long ledger, albeit marked superseded. **Action:** Make the update date 2026-11-15; put current claims in an executive one-pager and archive historical claims with explicit superseded watermarks.

## What can responsibly be said
> In a simulated isolated, single-lane four-way intersection without pedestrians, and under a specified 25% non-signaling/0%-false-signaling scenario, the signal-reading Smart Stop controller had lower mean control delay than the modeled all-way-stop baseline at 600 and 800 veh/h in balanced and arterial traffic; the blind version also showed lower delays, with a smaller improvement. Both results depend on particular stopping, geometry and perception assumptions. In the same model, a corrected mini-roundabout generally had lower delays, especially at 800 veh/h. An independent monitoring implementation reported no vehicle-footprint contacts in the honest-driver runs; this is not a real-world safety claim. Whether the system can be safely, legally and economically deployed is unresolved.

## Publication decision: bounded release checklist, no optimization treadmill
**Required before posting a research paper/preprint:**
1. Supply one frozen versioned archive of all tested code + core datasets + dependency file + tests + exact command line. Include a manifest/checksum and `AUDIT_VERSION`/Git commit. Re-run only the *fast* unit tests and a `--summarize` check on this frozen artifact; retain logs.
2. Correct C5 wording around roundabout parity, specify the signaling regime explicitly, and present stop-sign/HCM and roundabout/HCM calibration divergence near every headline table.
3. Remove any suggestion of proven collision-free operation, a guaranteed 1 m realized separation, a measured crash-risk advantage, “no civil works,” or established economics.
4. Publish the negative roundabout results and the false-signal stress results alongside the positive all-way-stop results, using the same visual prominence.
5. Separate full-stop legality/driver adaptation/pedestrians into clear **not modeled / not established** restrictions.

**Not required for this bounded simulation study:** more platoon tuning, dozens of reveal-distance optimizations, a new roundabout model, a full economic model, or a road deployment prototype. These are future-research items, not prerequisites to reporting a transparent, appropriately limited computational result.

**Standard for stronger engineering or safety claims:** independent validation of updated full source and safety checker, behavioral calibration, representative pedestrians and vulnerable users, perception errors, and regulatory/field work would be necessary.

## External verification (background, not primary evidence)
- FHWA current MUTCD 11th Edition Rev 1: https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm
- FHWA permission for experimentation: https://mutcd.fhwa.dot.gov/condexper.htm
- FHWA roundabout model comparisons, including HCM coefficient shape: https://highways.fhwa.dot.gov/media/11441
- Roundabout gap-acceptance functional form: https://link.springer.com/article/10.1007/s40534-015-0089-8

**Limitations of this audit:** The exact updated core package needed to inspect claims C1–C4 implementation was not attached in this message. I have not rerun hundreds of traffic simulations and have not certified collision detection or signal/stop parity from current full source. Conclusions labeled “checked” relate to the new CSV, the five attached Python scripts, and consistency of reported documents only.
