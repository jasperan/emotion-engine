"""Conversation Outcomes - extracts structured results when conversations end"""
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationOutcome:
    """Structured outcome of a completed conversation"""
    conversation_id: str
    outcome_type: str  # agreement, disagreement, information_exchange, task_assignment, inconclusive
    decisions: list[str]
    commitments: dict[str, str]  # agent_id -> what they committed to
    unresolved: list[str]
    participants: list[str]
    location: str | None
    step_range: tuple[int, int]
    message_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "outcome_type": self.outcome_type,
            "decisions": self.decisions,
            "commitments": self.commitments,
            "unresolved": self.unresolved,
            "participants": self.participants,
            "location": self.location,
            "step_range": list(self.step_range),
            "message_count": self.message_count,
        }

    def to_context_string(self) -> str:
        """Render as context for agent prompts"""
        parts = [f"Previous conversation outcome ({self.outcome_type}):"]
        if self.decisions:
            parts.append("  Decisions:")
            for d in self.decisions:
                parts.append(f"    - {d}")
        if self.commitments:
            parts.append("  Commitments:")
            for agent, commitment in self.commitments.items():
                parts.append(f"    - {agent}: {commitment}")
        if self.unresolved:
            parts.append("  Unresolved:")
            for u in self.unresolved:
                parts.append(f"    - {u}")
        return "\n".join(parts)


# Keyword patterns for outcome classification
_AGREEMENT_KEYWORDS = {"agree", "yes", "deal", "ok", "let's do", "sounds good", "i'll help", "together", "plan"}
_DISAGREEMENT_KEYWORDS = {"no", "disagree", "refuse", "won't", "can't", "impossible", "bad idea"}
_TASK_KEYWORDS = {"task", "assign", "volunteer", "i'll take", "my job", "responsible", "delegate"}
_COMMITMENT_KEYWORDS = {"i will", "i'll", "i promise", "count on me", "i commit", "my responsibility"}


