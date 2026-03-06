"""Negotiation Manager - state machine for inter-agent proposals and agreements"""
import uuid
from typing import Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field


class ProposalState(str, Enum):
    """State machine for proposals"""
    PENDING = "pending"
    COUNTER_PENDING = "counter_pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


@dataclass
class Proposal:
    """A tracked proposal between agents"""
    id: str
    proposer_id: str
    target_id: str | None  # None = open to anyone
    proposal_type: str  # task, trade, plan, movement, cooperation
    description: str
    parameters: dict[str, Any]
    state: ProposalState
    created_at_step: int
    expires_at_step: int | None  # None = no expiry
    counter_proposal: dict[str, Any] | None = None
    response_reasoning: str = ""
    resolved_at_step: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposer_id": self.proposer_id,
            "target_id": self.target_id,
            "proposal_type": self.proposal_type,
            "description": self.description,
            "parameters": self.parameters,
            "state": self.state.value,
            "created_at_step": self.created_at_step,
            "expires_at_step": self.expires_at_step,
            "counter_proposal": self.counter_proposal,
            "response_reasoning": self.response_reasoning,
            "resolved_at_step": self.resolved_at_step,
        }


@dataclass
class Agreement:
    """A binding agreement resulting from accepted proposal"""
    id: str
    proposal_id: str
    parties: list[str]  # agent IDs
    terms: str
    commitments: dict[str, str]  # agent_id -> what they committed to
    created_at_step: int
    fulfilled: bool = False
    fulfilled_at_step: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_id": self.proposal_id,
            "parties": self.parties,
            "terms": self.terms,
            "commitments": self.commitments,
            "created_at_step": self.created_at_step,
            "fulfilled": self.fulfilled,
            "fulfilled_at_step": self.fulfilled_at_step,
        }


