"""LLM-judge evaluator — scores output with an OpenAI or Anthropic model."""

from __future__ import annotations

import re
from typing import Any

from cobalt.evaluator import registry
from cobalt.types import EvalContext, EvalResult
from cobalt.utils.template import render


def _is_anthropic_model(model: str) -> bool:
    return model.startswith("claude")


def _build_prompt(config: dict[str, Any], context: EvalContext) -> str:
    """Render the judge prompt template with context variables."""
    ctx_dict: dict[str, Any] = {
        "output": context.output,
        "metadata": context.metadata,
        **context.item,
    }
    return render(config["prompt"], ctx_dict)


def _parse_boolean(text: str) -> tuple[float, str]:
    """Return (score, reason) for boolean scoring."""
    upper = text.upper()
    if "PASS" in upper:
        score = 1.0
    elif "FAIL" in upper:
        score = 0.0
    else:
        # Try to find a number
        nums = re.findall(r"\b([01](?:\.\d+)?|\d+(?:\.\d+)?)\b", text)
        score = float(nums[0]) if nums else 0.0
    return score, text.strip()


def _parse_scale(text: str) -> tuple[float, str]:
    """Return (score, reason) for scale (0–1) scoring."""
    nums = re.findall(r"\b(0(?:\.\d+)?|1(?:\.0+)?|\d+(?:\.\d+)?)\b", text)
    for raw in nums:
        value = float(raw)
        if 0.0 <= value <= 1.0:
            return value, text.strip()
    return 0.0, text.strip()


async def _call_openai(prompt: str, model: str, api_key: str | None) -> str:
    import openai

    client = openai.AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    return response.choices[0].message.content or ""


async def _call_anthropic(prompt: str, model: str, api_key: str | None) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text if response.content else ""


async def _llm_judge_handler(
    config: dict[str, Any],
    context: EvalContext,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> EvalResult:
    judge_model = config.get("model") or model or "gpt-4o-mini"
    scoring = config.get("scoring", "boolean")
    use_cot = config.get("chain_of_thought", scoring == "boolean")

    user_prompt = _build_prompt(config, context)

    if use_cot:
        system = (
            "You are an AI evaluator. Think step by step, then conclude with "
            "PASS or FAIL (for boolean) or a score 0.0–1.0 (for scale)."
        )
        full_prompt = f"{system}\n\n{user_prompt}"
    else:
        full_prompt = user_prompt

    if _is_anthropic_model(judge_model):
        raw = await _call_anthropic(full_prompt, judge_model, api_key)
    else:
        raw = await _call_openai(full_prompt, judge_model, api_key)

    if scoring == "boolean":
        score, reason = _parse_boolean(raw)
    else:
        score, reason = _parse_scale(raw)

    return EvalResult(
        score=score,
        reason=reason,
        chain_of_thought=raw if use_cot else None,
    )


registry.register("llm-judge", _llm_judge_handler)
