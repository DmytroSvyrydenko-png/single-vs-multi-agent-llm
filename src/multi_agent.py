import sys
from dataclasses import dataclass
from pathlib import Path

from agents import Agent, Runner, trace, ModelSettings, RunConfig
from openai.types.shared import Reasoning

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.opik_setup import ensure_opik_configured
from src.tools import list_available_companies, get_filing_sections, read_section
from src.single_agent import AgentResult


@dataclass
class MultiAgentPrompts:
    orchestrator: str
    reader: str = "" # context_pollution        
    researcher: str = "" # parallelization    
    executor: str = "" # verification      
    verifier: str = "" # verification      
    companies: list = None # parallelization


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


# Context Pollution
async def _run_context_pollution(prompts: MultiAgentPrompts, question: str) -> str:
    reader = _make_agent("Reader", prompts.reader)
    orchestrator = _make_agent("Orchestrator", prompts.orchestrator, use_tools=False)
    orchestrator.tools = [
        reader.as_tool(
            tool_name="read_and_extract",
            tool_description=(
                "Read the financial document and extract only the sections "
                "relevant to the question. Returns a focused summary."
            ),
        )
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
    for company in companies:
        agent = _make_agent(
            name=f"{company} Researcher",
            instructions=(
                f"You are the {company} Researcher. "
                f"Research ONLY {company.lower()} — do NOT read any other company's documents.\n\n"
                + prompts.researcher
            ),
        )
        researchers.append((company, agent))

    orchestrator = _make_agent("Orchestrator", prompts.orchestrator, use_tools=False)
    orchestrator.tools = [
        agent.as_tool(
            tool_name=f"research_{company.lower()}",
            tool_description=f"Research {company}'s data from their 10-K filing.",
        )
        for company, agent in researchers
    ]
    result = await Runner.run(
        orchestrator,
        question,
        run_config=RunConfig(workflow_name="parallelization__multi_agent"),
    )
    return result.final_output


# Verification
async def _run_verification(prompts: MultiAgentPrompts, question: str) -> str:
    executor = _make_agent("Executor", prompts.executor)
    verifier = _make_agent("Verifier", prompts.verifier)

    orchestrator = _make_agent("Orchestrator", prompts.orchestrator, use_tools=False)
    orchestrator.tools = [
        executor.as_tool(
            tool_name="extract_financial_data",
            tool_description=(
                "Extract structured financial data from the source document. "
                "Returns a draft answer in the required structured format."
            ),
        ),
        verifier.as_tool(
            tool_name="verify_and_correct",
            tool_description=(
                "Independently verify all factual claims in a draft answer "
                "against source documents and return a corrected final answer."
            ),
        ),
    ]
    result = await Runner.run(
        orchestrator,
        question,
        run_config=RunConfig(workflow_name="verification__multi_agent"),
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
