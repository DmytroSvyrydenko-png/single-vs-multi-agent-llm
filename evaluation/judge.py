# An old file no longer used in the project.
# It was created for the previous non-static results assessment system,
# which required an LLM as a judge.

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import openai

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.opik_setup import track_openai_client

_PROMPT_TEMPLATE = (Path(__file__).parent / "judge_prompt.md").read_text(encoding="utf-8")
_SCHEMA = json.loads((Path(__file__).parent / "judge_schema.json").read_text(encoding="utf-8"))


@dataclass
class JudgeScore:
    model: str
    score: int
    reason: str


@dataclass
class JudgeResult:
    scenario: str
    architecture: str
    scores: list[JudgeScore]
    quality_score: float
    error: str | None = None


def _call_judge(model: str, prompt: str) -> JudgeScore:
    client = track_openai_client(
        openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.OPENROUTER_API_KEY,
        )
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "judge_score",
                "strict": True,
                "schema": _SCHEMA,
            },
        },
    )

    data = json.loads(response.choices[0].message.content)
    score = int(data["score"])
    if score not in (0, 1):
        raise ValueError(f"Judge score out of range for {model}: {score}")

    reason = str(data["reason"]).strip()
    if not reason:
        raise ValueError(f"Missing judge reason for {model}")

    return JudgeScore(model=model, score=score, reason=reason)


def evaluate(
    scenario: str,
    architecture: str,
    question: str,
    reference_answer: str,
    agent_answer: str,
) -> JudgeResult:
    prompt = _PROMPT_TEMPLATE.format(
        question=question,
        ground_truth=reference_answer,
        agent_answer=agent_answer,
    )

    scores: list[JudgeScore] = []
    errors: list[str] = []

    for model in config.JUDGE_MODELS:
        try:
            scores.append(_call_judge(model, prompt))
        except Exception as e:
            errors.append(f"{model}: {e}")

    if not scores:
        return JudgeResult(
            scenario=scenario,
            architecture=architecture,
            scores=[],
            quality_score=0.0,
            error="; ".join(errors),
        )

    quality_score = sum(s.score for s in scores) / len(scores)

    return JudgeResult(
        scenario=scenario,
        architecture=architecture,
        scores=scores,
        quality_score=round(quality_score, 3),
        error="; ".join(errors) if errors else None,
    )
