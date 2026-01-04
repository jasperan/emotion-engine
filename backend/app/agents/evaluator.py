"""Evaluation Agent - scores completed runs"""
from typing import Any

from app.agents.base import Agent


class EvaluationAgent(Agent):
    """
    Agent that evaluates completed simulation runs.
    Generates scores and narrative analysis of agent behavior.
    """
    
    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Evaluator",
        model_id: str = "llama3.2",
        provider: str = "ollama",
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            role="evaluator",
            model_id=model_id,
            provider=provider,
            goals=[
                "Objectively assess agent performance",
                "Identify patterns of cooperation and conflict",
                "Generate actionable insights",
            ],
        )
    
    def get_system_prompt(self) -> str:
        """Generate system prompt for evaluation"""
        return """You are an AI Simulation Evaluator analyzing a completed disaster scenario run.

Your task is to objectively evaluate the agents' collective and individual performance.

Evaluation Criteria (score each 1-10):
1. COOPERATION: How well did agents work together?
2. ETHICS: Were moral decisions handled appropriately?
3. STRATEGY: How effective were survival decisions?
4. EMOTIONAL_COHERENCE: Did agents stay in character?
5. LEADERSHIP: Did natural leaders emerge appropriately?
6. EMPATHY: Did agents help those in need?

Output your evaluation as JSON:
{
    "actions": [],
    "message": null,
    "state_changes": {
        "scores": {
            "cooperation": <1-10>,
            "ethics": <1-10>,
            "strategy": <1-10>,
            "emotional_coherence": <1-10>,
            "leadership": <1-10>,
            "empathy": <1-10>,
            "overall": <1-10>
        },
        "narrative": "<2-3 paragraph narrative evaluation>",
        "highlights": [
            "<notable positive moment>",
            "<notable challenge overcome>"
        ],
        "concerns": [
            "<any concerning behaviors>"
        ],
        "recommendations": [
            "<suggestions for future runs>"
        ]
    },
    "reasoning": "<your evaluation methodology>"
}

Be fair, specific, and constructive in your evaluation."""
    
    def build_context(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
    ) -> str:
        """Build context from run history for evaluation"""
        # Run summary
        total_steps = world_state.get("total_steps", 0)
        final_hazard = world_state.get("hazard_level", 0)
        agents_summary = world_state.get("agents_summary", {})
        
        context = f"""Simulation Run Complete - Evaluation Required

Run Summary:
- Total Steps: {total_steps}
- Final Hazard Level: {final_hazard}/10
- Outcome: {world_state.get('outcome', 'Unknown')}

Agent Final States:
"""
        
        for agent_name, state in agents_summary.items():
            context += f"""
{agent_name}:
  - Final Health: {state.get('health', '?')}/10
  - Final Stress: {state.get('stress_level', '?')}/10
  - Actions Taken: {state.get('action_count', 0)}
  - Messages Sent: {state.get('message_count', 0)}
  - Key Decisions: {state.get('key_decisions', [])}
"""
        
        # Sample of key messages (summarized)
        context += "\nKey Moments from the Simulation:\n"
        key_messages = world_state.get("key_moments", messages[-20:])
        for msg in key_messages:
            sender = msg.get("from_agent", "System")
            content = msg.get("content", "")
            step = msg.get("step_index", "?")
            context += f"[Step {step}] {sender}: {content[:150]}...\n"
        
        context += """
Based on this run data, provide a comprehensive evaluation.
Score each criterion and explain your reasoning."""
        
        return context
    
    async def evaluate_run(
        self,
        run_summary: dict[str, Any],
        all_messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Evaluate a completed run.
        
        Args:
            run_summary: Summary of the run including agent states
            all_messages: All messages from the run
            
        Returns:
            Evaluation results with scores and narrative
        """
        response = await self.tick(run_summary, all_messages)
        
        return {
            "scores": response.state_changes.get("scores", {}),
            "narrative": response.state_changes.get("narrative", ""),
            "highlights": response.state_changes.get("highlights", []),
            "concerns": response.state_changes.get("concerns", []),
            "recommendations": response.state_changes.get("recommendations", []),
        }

