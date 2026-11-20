#!/usr/bin/env python3
"""
Motion-confirmed intent — the false-signal defense, built INTO the controller
==============================================================================
(2026-07-21.) `adversarial_intent.py` showed the trusting controller is
exposed to a false turn signal (signal "right", turn "left"): the cross-path
floor drops to 2.56 m, breaching margin in 32% of adversarial scenarios,
because the EXIT_ARM co-activation shortcut trusts the declared signal. It
also showed the fix — the `PerceptionDetector` phantom/`REVEAL_M` net, applied
to ALL declared intent (not just unreadable) — closes it (floor 3.48 m).

That fix previously lived only in the discrete test harness. This module
moves it into the controller itself, so the controller is safe against a
false or mistaken signal BY CONSTRUCTION — intent is a hypothesis confirmed
by motion before it can green-light a conflicting pair, never trusted on
declaration. A false signal can then cost throughput, but never cause a
collision.

`ConfirmedSmartStop` is the discrete controller with the defense installed;
`MotionConfirmedMixin` layers it onto any Smart Stop controller (the streaming
platoon controllers subclass the same base, so the same mixin composes with
them for a future streaming integration).
"""

from reality_sweeps import PerceptionDetector, make_phantoms
from path_based_smart_stop import PathBasedSmartStopAlgorithm


class MotionConfirmedMixin:
    """Wrap the controller's collision detector so every vehicle whose intent
    is not yet motion-confirmed is checked against ALL possible paths; register
    each vehicle's hypothesis phantoms as it is added. Self-contained — no
    harness-supplied variant map. Safety becomes independent of signal honesty.

    Cost: co-activations that were safe only under the (trusted) declared
    intent now wait for motion confirmation (REVEAL_M) instead of being
    granted on the blinker. Co-activations safe under EVERY intent (the
    EXIT_ARM topological pairs) still pass immediately, so the throughput hit
    falls only on the genuinely intent-dependent releases."""

    def __init__(self, geometry):
        super().__init__(geometry)
        self._mci_variants = {}
        self.collision_detector = PerceptionDetector(self.collision_detector,
                                                     self._mci_variants)

    def add_vehicle(self, vehicle):
        super().add_vehicle(vehicle)
        if getattr(vehicle, 'true_signal', None) is not None:
            self._mci_variants[id(vehicle)] = make_phantoms(
                vehicle.road_name, vehicle.order, self.geometry)


class ConfirmedSmartStop(MotionConfirmedMixin, PathBasedSmartStopAlgorithm):
    """Smart Stop that never bets a co-activation's safety on the declared
    turn signal being honest. Drop-in for PathBasedSmartStopAlgorithm."""
    pass
