import json
from dataclasses import dataclass


@dataclass
class EvalResult:
    scenario: str
    architecture: str
    quality_score: float  # 0.0 or 1.0
    reason: str
    failure_reason: str | None = None
    error: str | None = None


def evaluate(
    scenario: str,
    architecture: str,
    reference_answer: str,
    agent_answer: str,
) -> EvalResult:
    """
    Compare agent answer against ground truth numerically.

    Both reference and agent answers are expected to be JSON objects
    with numeric values. Comparison is done as float equality.
    Returns quality_score=1.0 if all values match, 0.0 otherwise.
    """
    try:
        ground_truth = json.loads(reference_answer)
    except Exception as e:
        failure_reason = f"Failed to parse ground truth: {e}"
        return EvalResult(scenario=scenario, architecture=architecture,
                          quality_score=0.0, reason=failure_reason,
                          failure_reason=failure_reason, error=failure_reason)

    try:
        agent_json = json.loads(agent_answer)
    except Exception:
        failure_reason = f"Agent response is not valid JSON: {agent_answer!r}"
        return EvalResult(scenario=scenario, architecture=architecture,
                          quality_score=0.0, reason=failure_reason,
                          failure_reason=failure_reason)

    mismatches = []
    for key, expected in ground_truth.items():
        if key not in agent_json:
            mismatches.append(f"'{key}' is missing")
            continue
        try:
            agent_val = float(str(agent_json[key]).replace(",", ""))
            expected_val = float(expected)
        except (ValueError, TypeError):
            mismatches.append(f"'{key}': could not parse agent value {agent_json[key]!r} as float")
            continue
        if agent_val != expected_val:
            mismatches.append(f"'{key}': expected {expected_val}, got {agent_val}")

    if mismatches:
        failure_reason = "; ".join(mismatches)
        return EvalResult(scenario=scenario, architecture=architecture,
                          quality_score=0.0, reason=failure_reason,
                          failure_reason=failure_reason)

    return EvalResult(scenario=scenario, architecture=architecture,
                      quality_score=1.0, reason="All values match")