class NegotiationManager:
    """
    Manages formal negotiation between agents with tracked state machines.

    Proposal lifecycle:
        propose -> [pending]
                    |- accept_proposal -> [accepted] -> Agreement created
                    |- counter_propose -> [counter_pending] -> accept/reject
                    |- reject_proposal -> [rejected]
                    |- withdraw_proposal -> [withdrawn]
                    |- (timeout) -> [expired]
    """

    def __init__(self, default_expiry_steps: int = 5):
        self._proposals: dict[str, Proposal] = {}
        self._agreements: dict[str, Agreement] = {}
        self._agent_proposals: dict[str, list[str]] = {}  # agent_id -> proposal_ids
        self._agent_agreements: dict[str, list[str]] = {}  # agent_id -> agreement_ids
        self.default_expiry_steps = default_expiry_steps

    def create_proposal(
        self,
        proposer_id: str,
        target_id: str | None,
        proposal_type: str,
        description: str,
        parameters: dict[str, Any],
        current_step: int,
        expiry_steps: int | None = None,
    ) -> Proposal:
        """Create a new proposal"""
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        expiry = expiry_steps if expiry_steps is not None else self.default_expiry_steps
        proposal = Proposal(
            id=proposal_id,
            proposer_id=proposer_id,
            target_id=target_id,
            proposal_type=proposal_type,
            description=description,
            parameters=parameters,
            state=ProposalState.PENDING,
            created_at_step=current_step,
            expires_at_step=current_step + expiry if expiry else None,
        )
        self._proposals[proposal_id] = proposal
        self._agent_proposals.setdefault(proposer_id, []).append(proposal_id)
        if target_id:
            self._agent_proposals.setdefault(target_id, []).append(proposal_id)
        return proposal

    def accept_proposal(
        self,
        proposal_id: str,
        acceptor_id: str,
        current_step: int,
        reasoning: str = "",
    ) -> Agreement | None:
        """Accept a proposal, creating a binding agreement"""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None
        if proposal.state not in (ProposalState.PENDING, ProposalState.COUNTER_PENDING):
            return None

        proposal.state = ProposalState.ACCEPTED
        proposal.resolved_at_step = current_step
        proposal.response_reasoning = reasoning

        # Create agreement
        agreement_id = f"agree_{uuid.uuid4().hex[:8]}"
        parties = [proposal.proposer_id, acceptor_id]

        # Build commitments from proposal parameters
        commitments = {}
        if "proposer_commitment" in proposal.parameters:
            commitments[proposal.proposer_id] = proposal.parameters["proposer_commitment"]
        if "target_commitment" in proposal.parameters:
            commitments[acceptor_id] = proposal.parameters["target_commitment"]
        # If counter-proposal was accepted, use counter terms
        if proposal.counter_proposal:
            commitments.update(proposal.counter_proposal.get("commitments", {}))

        agreement = Agreement(
            id=agreement_id,
            proposal_id=proposal_id,
            parties=parties,
            terms=proposal.description,
            commitments=commitments,
            created_at_step=current_step,
        )
        self._agreements[agreement_id] = agreement
        for party in parties:
            self._agent_agreements.setdefault(party, []).append(agreement_id)

        return agreement

    def reject_proposal(
        self,
        proposal_id: str,
        rejector_id: str,
        current_step: int,
        reasoning: str = "",
    ) -> bool:
        """Reject a proposal"""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False
        if proposal.state not in (ProposalState.PENDING, ProposalState.COUNTER_PENDING):
            return False

        proposal.state = ProposalState.REJECTED
        proposal.resolved_at_step = current_step
        proposal.response_reasoning = reasoning
        return True

    def counter_propose(
        self,
        proposal_id: str,
        counter_agent_id: str,
        counter_terms: dict[str, Any],
        current_step: int,
    ) -> bool:
        """Submit a counter-proposal modifying the original terms"""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False
        if proposal.state != ProposalState.PENDING:
            return False

        proposal.state = ProposalState.COUNTER_PENDING
        proposal.counter_proposal = {
            "from_agent": counter_agent_id,
            "terms": counter_terms,
            "step": current_step,
            "commitments": counter_terms.get("commitments", {}),
        }
        # Reset expiry for counter-proposal
        if proposal.expires_at_step:
            proposal.expires_at_step = current_step + self.default_expiry_steps
        return True

    def withdraw_proposal(
        self, proposal_id: str, agent_id: str, current_step: int
    ) -> bool:
        """Proposer withdraws their proposal"""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False
        if proposal.proposer_id != agent_id:
            return False
        if proposal.state in (ProposalState.ACCEPTED, ProposalState.REJECTED):
            return False

        proposal.state = ProposalState.WITHDRAWN
        proposal.resolved_at_step = current_step
        return True

    def expire_proposals(self, current_step: int) -> list[str]:
        """Expire proposals past their deadline. Returns expired proposal IDs."""
        expired = []
        for proposal in self._proposals.values():
            if (
                proposal.state in (ProposalState.PENDING, ProposalState.COUNTER_PENDING)
                and proposal.expires_at_step is not None
                and current_step >= proposal.expires_at_step
            ):
                proposal.state = ProposalState.EXPIRED
                proposal.resolved_at_step = current_step
                expired.append(proposal.id)
        return expired

    def fulfill_agreement(self, agreement_id: str, current_step: int) -> bool:
        """Mark an agreement as fulfilled"""
        agreement = self._agreements.get(agreement_id)
        if not agreement:
            return False
        agreement.fulfilled = True
        agreement.fulfilled_at_step = current_step
        return True

    def get_pending_proposals_for_agent(self, agent_id: str) -> list[Proposal]:
        """Get all pending proposals targeting this agent"""
        return [
            p for p in self._proposals.values()
            if p.state in (ProposalState.PENDING, ProposalState.COUNTER_PENDING)
            and (p.target_id == agent_id or p.target_id is None)
            and p.proposer_id != agent_id
        ]

    def get_agent_active_agreements(self, agent_id: str) -> list[Agreement]:
        """Get all unfulfilled agreements for an agent"""
        agreement_ids = self._agent_agreements.get(agent_id, [])
        return [
            self._agreements[aid]
            for aid in agreement_ids
            if aid in self._agreements and not self._agreements[aid].fulfilled
        ]

    def get_negotiation_context(self, agent_id: str) -> dict[str, Any]:
        """Get negotiation context for an agent's prompt"""
        pending = self.get_pending_proposals_for_agent(agent_id)
        agreements = self.get_agent_active_agreements(agent_id)

        # Also get proposals this agent made that are pending response
        my_pending = [
            p for p in self._proposals.values()
            if p.proposer_id == agent_id
            and p.state in (ProposalState.PENDING, ProposalState.COUNTER_PENDING)
        ]

        return {
            "incoming_proposals": [p.to_dict() for p in pending],
            "my_pending_proposals": [p.to_dict() for p in my_pending],
            "active_agreements": [a.to_dict() for a in agreements],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposals": {pid: p.to_dict() for pid, p in self._proposals.items()},
            "agreements": {aid: a.to_dict() for aid, a in self._agreements.items()},
        }