class ConversationOutcomeExtractor:
    """
    Extracts structured outcomes from completed conversations.
    Uses keyword-based heuristics (could be enhanced with LLM summarization).
    """

    def __init__(self):
        self._outcomes: dict[str, ConversationOutcome] = {}
        self._agent_outcomes: dict[str, list[str]] = {}  # agent_id -> outcome_ids

    def extract_outcome(
        self,
        conversation_id: str,
        messages: list[dict[str, Any]],
        participants: list[str],
        location: str | None,
        agent_names: dict[str, str] | None = None,
    ) -> ConversationOutcome:
        """Extract structured outcome from conversation messages"""
        names = agent_names or {}

        if not messages:
            outcome = ConversationOutcome(
                conversation_id=conversation_id,
                outcome_type="inconclusive",
                decisions=[],
                commitments={},
                unresolved=[],
                participants=participants,
                location=location,
                step_range=(0, 0),
                message_count=0,
            )
            self._store_outcome(outcome)
            return outcome

        # Determine step range
        steps = [m.get("step_index", 0) for m in messages]
        step_range = (min(steps), max(steps))

        # Analyze message content
        all_text = " ".join(m.get("content", "").lower() for m in messages)
        last_messages = messages[-3:] if len(messages) >= 3 else messages

        # Classify outcome type
        outcome_type = self._classify_outcome(all_text, last_messages)

        # Extract decisions (statements in last few messages that sound decisive)
        decisions = self._extract_decisions(last_messages, names)

        # Extract commitments
        commitments = self._extract_commitments(messages, names)

        # Extract unresolved topics (questions without answers)
        unresolved = self._extract_unresolved(messages, names)

        outcome = ConversationOutcome(
            conversation_id=conversation_id,
            outcome_type=outcome_type,
            decisions=decisions,
            commitments=commitments,
            unresolved=unresolved,
            participants=participants,
            location=location,
            step_range=step_range,
            message_count=len(messages),
        )

        self._store_outcome(outcome)
        return outcome

    def _classify_outcome(
        self, all_text: str, last_messages: list[dict[str, Any]]
    ) -> str:
        """Classify the overall outcome type"""
        last_text = " ".join(m.get("content", "").lower() for m in last_messages)

        # Check task assignment patterns
        task_score = sum(1 for kw in _TASK_KEYWORDS if kw in all_text)
        agreement_score = sum(1 for kw in _AGREEMENT_KEYWORDS if kw in last_text)
        disagreement_score = sum(1 for kw in _DISAGREEMENT_KEYWORDS if kw in last_text)

        if task_score >= 2:
            return "task_assignment"
        if agreement_score > disagreement_score and agreement_score >= 2:
            return "agreement"
        if disagreement_score > agreement_score and disagreement_score >= 2:
            return "disagreement"
        if len(last_messages) >= 2:
            return "information_exchange"
        return "inconclusive"

    def _extract_decisions(
        self, last_messages: list[dict[str, Any]], names: dict[str, str]
    ) -> list[str]:
        """Extract decision-like statements from final messages"""
        decisions = []
        decision_indicators = [
            "let's", "we should", "we will", "the plan is",
            "decided", "going to", "agreed to",
        ]

        for msg in last_messages:
            content = msg.get("content", "")
            content_lower = content.lower()
            sender = msg.get("from_agent_name", msg.get("from_agent", "Someone"))

            for indicator in decision_indicators:
                if indicator in content_lower:
                    # Extract the sentence containing the indicator
                    sentences = content.split(".")
                    for sentence in sentences:
                        if indicator in sentence.lower() and len(sentence.strip()) > 10:
                            decisions.append(f"{sender}: {sentence.strip()}")
                            break
                    break

        return decisions[:5]  # Cap at 5

    def _extract_commitments(
        self, messages: list[dict[str, Any]], names: dict[str, str]
    ) -> dict[str, str]:
        """Extract personal commitments from messages"""
        commitments = {}

        for msg in messages:
            content = msg.get("content", "").lower()
            sender_id = msg.get("from_agent", "")
            sender_name = msg.get("from_agent_name", sender_id)

            for kw in _COMMITMENT_KEYWORDS:
                if kw in content:
                    # Extract the commitment sentence
                    sentences = msg.get("content", "").split(".")
                    for sentence in sentences:
                        if kw in sentence.lower() and len(sentence.strip()) > 10:
                            commitments[sender_name] = sentence.strip()
                            break
                    break

        return commitments

    def _extract_unresolved(
        self, messages: list[dict[str, Any]], names: dict[str, str]
    ) -> list[str]:
        """Extract unresolved questions"""
        questions = []
        for msg in messages[-5:]:
            content = msg.get("content", "")
            if "?" in content:
                sender = msg.get("from_agent_name", msg.get("from_agent", "Someone"))
                # Extract question sentences
                for sentence in content.split("."):
                    if "?" in sentence and len(sentence.strip()) > 10:
                        questions.append(f"{sender}: {sentence.strip()}")

        return questions[:3]  # Cap at 3

    def _store_outcome(self, outcome: ConversationOutcome) -> None:
        """Store outcome and index by participant"""
        self._outcomes[outcome.conversation_id] = outcome
        for participant in outcome.participants:
            self._agent_outcomes.setdefault(participant, []).append(
                outcome.conversation_id
            )

    def get_agent_recent_outcomes(
        self, agent_id: str, limit: int = 3
    ) -> list[ConversationOutcome]:
        """Get recent conversation outcomes for an agent"""
        outcome_ids = self._agent_outcomes.get(agent_id, [])
        outcomes = [
            self._outcomes[oid]
            for oid in outcome_ids[-limit:]
            if oid in self._outcomes
        ]
        return outcomes

    def get_outcome(self, conversation_id: str) -> ConversationOutcome | None:
        return self._outcomes.get(conversation_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcomes": {
                cid: o.to_dict() for cid, o in self._outcomes.items()
            }
        }
