#!/usr/bin/env python3
"""
Block 3 — Human Realism on Both Sides (the mature-vs-mature race)
==================================================================
Blocks 1-2 left the two contenders idealized in opposite directions:
the roundabout had no follow-up headway and stop-dead entries; Smart Stop
had instant flash compliance and no protection against heterogeneous
driver launch delays (the U(0.5-2.0 s) jitter that produced a 2.29 m
near-collision in the original reality sweep). Block 3 removes both sets
of flattery at once:

Smart Stop side (GatedPlatoonSmartStop + RollingVehicle):
  - Reaction jitter: every stopped launch waits a per-driver
    perception-reaction delay after its green flash (harness-injected).
  - Motion-confirmed gating, done properly: rather than a blunt "no new
    flash while anyone is dwelling," the DwellRobustDetector clears a
    pair only if it is collision-free under EVERY launch-delay hypothesis
    (0 / 1.2 / 2.5 s) for each vehicle that is not yet confirmed moving.
    Topologically independent pairs (parallel, R+R, distinct exit arms)
    pass all hypotheses trivially — jitter cannot hurt them — so gating
    costs throughput only where timing actually matters. Platoon releases
    are inherently motion-confirmed (leader must be 7 m downstream).
  - Rolling green: a head arriving at the line whose window is already
    open (activated within ROLL_WINDOW of reaching the line) crosses at
    its movement's curvature speed without stopping — the green-wave
    mechanism that attacks the stop-start penalty. Rolling launches skip
    the reaction dwell (the driver never stopped) and are instantly
    motion-confirmed.

Roundabout side (RealisticRoundabout):
  - Follow-up headway: successive entries from one approach >= 2.8 s
    apart (HCM ~2.6-3.1 s) — the entry-discharge limit the permissive
    and gap-only models lacked.
  - Rolling entry: a vehicle reaching the yield line with an acceptable
    gap enters at ring speed without stopping (same RollingVehicle
    mechanism, same ROLL_WINDOW — symmetric treatment).
  - Stopped entries still pay the driver reaction dwell (harness-injected
    jitter), as at any yield line.
"""

from roundabout_entry import GapAcceptanceRoundabout
from block2_platoon import FollowingVehicle, PlatoonSmartStop

ROLL_WINDOW = 0.3       # s — activation within this of line arrival = rolling
CONFIRM_V   = 0.3       # m/s — below this (and < CONFIRM_POS) = not yet moving
CONFIRM_POS = 1.0       # m along path
DWELL_HYPOTHESES = (0.0, 1.2, 2.5)   # launch-delay hypotheses (2.5 ~ p99 dwell)
FOLLOW_UP_S = 2.8       # s — roundabout entry follow-up headway (HCM ~2.6-3.1)


