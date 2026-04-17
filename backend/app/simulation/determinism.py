"""Simulation determinism verifier.

Computes a rolling hash over all simulation events to verify reproducibility.
Two runs with the same seed + config should produce identical fingerprints.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class DivergenceReport:
    """Result of comparing two DeterminismTracker instances."""

    identical: bool
    first_divergent_step: int | None
    total_steps: int
    details: str


class DeterminismTracker:
    """Rolling cryptographic hash over simulation events.

    Ingests every simulation event in deterministic order and maintains
    both a cumulative SHA-256 digest and per-step digests so that two
    runs with the same seed + config can be compared at any granularity.
    """

    def __init__(self) -> None:
        self._hasher = hashlib.sha256()
        self._step_hashers: dict[int, hashlib._Hash] = {}
        self._step_order: list[int] = []  # ordered unique steps
        self._step_fingerprints: dict[int, str | None] = {}
        self._event_count = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _canonical_json(obj: Any) -> str:
        """Produce a canonical JSON string with sorted keys and no extra whitespace."""
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _feed(self, data: str) -> None:
        """Feed a string into the cumulative hasher."""
        self._hasher.update(data.encode("utf-8"))
        self._event_count += 1

    def _feed_step(self, step: int, data: str) -> None:
        """Feed a string into both the cumulative and per-step hashers."""
        encoded = data.encode("utf-8")
        self._hasher.update(encoded)
        self._event_count += 1

        if step not in self._step_hashers:
            self._step_hashers[step] = hashlib.sha256()
            self._step_order.append(step)
            self._step_fingerprints[step] = None  # mark dirty

        self._step_hashers[step].update(encoded)
        self._step_fingerprints[step] = None  # invalidate cache

    # ------------------------------------------------------------------
    # Public recording API
    # ------------------------------------------------------------------

    def record_tick(
        self,
        agent_id: str,
        step: int,
        actions: list[dict[str, Any]] | None = None,
        message: dict[str, Any] | str | None = None,
        state_changes: dict[str, Any] | None = None,
    ) -> None:
        """Record an agent tick output (actions, message, state changes)."""
        payload = self._canonical_json(
            {
                "type": "tick",
                "agent_id": agent_id,
                "step": step,
                "actions": actions or [],
                "message": message,
                "state_changes": state_changes or {},
            }
        )
        self._feed_step(step, payload)

    def record_world_state(self, step: int, world_state: dict[str, Any]) -> None:
        """Record a world state snapshot (canonical JSON, sorted keys)."""
        payload = self._canonical_json(
            {
                "type": "world_state",
                "step": step,
                "state": world_state,
            }
        )
        self._feed_step(step, payload)

    def record_event(self, event_type: str, data: Any) -> None:
        """Record a general simulation event (not tied to a specific step)."""
        payload = self._canonical_json(
            {
                "type": "event",
                "event_type": event_type,
                "data": data,
            }
        )
        self._feed(payload)

    # ------------------------------------------------------------------
    # Fingerprint queries
    # ------------------------------------------------------------------

    def fingerprint(self) -> str:
        """Return the cumulative hex digest covering all recorded events."""
        return self._hasher.hexdigest()

    def step_fingerprint(self, step: int) -> str:
        """Return the hex digest for a single step.

        Raises KeyError if the step was never recorded.
        """
        if step not in self._step_hashers:
            raise KeyError(f"No events recorded for step {step}")

        cached = self._step_fingerprints.get(step)
        if cached is not None:
            return cached

        fp = self._step_hashers[step].hexdigest()
        self._step_fingerprints[step] = fp
        return fp

    @property
    def steps_recorded(self) -> list[int]:
        """Return the list of steps that have been recorded, in order."""
        return list(self._step_order)

    @property
    def event_count(self) -> int:
        return self._event_count

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(self, other: DeterminismTracker) -> DivergenceReport:
        """Compare this tracker with another and find the first divergence point."""
        self_steps = self.steps_recorded
        other_steps = other.steps_recorded

        total = max(len(self_steps), len(other_steps))

        # Quick check: if cumulative fingerprints match, they're identical
        if self.fingerprint() == other.fingerprint():
            return DivergenceReport(
                identical=True,
                first_divergent_step=None,
                total_steps=total,
                details="Fingerprints match. Simulations are deterministically identical.",
            )

        # Walk through steps to find the first divergence
        all_steps = sorted(set(self_steps) | set(other_steps))

        for step in all_steps:
            self_has = step in self._step_hashers
            other_has = step in other._step_hashers

            if self_has and not other_has:
                return DivergenceReport(
                    identical=False,
                    first_divergent_step=step,
                    total_steps=total,
                    details=f"Step {step} exists in first tracker but not second.",
                )
            if other_has and not self_has:
                return DivergenceReport(
                    identical=False,
                    first_divergent_step=step,
                    total_steps=total,
                    details=f"Step {step} exists in second tracker but not first.",
                )

            if self.step_fingerprint(step) != other.step_fingerprint(step):
                return DivergenceReport(
                    identical=False,
                    first_divergent_step=step,
                    total_steps=total,
                    details=(
                        f"Divergence at step {step}: "
                        f"first={self.step_fingerprint(step)[:16]}... "
                        f"second={other.step_fingerprint(step)[:16]}..."
                    ),
                )

        # Steps all match individually but cumulative differs: event-only divergence
        return DivergenceReport(
            identical=False,
            first_divergent_step=None,
            total_steps=total,
            details=(
                "Per-step fingerprints match, but cumulative fingerprints differ. "
                "Divergence is in non-step events (record_event calls)."
            ),
        )
