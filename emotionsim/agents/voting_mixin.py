from dataclasses import dataclass
from collections import defaultdict
from emotionsim.acp.message import PersonalityProfile


@dataclass
class VoteResult:
    winner: str
    confidence: float
    breakdown: dict
    total_votes: int


class GroupDecisionMixin:
    """Provides ensemble voting for agent group decisions."""

    def tally_votes(
        self,
        votes: dict[str, dict],
        personalities: dict[str, PersonalityProfile] | None = None,
        trust_levels: dict[tuple[str, str], float] | None = None,
    ) -> VoteResult:
        effective_weights: dict[str, float] = {}
        for agent_name, vote_data in votes.items():
            base_weight = vote_data["weight"]
            if personalities and agent_name in personalities:
                p = personalities[agent_name]
                leadership_mod = p.leadership / 5.0
                stress_penalty = 1.0 - (p.stress / 20.0)
                base_weight *= leadership_mod * stress_penalty
            if trust_levels:
                trust_scores = [
                    trust_levels.get((other, agent_name), 0.5)
                    for other in votes if other != agent_name
                ]
                if trust_scores:
                    avg_trust = sum(trust_scores) / len(trust_scores)
                    base_weight *= (0.5 + avg_trust)
            effective_weights[agent_name] = base_weight

        choice_weights: dict[str, dict] = defaultdict(
            lambda: {"weight": 0.0, "votes": 0, "agents": []}
        )
        for agent_name, vote_data in votes.items():
            choice = vote_data["choice"]
            choice_weights[choice]["weight"] += effective_weights[agent_name]
            choice_weights[choice]["votes"] += 1
            choice_weights[choice]["agents"].append(agent_name)

        if not choice_weights:
            return VoteResult(winner="", confidence=0.0, breakdown={}, total_votes=0)

        winner_key = max(choice_weights, key=lambda k: choice_weights[k]["weight"])
        total_weight = sum(c["weight"] for c in choice_weights.values())
        confidence = (
            choice_weights[winner_key]["weight"] / total_weight
            if total_weight > 0
            else 0.0
        )

        return VoteResult(
            winner=winner_key,
            confidence=confidence,
            breakdown=dict(choice_weights),
            total_votes=len(votes),
        )
