"""StubLLMClient: deterministic, offline LLM client for the eval harness.

Routes responses by system prompt (think / plan / act / reflect / governance /
evaluate) so full simulation runs execute headlessly with zero network calls.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse


def _act_json() -> str:
    return json.dumps({
        "action": "They move decisively toward the safest nearby location.",
        "speech": "We need to move now and stick together!",
        "thought": "The situation is getting worse, we must act.",
        "emotion": "fear",
        "move_to": None,
        "stress_level": 6,
    })


def _think_json() -> str:
    return json.dumps({
        "urgency": "medium",
        "assessment": "Conditions are worsening but manageable for now.",
        "top_need": "shelter",
    })


def _plan_json() -> str:
    return json.dumps({
        "goal": "Reach safety and help others",
        "steps": ["Move toward high ground", "Check on nearby survivors"],
        "success_criteria": "Everyone is safe",
        "fallback": "Stay put and wait",
    })


def _reflect_json() -> str:
    return json.dumps({
        "summary": "Acting together improves our chances.",
        "lessons": ["Coordinate before moving", "Check on the vulnerable first"],
        "importance": 7,
    })


def _governance_json() -> str:
    return json.dumps({
        "significance": 0.2,
        "approved": True,
        "note": "Reasonable action under the circumstances.",
    })


def _evaluate_json() -> str:
    return json.dumps({
        "state_changes": {
            "scores": {
                "cooperation": 7,
                "ethics": 7,
                "strategy": 6,
                "emotional_coherence": 6,
                "leadership": 6,
                "empathy": 7,
                "overall": 7,
            }
        },
        "reasoning": "Stub evaluation for offline runs.",
    })


class StubLLMClient(LLMClient):
    """Deterministic offline client returning valid JSON for every phase."""

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system: str | None = None,
        json_mode: bool = False,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        sys_text = system or ""
        if "analyzing a situation" in sys_text:
            content = _think_json()
        elif "creating an action plan" in sys_text:
            content = _plan_json()
        elif "reflecting on what just happened" in sys_text:
            content = _reflect_json()
        elif "ethics reviewer" in sys_text:
            content = _governance_json()
        elif "AI Simulation Evaluator" in sys_text:
            content = _evaluate_json()
        else:
            content = _act_json()
        return LLMResponse(content=content, raw_response={"stub": True}, usage={})

    async def health_check(self) -> bool:
        return True

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return "StubLLMClient()"
