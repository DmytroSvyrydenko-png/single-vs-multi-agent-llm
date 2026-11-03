# Single-Agent vs Multi-Agent LLM Systems

Bachelor's thesis project (Riga Technical University, Computer Systems, 2026).

When is it worth splitting an LLM agent into several cooperating agents, and when does one agent do the job better? This project answers that with a controlled experiment: the same tasks, the same model, the same tools, run through a **single-agent (SAS)** and a **multi-agent (MAS)** architecture, and compared on **quality, latency, token usage, cost and stability**.

## Why no RAG

This project deliberately does **not** use RAG (no embeddings, no vector store, no retrieval pipeline). The goal is to compare *agent architectures*, not retrieval quality. With RAG in the loop, a difference in results could come from what the retriever happened to return. Instead, both architectures get the same plain, deterministic tools: list companies, read a filing section, read a full document, keyword search, a line-range window, and a calculator. Any difference in outcome comes from how the agents are organised.

## Data

Annual reports (Form 10-K) of 16 large US tech companies, including Apple, Microsoft, NVIDIA, Intel, AMD, Alphabet, Amazon and Meta. Documents are stored locally as text and can also be fetched from SEC EDGAR via `edgartools`.

## Scenarios

Three scenarios, each with three difficulty levels (9 tasks), each run **5 times per architecture** (90 runs in total). Every task has a numeric ground-truth answer.

| Scenario | What it stresses | Single agent | Multi-agent design |
|---|---|---|---|
| **Context pollution** | Reading 3-5 full documents into one context | One agent reads every document and calculates | Orchestrator + a reader agent per document (returns only the relevant facts) + a mathematician agent |
| **Parallelization** | Researching 3-7 companies independently | One agent researches companies in turn (parallel tool calls allowed) | Orchestrator dispatches up to 5 researcher agents in parallel |
| **Verification** | Multi-step calculations with traps (sign errors, tax reconciliation) | One agent searches, calculates and answers | Orchestrator + executor (extracts values, drafts answer) + verifier (checks and corrects, no document access) |

## Evaluation

The evaluation design is one of the thesis's own contributions: a multi-dimensional score in which quality acts as a multiplier, so an unreliable result cannot be compensated by speed or low cost.

- **Quality**: deterministic. The agent must return JSON; each value is compared with the ground truth. The task scores 1 only if every value matches. An earlier version used an LLM-as-a-judge (several models through OpenRouter); it was replaced by exact matching, since every task has an unambiguous numeric answer. The old judge code is kept in `evaluation/judge.py` for reference.
- **Latency, tokens, cost**: measured per run.
- **Stability**: based on the coefficient of variation of quality, time and cost across the 5 runs.
- **Overall score** (quality-gated, so a wrong answer cannot win on speed or price):

```
Overall = Quality * (0.50 + 0.20 * Stability + 0.15 * TimeEfficiency + 0.15 * CostEfficiency)
```

All runs are traced with **Opik** (agent steps, tool calls, tokens, cost).

## Results

Mean per scenario over all variants and runs:

| Scenario | Architecture | Quality | Time (s) | Tokens | Cost (USD) |
|---|---|---|---|---|---|
| Context pollution | MAS | **1.00** | 46.0 | **289k** | **0.23** |
| Context pollution | SAS | 0.67 | **17.2** | 645k | 0.48 |
| Parallelization | MAS | 0.80 | 27.3 | **136k** | **0.11** |
| Parallelization | SAS | **0.93** | **26.1** | 526k | 0.40 |
| Verification | MAS | 1.00 | 52.3 | 124k | 0.11 |
| Verification | SAS | 1.00 | **20.2** | **72k** | **0.05** |

Overall score by scenario:

| Scenario | MAS | SAS | Better |
|---|---|---|---|
| Context pollution | 0.88 | 0.59 | MAS |
| Parallelization | 0.76 | 0.80 | SAS |
| Verification | 0.80 | 0.96 | SAS |
| **Overall** | **0.81** | 0.79 | MAS (narrowly) |

### Key findings

- **Context isolation can be a necessity, not an optimisation.** With enough documents, the single agent hit the limit of its context window and could not finish the task. Reader sub-agents, each working in a clean context and passing only the relevant facts to the orchestrator, kept quality at 1.00. Context isolation should be considered at design time, not added later.
- **In multi-agent systems, the weak point was aggregation, not the sub-agents.** In the parallelization scenario the researcher agents returned correct results; the errors appeared when the orchestrator combined them, and grew with the number of sources. Precise orchestrator instructions on result format and aggregation matter more than the parallel mechanism itself.
- **A verifier agent only pays off when the base system is unreliable.** When the single agent already solved the task correctly, adding a verifier did not improve quality but raised cost up to almost 4x. Add one only for a known failure category with clearly defined checks; otherwise it creates an illusion of verification.
- **Parallel sub-agents save tokens, not time.** Each sub-agent works in a clean context instead of accumulating every previous source, so with 3 companies the multi-agent system was about 4x cheaper in tokens and cost at identical quality, while latency did not improve.

## Architecture guidelines

1. **Start with a single agent.** Add multi-agent complexity only for a concrete structural reason and a measurable gain in quality, stability or resource efficiency.
2. **Use context isolation** when a task has to read far more information than the final answer needs.
3. **Use parallel sub-agents** for independent subtasks, for resource efficiency, and invest in precise aggregation instructions.
4. **Add a verifier** only when the base system is reliably wrong in a specific error category and the checks can be stated clearly.

The thesis applies these guidelines to four typical enterprise agent use cases (IT service management, knowledge synthesis, code review, sales support). Its conclusion: the architecture choice depends on the task's structure (context volume, divisibility, verifiability of the result), not on the industry or the number of steps.

### Limitations

The tasks have well-defined numeric answers, and the experiment used one model configuration. Open-ended tasks and newer models may shift the boundary between the two architectures.

## Stack

- Python, **OpenAI Agents SDK** (agents, agents-as-tools, parallel tool calls)
- Model: `gpt-5.4-mini` (reasoning effort: medium), same for every agent
- **Opik** for tracing
- `edgartools` (SEC EDGAR), pandas, Jupyter

## Project structure

```
config.py                 model, scenarios, number of runs, paths
src/single_agent.py       single-agent runner
src/multi_agent.py        multi-agent designs per scenario
src/tools.py              document tools and a safe calculator
src/opik_setup.py         Opik tracing setup
evaluation/tasks.yaml     tasks, prompts and ground-truth answers
evaluation/evaluator.py   deterministic evaluation
evaluation/judge.py       earlier LLM-as-a-judge (no longer used)
notebooks/                run the experiment, aggregate results, download filings
results/                  raw per-run results and aggregated tables
```

## Running

```bash
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY and, optionally, Opik credentials
```

Then run `notebooks/run_experiment.ipynb` to execute the tasks and `notebooks/aggregate_results.ipynb` to build the tables.

Note: some aggregated table headers are in Latvian, the language of the thesis.