#!/usr/bin/env python3
"""
Independent collision checker (audit 3, 2026-11-11)
===================================================
Measures footprint contact between every pair of vehicles physically
present, continuously between simulation steps.

Independence: it shares no code with the controllers' decision checks
(obb_survival_gate.py, turn_aware_collision.py) or with the old observer
(OBBWatch): its own footprint, its own exact polygon distance, its own pair
loop. The only thing it shares is the simulator's convention that a car's
(x, y) is the centre of its 4.5 x 2.0 m footprint.

What it closes, relative to OBBWatch (audit 3, F3):
  - every pair is checked, including same-lane and same-movement pairs;
  - the front car stopped at each stop line is included, so a moving car
    clipping a waiting car is caught;
  - contact BETWEEN steps is caught, not only at step instants.

Between steps, each car's pose is interpolated linearly in position and
heading. Footprint distance can change no faster than the two cars' fastest
corner speeds combined, so an interval whose end distances are large enough
cannot hide a contact; otherwise it is bisected down to MIN_DT. Linear
interpolation departs from the true curved path by a few millimetres per
0.1 s step at these speeds; gaps under TOL_M are reported as near-contacts.

Categories (each reported separately):
  moving-moving          both cars launched
  moving-stopped-cross   a moving car vs a car waiting at another approach's line
  moving-stopped-lane    a moving car vs the next car waiting in its own lane
                         (a queue-model artifact if the mover just launched)
  stopped-stopped        two waiting cars

Usage: mix `IndependentWatch` into a controller class (see `watched`), run
it, then read `alg.ic` (a ContactMonitor): `.summary()`, `.events`.
"""

import math

from config import METERS_PER_UNIT as MPU

CAR_L, CAR_W = 4.5, 2.0
HALF_DIAG = math.hypot(CAR_L, CAR_W) / 2
MIN_DT_FRAC = 1e-2        # bisection floor as a fraction of a step (1 ms at dt=0.1)
TOL_M = 0.02              # interpolation tolerance (m)
NEAR_M = 0.5              # refine minimum-gap estimates only below this (m)


# ── exact geometry ─────────────────────────────────────────────────────────

def footprint(x, y, h):
    """Corners (m) of a CAR_L x CAR_W rectangle centred at (x, y), heading h."""
    c, s = math.cos(h), math.sin(h)
    hl, hw = CAR_L / 2, CAR_W / 2
    return [(x + dx * c - dy * s, y + dx * s + dy * c)
            for dx, dy in ((hl, hw), (-hl, hw), (-hl, -hw), (hl, -hw))]


def _edges(P):
    return [(P[i], P[(i + 1) % len(P)]) for i in range(len(P))]


def _penetration(A, B):
    """None if A and B are separated; else minus the smallest overlap depth
    over all edge normals (<= 0; 0 means touching)."""
    depth = float('inf')
    for P in (A, B):
        for (ax, ay), (bx, by) in _edges(P):
            nx, ny = -(by - ay), bx - ax
            m = math.hypot(nx, ny)
            nx, ny = nx / m, ny / m
            pa = [px * nx + py * ny for px, py in A]
            pb = [px * nx + py * ny for px, py in B]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return None
            depth = min(depth, min(max(pa), max(pb)) - max(min(pa), min(pb)))
    return -depth


def _point_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def poly_distance(A, B):
    """Exact distance between convex polygons A and B (m): positive gap when
    apart, <= 0 (minus penetration depth) when touching or overlapping."""
    pen = _penetration(A, B)
    if pen is not None:
        return pen
    best = float('inf')
    for P, Q in ((A, B), (B, A)):
        for (px, py) in P:
            for (ax, ay), (bx, by) in _edges(Q):
                best = min(best, _point_seg(px, py, ax, ay, bx, by))
    return best


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _lerp_pose(p0, p1, u):
    return (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u,
            p0[2] + _wrap(p1[2] - p0[2]) * u)


def min_distance_over_step(a0, a1, b0, b1):
    """Certified minimum footprint distance over one step, with each car's
    pose (x, y, heading; metres/radians) interpolated linearly from *0 to *1.
    Returns (min distance found, lower bound on the true minimum)."""
    def d(u):
        pa, pb = _lerp_pose(a0, a1, u), _lerp_pose(b0, b1, u)
        return poly_distance(footprint(*pa), footprint(*pb))

    lip = (math.hypot(a1[0] - a0[0], a1[1] - a0[1]) + abs(_wrap(a1[2] - a0[2])) * HALF_DIAG
           + math.hypot(b1[0] - b0[0], b1[1] - b0[1]) + abs(_wrap(b1[2] - b0[2])) * HALF_DIAG)
    d0, d1 = d(0.0), d(1.0)
    best = min(d0, d1)
    lower = best
    if lip == 0.0:
        return best, best
    stack = [(0.0, 1.0, d0, d1)]
    while stack:
        u0, u1, da, db = stack.pop()
        lb = (da + db - lip * (u1 - u0)) / 2
        if lb > min(best, NEAR_M) or (lb > 0.0 and best <= 0.0):
            continue                      # cannot hold a contact or a smaller gap
        if u1 - u0 <= MIN_DT_FRAC:
            lower = min(lower, lb)
            continue
        um = (u0 + u1) / 2
        dm = d(um)
        best = min(best, dm)
        stack.append((u0, um, da, dm))
        stack.append((um, u1, dm, db))
    return best, min(lower, best)


