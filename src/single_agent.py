import sys
from dataclasses import dataclass
from pathlib import Path

from agents import Agent, Runner, trace, ModelSettings, RunConfig
from openai.types.shared import Reasoning

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.opik_setup import ensure_opik_configured
from src.tools import (
    calculator,
    get_filing_sections,
    list_available_companies,
    read_document_window,
    read_full_document,
    read_section,
    search_document,
)


@dataclass
class AgentResult:
    scenario: str
    architecture: str
    answer: str
    error: str | None = None


def _scenario_tools(scenario: str):
    if scenario == config.SCENARIO_CONTEXT_POLLUTION:
        return [list_available_companies, read_full_document, calculator]
    if scenario == config.SCENARIO_PARALLELIZATION:
        return [list_available_companies, get_filing_sections, read_section, calculator]
    if scenario == config.SCENARIO_VERIFICATION:
        return [list_available_companies, search_document, read_document_window, calculator]
    return [list_available_companies, get_filing_sections, read_section, calculator]


def _make_agent(
    name: str,
    instructions: str,
    tools: list | None = None,
    parallel_tool_calls: bool = True,
) -> Agent:
    return Agent(
        name=name,
        instructions=instructions,
        model=config.AGENT_MODEL,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=config.AGENT_REASONING_EFFORT),
            parallel_tool_calls=parallel_tool_calls,
        ),
        tools=tools if tools is not None else [],
    )


async def run_single_agent(scenario: str, system_prompt: str, question: str) -> AgentResult:
    ensure_opik_configured()
    agent = _make_agent(
        "SingleAgent",
        system_prompt,
        tools=_scenario_tools(scenario),
        parallel_tool_calls=scenario == config.SCENARIO_PARALLELIZATION,
    )

    try:
        with trace(f"{scenario}__single_agent"):
            result = await Runner.run(
                agent,
                question,
                run_config=RunConfig(workflow_name=f"{scenario}__single_agent"),
                max_turns=25 if scenario == config.SCENARIO_VERIFICATION else 10,
            )
        return AgentResult(scenario=scenario, architecture="single_agent", answer=result.final_output)

    except Exception as e:
        return AgentResult(scenario=scenario, architecture="single_agent", answer="", error=str(e))
