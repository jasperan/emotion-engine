"""Structured-output enforcement for LLM agent responses (Step 3).

Defines Pydantic schemas for the three agent response types (act / think /
plan), a content validator that tolerates common LLM output sloppiness
(markdown fences, prose around JSON), and the schema instructions used for
retry-with-feedback.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, Field, ValidationError

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ActResponse(BaseModel):
    """Cinematic act-phase output (new schema) + legacy action format.

    The ``actions``/``message``/``state_changes``/``reasoning`` fields accept
    the pre-cinematic format so both shapes validate.
    """

    action: str = Field(default="", description="Stage direction, third person")
    speech: str | None = Field(default=None, description="Spoken dialogue or null")
    thought: str | None = Field(default=None, description="Private inner thought")
    emotion: str | None = Field(default=None, description="Dominant emotion")
    move_to: str | None = Field(default=None, description="Location to move to or null")
    stress_level: int | None = Field(default=None, ge=1, le=10)

    # Legacy / parallel format
    actions: list[dict[str, Any]] | None = None
    message: dict[str, Any] | None = None
    state_changes: dict[str, Any] | None = None
    reasoning: str | None = None


class ThinkResponse(BaseModel):
    """THINK-phase situation assessment."""

    urgency: str = Field(default="medium", pattern="^(high|medium|low)$")
    assessment: str = Field(default="Situation unclear.", min_length=1)
    top_need: str = Field(default="survival", min_length=1)


class PlanResponse(BaseModel):
    """PLAN-phase action plan."""

    goal: str = Field(default="Survive", min_length=1)
    steps: list[str] = Field(default_factory=list)
    success_criteria: str = Field(default="Situation improved", min_length=1)
    fallback: str | None = None


class ReflectionResponse(BaseModel):
    """Batched self-reflection output: lessons distilled from recent activity."""

    summary: str = Field(default="", min_length=1)
    lessons: list[str] = Field(default_factory=list)
    importance: int = Field(default=5, ge=1, le=10)


class GovernanceScoreResponse(BaseModel):
    """LLM ethics-reviewer output for a flagged agent action."""

    significance: float = Field(default=0.0, ge=0.0, le=1.0)
    approved: bool = False
    note: str = Field(default="", min_length=1)


# ---------------------------------------------------------------------------
# Extraction + validation
# ---------------------------------------------------------------------------


def extract_json_text(content: str) -> str | None:
    """Extract a JSON object from raw LLM output.

    Handles: bare JSON, markdown code fences, and JSON embedded in prose.
    Returns None when no JSON object can be found.
    """
    content = (content or "").strip()
    if not content:
        return None

    if content.startswith("{") and content.endswith("}"):
        return content

    json_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if json_block:
        return json_block.group(1).strip()

    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content, re.DOTALL)
    if json_match:
        return json_match.group(0)

    return None


def validate_content(
    content: str,
    model: type[T],
) -> tuple[bool, T | None, str]:
    """Validate raw LLM content against a Pydantic model.

    Returns ``(ok, parsed, error)`` where ``error`` is a human-readable
    message suitable for retry-with-feedback, or "" on success.
    """
    json_text = extract_json_text(content)
    if json_text is None:
        return False, None, "No JSON object found in the response."

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return False, None, f"Invalid JSON: {exc}"

    try:
        parsed = model.model_validate(data)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        return False, None, f"Schema validation failed: {errors}"

    return True, parsed, ""


def schema_instructions(model: type[BaseModel]) -> str:
    """Compact JSON-schema instructions for prompt injection on retry."""
    return json.dumps(model.model_json_schema(), indent=2)