# ── monitoring a run ──────────────────────────────────────────────────────

class ContactMonitor:
    """Feed it the vehicles present after every step; it checks every pair
    over the step just taken."""

    CATS = ('moving-moving', 'moving-stopped-cross', 'moving-stopped-lane',
            'stopped-stopped')

    def __init__(self):
        self.prev = {}                    # vehicle -> pose (m, m, rad)
        self.min_gap = {c: float('inf') for c in self.CATS}
        self.events = []                  # contacts and near-contacts
        self._seen = set()                # (id pair) already reported
        self.pairs_checked = 0

    def observe(self, t, present):
        """present: list of (vehicle, pose, moving: bool)."""
        cur = {v: (pose, moving) for v, pose, moving in present}
        items = list(cur.items())
        for i in range(len(items)):
            va, (pa1, ma) = items[i]
            pa0 = self.prev.get(va, pa1)
            for j in range(i + 1, len(items)):
                vb, (pb1, mb) = items[j]
                pb0 = self.prev.get(vb, pb1)
                # Cheap certified prefilter on centre distance.
                c0 = math.hypot(pa0[0] - pb0[0], pa0[1] - pb0[1])
                c1 = math.hypot(pa1[0] - pb1[0], pa1[1] - pb1[1])
                move = (math.hypot(pa1[0] - pa0[0], pa1[1] - pa0[1])
                        + math.hypot(pb1[0] - pb0[0], pb1[1] - pb0[1]))
                if (c0 + c1 - move) / 2 - 2 * HALF_DIAG > NEAR_M:
                    continue
                self.pairs_checked += 1
                gap, lower = min_distance_over_step(pa0, pa1, pb0, pb1)
                gap = float(gap)
                if ma and mb:
                    cat = 'moving-moving'
                elif ma or mb:
                    same = va.road_name == vb.road_name
                    cat = 'moving-stopped-lane' if same else 'moving-stopped-cross'
                else:
                    cat = 'stopped-stopped'
                self.min_gap[cat] = min(self.min_gap[cat], gap)
                if gap < TOL_M:
                    key = (cat,) + tuple(sorted((id(va), id(vb))))
                    if key not in self._seen:
                        self._seen.add(key)
                        self.events.append(dict(
                            t=round(t, 2), category=cat,
                            contact=gap <= 0.0, gap_m=round(gap, 3),
                            a=_tag(va), b=_tag(vb)))
                    else:                 # keep the deepest value per pair
                        for e in reversed(self.events):
                            if e['category'] == cat and {e['a'], e['b']} == {_tag(va), _tag(vb)}:
                                if gap < e['gap_m']:
                                    e['gap_m'] = round(gap, 3)
                                    e['contact'] = e['contact'] or gap <= 0.0
                                break
        self.prev = {v: pose for v, (pose, _) in cur.items()}

    def summary(self):
        out = {}
        for c in self.CATS:
            ev = [e for e in self.events if e['category'] == c]
            out[c] = dict(contacts=sum(e['contact'] for e in ev),
                          near=sum(not e['contact'] for e in ev),
                          min_gap_m=(round(self.min_gap[c], 3)
                                     if self.min_gap[c] != float('inf') else None))
        return out


def _tag(v):
    sig = getattr(v, 'true_signal', getattr(v, 'signal', '?'))
    return f"{v.road_name}/{sig}#{getattr(v, 'order', '?')}"


def _pose(v):
    return (float(v.state.x) * MPU, float(v.state.y) * MPU, float(v.state.heading))


def present_vehicles(alg):
    """Every active car, plus the front waiting car of each approach (it sits
    at the stop line; cars queued behind it are not positioned by the model)."""
    out = []
    active = [v for v in getattr(alg, 'active_vehicles', [])
              if v.active and not v.completed]
    for v in active:
        out.append((v, _pose(v), True))
    waiting = list(getattr(alg, 'waiting_vehicles', []))
    waiting += list(getattr(alg, '_pending', []))
    front = {}
    for v in waiting:
        if v.active or v.completed:
            continue
        if v.road_name not in front or v.order < front[v.road_name].order:
            front[v.road_name] = v
    for v in front.values():
        out.append((v, _pose(v), False))
    return out


class IndependentWatch:
    """Mixin: after every step, check every present pair over that step."""

    def step(self, dt=0.1):
        status = super().step(dt)
        if not hasattr(self, 'ic'):
            self.ic = ContactMonitor()
        self.ic.observe(self.current_time, present_vehicles(self))
        return status


def watched(base):
    """Controller class with the independent checker mixed in."""
    return type(base.__name__ + 'IC', (IndependentWatch, base), {})
