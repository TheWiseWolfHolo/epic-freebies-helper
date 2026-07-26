"""Construct hCaptcha agents with the configured provider injected."""

from __future__ import annotations

from typing import Any

from hcaptcha_challenger.agent import AgentV
from loguru import logger

from llm.provider import create_llm_provider

_REASONER_ATTRIBUTES = (
    "_challenge_router",
    "_image_classifier",
    "_spatial_path_reasoner",
    "_spatial_point_reasoner",
)


def create_hcaptcha_agent(*, page: Any, settings: Any) -> AgentV:
    """Create AgentV while containing its private provider seam in one place."""
    agent = AgentV(page=page, agent_config=settings)
    provider = create_llm_provider(settings)
    for attribute in _REASONER_ATTRIBUTES:
        reasoner = getattr(agent.robotic_arm, attribute)
        if not hasattr(reasoner, "_provider"):
            raise RuntimeError(
                f"hcaptcha-challenger integration changed: {attribute} has no provider seam"
            )
        reasoner._provider = provider
    logger.info(
        "hCaptcha LLM provider ready | protocol={} | model={}",
        settings.LLM_PROVIDER,
        settings.LLM_MODEL,
    )
    return agent
