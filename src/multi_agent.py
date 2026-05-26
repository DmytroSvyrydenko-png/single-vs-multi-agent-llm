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
from src.single_agent import AgentResult


@dataclass
class MultiAgentPrompts:
    orchestrator: str
    reader: str = "" # context_pollution        
    mathematician: str = "" # context_pollution
    researcher: str = "" # parallelization    
    executor: str = "" # verification      
    verifier: str = "" # verification      
    companies: list = None # parallelization


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


# Context Pollution
async def _run_context_pollution(prompts: MultiAgentPrompts, question: str) -> str:
    reader = _make_agent(
        "DocumentReader",
        prompts.reader,
        tools=[read_full_document],
        parallel_tool_calls=False,
    )
    mathematician = _make_agent(
        "Mathematician",
        prompts.mathematician,
        tools=[calculator],
        parallel_tool_calls=False,
    )
    orchestrator = _make_agent(
        "Orchestrator",
        prompts.orchestrator,
        tools=[list_available_companies],
        parallel_tool_calls=False,
    )
    orchestrator.tools = [
        list_available_companies,
        reader.as_tool(
            tool_name="read_full_document_and_extract",
            tool_description=(
                "Read exactly one specified local 10-K document and extract focused facts relevant to the question. "
                "Call this tool separately for each company. Returns a concise summary with source company name and numeric candidates."
            ),
        ),
        mathematician.as_tool(
            tool_name="calculate_financial_metrics",
            tool_description=(
                "Calculate requested financial metrics from extracted numeric candidates. "
                "Use this after document facts have been collected."
            ),
        ),
    ]
    result = await Runner.run(
        orchestrator,
        question,
        run_config=RunConfig(workflow_name="context_pollution__multi_agent"),
    )
    return result.final_output


# Parallelization
async def _run_parallelization(prompts: MultiAgentPrompts, question: str) -> str:
    companies = prompts.companies if prompts.companies else ["Nvidia", "AMD", "Intel"]
    researchers = []
    worker_count = min(5, max(1, len(companies)))
    for worker_index in range(worker_count):
        agent = _make_agent(
            name=f"Researcher {worker_index + 1}",
            instructions=(
                "You are a parallel financial researcher. "
                "Research only the company or company subset assigned by the orchestrator. "
                "Use filing sections, extract raw numbers, and do not perform final cross-company ranking unless asked.\n\n"
                + prompts.researcher
            ),
            tools=[get_filing_sections, read_section],
        )
        researchers.append((worker_index + 1, agent))

    orchestrator = _make_agent(
        "Orchestrator",
        prompts.orchestrator,
        tools=[list_available_companies, calculator],
    )
    batch_tools = [
        agent.as_tool(
            tool_name=f"research_batch_{worker_index}",
            tool_description=(
                "Research an assigned batch of companies from their 10-K filings. "
                "Call all needed research_batch tools in parallel in a single turn when the batches are independent."
            ),
        )
        for worker_index, agent in researchers
    ]
    orchestrator.tools = [list_available_companies, calculator, *batch_tools]
    result = await Runner.run(
        orchestrator,
        question,
        run_config=RunConfig(workflow_name="parallelization__multi_agent"),
    )
    return result.final_output


# Verification
async def _run_verification(prompts: MultiAgentPrompts, question: str) -> str:
    executor = _make_agent(
        "Executor",
        prompts.executor,
        tools=[list_available_companies, search_document, read_document_window, calculator],
        parallel_tool_calls=False,
    )
    verifier = _make_agent(
        "Verifier",
        prompts.verifier,
        tools=[calculator],
        parallel_tool_calls=False,
    )

    orchestrator = _make_agent("Orchestrator", prompts.orchestrator, tools=[], parallel_tool_calls=False)
    orchestrator.tools = [
        executor.as_tool(
            tool_name="extract_financial_data",
            tool_description=(
                "Search local 10-K documents, extract raw values, calculate draft metrics, "
                "and return a draft answer with raw_values and formulas_used."
            ),
            max_turns=25,
        ),
        verifier.as_tool(
            tool_name="verify_and_correct",
            tool_description=(
                "Verify a draft answer using provided raw_values and formulas_used. "
                "Do not search documents. Return a corrected final JSON answer."
            ),
            max_turns=8,
        ),
    ]
    result = await Runner.run(
        orchestrator,
        question,
        run_config=RunConfig(workflow_name="verification__multi_agent"),
        max_turns=15,
    )
    return result.final_output


async def run_multi_agent(scenario: str, prompts: MultiAgentPrompts, question: str) -> AgentResult:
    try:
        ensure_opik_configured()
        with trace(f"{scenario}__multi_agent"):
            if scenario == config.SCENARIO_CONTEXT_POLLUTION:
                answer = await _run_context_pollution(prompts, question)
            elif scenario == config.SCENARIO_PARALLELIZATION:
                answer = await _run_parallelization(prompts, question)
            elif scenario == config.SCENARIO_VERIFICATION:
                answer = await _run_verification(prompts, question)
            else:
                raise ValueError(f"Unknown scenario: '{scenario}'")

        return AgentResult(scenario=scenario, architecture="multi_agent", answer=answer)

    except Exception as e:
        return AgentResult(scenario=scenario, architecture="multi_agent", answer="", error=str(e))
