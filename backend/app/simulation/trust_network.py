"""Trust Network - bilateral trust signals and transitive trust"""
from typing import Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TrustSignal:
    """A trust signal emitted when trust changes significantly"""
    from_agent: str
    to_agent: str
    signal_type: str  # warming, cooling, vouching
    reason: str
    step: int
    trust_level: int  # current trust level after change

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "signal_type": self.signal_type,
            "reason": self.reason,
            "step": self.step,
            "trust_level": self.trust_level,
        }


class TrustNetwork:
    """
    Manages bilateral trust signals between agents.

    Unlike unilateral trust in AgentMemory, this network:
    - Emits visible signals when trust changes significantly (delta >= 2)
    - Supports transitive trust via vouching
    - Tracks trust history for relationship narrative
    """

    SIGNIFICANT_DELTA = 2

    def __init__(self):
        # Pending signals: agent_id -> list of TrustSignals to deliver
        self._pending_signals: dict[str, list[TrustSignal]] = defaultdict(list)
        # All emitted signals for history
        self._signal_history: list[TrustSignal] = []
        # Vouch records: (voucher, subject) -> list of vouchees
        self._vouches: dict[tuple[str, str], list[str]] = {}

    def record_trust_change(
        self,
        from_agent: str,
        to_agent: str,
        old_trust: int,
        new_trust: int,
        reason: str,
        step: int,
    ) -> TrustSignal | None:
        """
        Record a trust change. If significant (delta >= 2), emit a signal
        visible to the other agent.
        """
        delta = new_trust - old_trust
        if abs(delta) < self.SIGNIFICANT_DELTA:
            return None

        signal_type = "warming" if delta > 0 else "cooling"
        signal = TrustSignal(
            from_agent=from_agent,
            to_agent=to_agent,
            signal_type=signal_type,
            reason=reason,
            step=step,
            trust_level=new_trust,
        )
        self._pending_signals[to_agent].append(signal)
        self._signal_history.append(signal)
        return signal

    def vouch_for(
        self,
        voucher_id: str,
        subject_id: str,
        recipient_ids: list[str],
        step: int,
        reason: str = "",
    ) -> list[TrustSignal]:
        """
        Agent vouches for another, creating transitive trust signals.
        Recipients receive a 'vouching' signal about the subject.
        """
        key = (voucher_id, subject_id)
        self._vouches[key] = recipient_ids

        signals = []
        for recipient_id in recipient_ids:
            signal = TrustSignal(
                from_agent=voucher_id,
                to_agent=recipient_id,
                signal_type="vouching",
                reason=f"Vouches for {subject_id}: {reason}" if reason else f"Vouches for {subject_id}",
                step=step,
                trust_level=0,  # Not a direct trust level, indicates vouch
            )
            self._pending_signals[recipient_id].append(signal)
            self._signal_history.append(signal)
            signals.append(signal)

        return signals

    def get_pending_signals(self, agent_id: str, clear: bool = True) -> list[TrustSignal]:
        """Get pending trust signals for an agent"""
        signals = self._pending_signals.get(agent_id, []).copy()
        if clear:
            self._pending_signals[agent_id] = []
        return signals

    def get_trust_context(self, agent_id: str) -> str:
        """Build trust context string for agent prompt"""
        signals = self.get_pending_signals(agent_id, clear=False)
        if not signals:
            return ""

        parts = ["Trust signals:"]
        for sig in signals:
            if sig.signal_type == "warming":
                parts.append(
                    f"- {sig.from_agent} is warming toward you (trust now {sig.trust_level}/10): {sig.reason}"
                )
            elif sig.signal_type == "cooling":
                parts.append(
                    f"- {sig.from_agent} is becoming distant (trust now {sig.trust_level}/10): {sig.reason}"
                )
            elif sig.signal_type == "vouching":
                parts.append(f"- {sig.from_agent} {sig.reason}")

        return "\n".join(parts)

    def get_signal_history(
        self,
        agent_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get trust signal history, optionally filtered by agent"""
        signals = self._signal_history
        if agent_id:
            signals = [
                s for s in signals
                if s.from_agent == agent_id or s.to_agent == agent_id
            ]
        return [s.to_dict() for s in signals[-limit:]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_history": [s.to_dict() for s in self._signal_history],
            "vouches": {
                f"{k[0]}:{k[1]}": v for k, v in self._vouches.items()
            },
        }
