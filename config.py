import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPIK_API_KEY = os.getenv("OPIK_API_KEY")
OPIK_WORKSPACE = os.getenv("OPIK_WORKSPACE")
OPIK_URL = os.getenv("OPIK_URL")
OPIK_PROJECT_NAME = os.getenv("OPIK_PROJECT_NAME", "single-vs-multi-agent-llm")

AGENT_MODEL = "gpt-5.4-mini-2026-03-17"
AGENT_REASONING_EFFORT = "medium"

# JUDGE_MODELS = [
#     "openai/gpt-5.4-mini",
#     "anthropic/claude-haiku-4.5",
#     "google/gemini-3-flash-preview",
# ]

ROOT_DIR = Path(__file__).parent
DOCUMENTS_DIR = ROOT_DIR / "documents"

SCENARIO_CONTEXT_POLLUTION = "context_pollution"
SCENARIO_PARALLELIZATION = "parallelization"
SCENARIO_VERIFICATION = "verification"

N_RUNS = 1

RESULTS_DIR = ROOT_DIR / "results"
RAW_RESULTS_DIR = RESULTS_DIR / "raw"
AGGREGATED_RESULTS_DIR = RESULTS_DIR / "aggregated"