class RollingVehicle(FollowingVehicle):
    """FollowingVehicle + rolling arrival: if activated within ROLL_WINDOW
    of reaching the line (`roll_deadline`), the vehicle enters at
    `roll_v0` with no reaction dwell — it never stopped. Otherwise it
    launches from rest after its (harness-assigned) reaction delay."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.roll_deadline = -1.0     # set by the harness at line arrival
        self.roll_v0 = 0.0
        self.rolled = False
        # While in the roll window the harness sets state.velocity = roll_v0
        # so the collision predictor sees the vehicle as it really is — an
        # approach at speed, not a car at rest. (Predicting rolling arrivals
        # from v=0 undershot their progress and cleared conflicts that then
        # realized as 0.08 m approaches — caught by the cross-path
        # observable.) The harness zeroes it if the roll window expires.

    def activate(self, current_time):
        super().activate(current_time)
        if current_time <= self.roll_deadline and self.roll_v0 > 0.0:
            self.state.velocity = self.roll_v0
            # No dwell - already moving. A hesitant roller (roll_hesitation > 0,
            # 2026-11-11) never stops but crosses the line that many seconds
            # late, still at speed: a time-loss model of easing off while
            # deciding. Default 0 = legacy behaviour.
            self._go_time = current_time + getattr(self, 'roll_hesitation', 0.0)
            self.rolled = True
        else:
            self.state.velocity = 0.0         # stopped launch from rest


class _DelayShift:
    """Duck-typed proxy: vehicle whose predicted trajectory is shifted by a
    launch-delay hypothesis d (position at t = real position at t - d)."""

    def __init__(self, vehicle, delay):
        object.__setattr__(self, '_v', vehicle)
        object.__setattr__(self, '_d', delay)

    def __getattr__(self, name):
        return getattr(self._v, name)

    def get_future_position(self, time_ahead):
        return self._v.get_future_position(max(0.0, time_ahead - self._d))


def _uncertain(v):
    """True if this vehicle's launch timing is not yet observable: either a
    candidate (not active) or flashed but not confirmed moving."""
    if getattr(v, 'completed', False):
        return False
    if getattr(v, 'rolled', False):
        return False                      # rolling launch: moving by definition
    if not getattr(v, 'active', False):
        return True                       # candidate under evaluation
    return (v.state.velocity < CONFIRM_V
            and v.current_position_meters < CONFIRM_POS)


class DwellRobustDetector:
    """Clears a pair only if collision-free under every launch-delay
    hypothesis for each timing-uncertain vehicle. This is motion-confirmed
    gating in detector form: pairs whose safety does not depend on launch
    timing (topological rules, far geometry) pass all hypotheses at no
    cost; pairs cleared only by trajectory prediction are held until the
    uncertain party is confirmed rolling."""

    def __init__(self, inner, min_candidate_dwell=0.0):
        self.inner = inner
        self.safety_margin = inner.safety_margin
        # Pre-flash (Block 5 lever 2): a STOPPED candidate physically cannot
        # launch in under ~0.5 s of perception-reaction, so the d=0 hypothesis
        # is impossible for it — testing it anyway forces the flash to wait
        # for full conflict clearance that the driver's own reaction time
        # would have absorbed. Setting min_candidate_dwell=0.5 drops the
        # impossible hypothesis for stopped candidates only (rolling arrivals
        # and already-active vehicles keep d=0), letting the flash overlap
        # the tail of a clearing conflict while remaining delay-robust.
        self.min_candidate_dwell = min_candidate_dwell

    # Dense lattice for pre-flash mode: pre-flash approves activations right
    # at the margin boundary, where the coarse 3-point lattice leaves gaps an
    # actual dwell can land in (observed: 2.14 m cross-path with {0.5,1.2,2.5}
    # — a real dwell between samples slipped through). Bounds match the
    # harness jitter range U(0.5, 2.0) plus tail.
    PREFLASH_HYPOTHESES = (0.5, 0.8, 1.1, 1.5, 2.0, 2.5)

    def _hyps(self, v):
        # Optional per-controller hypotheses (2026-11-11; legacy = None):
        # `roll_hyps` covers a flashed roller that hasn't crossed the line yet
        # (it may be hesitating); `stop_hyps` replaces the module-level
        # DWELL_HYPOTHESES for this controller only.
        roll_hyps = getattr(self, 'roll_hyps', None)
        if (roll_hyps and getattr(v, 'rolled', False) and getattr(v, 'active', False)
                and v.current_position_meters < CONFIRM_POS):
            return roll_hyps
        if not _uncertain(v):
            return (0.0,)
        # "Stopped" must be a KINEMATIC test: a candidate inside its roll
        # window is approaching at speed (harness presets state.velocity =
        # roll_v0) and launches with ZERO dwell if flashed — treating it as a
        # >=0.5 s-dwell stopped car under-predicts its advance (observed:
        # 2.14 m cross-path at balanced-1200, where most launches roll).
        if (self.min_candidate_dwell > 0.0 and not getattr(v, 'active', False)
                and v.state.velocity < CONFIRM_V):
            return self.PREFLASH_HYPOTHESES
        return getattr(self, 'stop_hyps', None) or DWELL_HYPOTHESES

    def check_collision(self, v1, v2, time_horizon=3.0,
                        signal1=None, signal2=None):
        d1s = self._hyps(v1)
        d2s = self._hyps(v2)
        for d1 in d1s:
            p1 = _DelayShift(v1, d1) if d1 else v1
            for d2 in d2s:
                p2 = _DelayShift(v2, d2) if d2 else v2
                if self.inner.check_collision(p1, p2, time_horizon,
                                              signal1=signal1, signal2=signal2):
                    return True
        return False


class EvasiveVehicle(RollingVehicle):
    """RollingVehicle + reactive evasive braking (Block 7): if any cross-path
    peer's predicted separation falls below BRAKE_RANGE_M within the next
    ~0.8 s, the less-committed vehicle (smaller path progress; ties broken
    by later order) brakes to a stop until the conflict clears. This is the
    human evasion the compliance sweep deliberately omitted — its absence
    made every jumper conflict a guaranteed collision.

    The harness wires `_peers` to the algorithm's live active-vehicle list."""

    # Trigger on time-to-conflict, not proximity: braking from 6 m/s at
    # -3 m/s^2 takes 2 s — a 0.8 s horizon detects conflicts after the point
    # of no return (first draft did exactly that; still 0.00 m). The horizon
    # must exceed the braking envelope.
    BRAKE_RANGE_M = 3.4
    _LOOKAHEADS = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._peers = None

    def _must_yield(self):
        import math as _m
        from config import METERS_PER_UNIT as _mpu
        for p in self._peers:
            if p is self or not p.active or p.completed:
                continue
            if p.road_name == self.road_name and p.signal == self.signal:
                continue
            for ta in self._LOOKAHEADS:
                mp = self.get_future_position(ta)
                pp = p.get_future_position(ta)
                if not mp or not pp:
                    continue
                d = _m.hypot(mp[0] - pp[0], mp[1] - pp[1]) * _mpu
                if d < self.BRAKE_RANGE_M:
                    mine, theirs = self.current_position_meters, p.current_position_meters
                    if mine < theirs or (mine == theirs and self.order > p.order):
                        return True
                    break
        return False

    def update(self, dt, target_speed=None):
        if self.active and self._peers and self._must_yield():
            return super().update(dt, 0.0)
        return super().update(dt, target_speed)


