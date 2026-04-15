import sys
from dataclasses import dataclass
from pathlib import Path

from agents import Agent, Runner, trace, ModelSettings, RunConfig
from openai.types.shared import Reasoning

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.opik_setup import ensure_opik_configured
from src.tools import list_available_companies, get_filing_sections, read_section


@dataclass
class AgentResult:
    scenario: str
    architecture: str
    answer: str
    error: str | None = None


def _make_agent(name: str, instructions: str, use_tools: bool = True) -> Agent:
    return Agent(
        name=name,
        instructions=instructions,
        model=config.AGENT_MODEL,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=config.AGENT_REASONING_EFFORT)
        ),
        tools=[list_available_companies, get_filing_sections, read_section] if use_tools else [],
    )


async def run_single_agent(scenario: str, system_prompt: str, question: str) -> AgentResult:
    ensure_opik_configured()
    agent = _make_agent("SingleAgent", system_prompt)

    try:
        with trace(f"{scenario}__single_agent"):
            result = await Runner.run(
                agent,
                question,
                run_config=RunConfig(workflow_name=f"{scenario}__single_agent"),
            )
        return AgentResult(scenario=scenario, architecture="single_agent", answer=result.final_output)

    except Exception as e:
        return AgentResult(scenario=scenario, architecture="single_agent", answer="", error=str(e))