class GatedPlatoonSmartStop(PlatoonSmartStop):
    """Block 2 platoon Smart Stop + dwell-robust (motion-confirmed)
    activation. Vehicle-side realism (reaction jitter, rolling green) is
    carried by RollingVehicle + harness wiring."""

    USE_ROLLING = True

    # Platoon followers launch off the movement of the car ahead, not off
    # the flash — the anticipation embodied in real ~2 s signalized
    # saturation headways. Charging followers the full flash-reaction
    # jitter on top of the 7 m release spacing double-counts their
    # reaction (the mirror of the roundabout post-acceptance dwell
    # double-count). Heads keep the full jitter: that is the honest cost
    # of the flash interface.
    FOLLOWER_MAX_DWELL = 0.6

    def __init__(self, geometry):
        super().__init__(geometry)
        # Wrap the PlatoonDetector (same-path arc rule stays innermost and
        # position-based; dwell hypotheses apply to the trajectory checks).
        self.collision_detector = DwellRobustDetector(self.collision_detector)

    def _claim_followers(self, leader):
        n0 = len(self._pending)
        super()._claim_followers(leader)
        for v in self._pending[n0:]:
            if getattr(v, 'reaction_delay', 0.0) > self.FOLLOWER_MAX_DWELL:
                v.reaction_delay = self.FOLLOWER_MAX_DWELL


class RealisticRoundabout(GapAcceptanceRoundabout):
    """Gap-acceptance roundabout + follow-up headway + rolling entry
    (via RollingVehicle). Stopped entries pay the driver reaction dwell."""

    USE_ROLLING = True

    def __init__(self, geometry):
        super().__init__(geometry)
        self._last_entry = {}          # road -> time of last entry

    def _try_enter_roundabout(self):
        for waiting_vehicle in self.waiting_vehicles[:]:
            last = self._last_entry.get(waiting_vehicle.road_name)
            if last is not None and self.current_time - last < FOLLOW_UP_S:
                continue
            if not self._gap_ok(waiting_vehicle):
                continue
            can_enter = True
            for active_vehicle in self.active_vehicles:
                if self.collision_detector.check_collision(
                        waiting_vehicle, active_vehicle, time_horizon=3.0):
                    can_enter = False
                    break
            if can_enter:
                self.waiting_vehicles.remove(waiting_vehicle)
                waiting_vehicle.activate(self.current_time)
                self.active_vehicles.append(waiting_vehicle)
                self._last_entry[waiting_vehicle.road_name] = self.current_time
                break
