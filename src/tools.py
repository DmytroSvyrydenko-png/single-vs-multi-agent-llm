import os
import ast
import operator
from functools import lru_cache
from pathlib import Path

from agents import function_tool
from edgar import Company, set_identity

import config

set_identity(os.getenv("EDGAR_IDENTITY", "student@university.lv"))


COMPANIES = {
    "adobe": "ADBE",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "amd": "AMD",
    "apple": "AAPL",
    "broadcom": "AVGO",
    "cisco": "CSCO",
    "ibm": "IBM",
    "intel": "INTC",
    "meta": "META",
    "microsoft": "MSFT",
    "netflix": "NFLX",
    "nvidia": "NVDA",
    "oracle": "ORCL",
    "qualcomm": "QCOM",
    "salesforce": "CRM",
}


DOCUMENT_FILES = {
    company: config.DOCUMENTS_DIR / f"{company}_10k.txt"
    for company in COMPANIES
}


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


@lru_cache(maxsize=16)
def _get_tenk(ticker: str):
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    return filing.obj()


@function_tool
def list_available_companies() -> str:
    lines = ["Companies with available 10-K annual reports:\n"]
    for name, ticker in COMPANIES.items():
        local_status = "local document available" if DOCUMENT_FILES[name].exists() else "SEC EDGAR only"
        lines.append(f"  {name} (ticker: {ticker}; {local_status})")
    lines.append(
        "\nUsage: get_filing_sections('name_of_company'), read_section('name_of_company', 'section'), "
        "read_full_document('name_of_company'), search_document('name_of_company', 'query'), "
        "or read_document_window('name_of_company', start_line, line_count)"
    )
    return "\n".join(lines)


@function_tool
def get_filing_sections(company: str) -> str:
    company = company.lower().strip()
    if company not in COMPANIES:
        available = ", ".join(COMPANIES.keys())
        return f"ERROR: Unknown company '{company}'. Available: {available}"

    try:
        tenk = _get_tenk(COMPANIES[company])
        sections = tenk.sections
        lines = [f"Sections in {company.capitalize()}'s 10-K:\n"]
        for s in sections:
            lines.append(f"  {s}")
        lines.append("\nUsage: read_section('name_of_company', 'name_of_section')")
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR fetching sections for '{company}': {e}"


@function_tool
def read_section(company: str, item: str) -> str:
    company = company.lower().strip()
    if company not in COMPANIES:
        available = ", ".join(COMPANIES.keys())
        return f"ERROR: Unknown company '{company}'. Available: {available}"

    try:
        tenk = _get_tenk(COMPANIES[company])
        content = str(tenk[item])
        if not content or content.strip() in ("None", ""):
            return f"ERROR: Section '{item}' is empty or not available for {company}."
        return content
    except Exception as e:
        return f"ERROR reading '{item}' for '{company}': {e}"


@function_tool
def read_full_document(company: str) -> str:
    company = company.lower().strip()
    if company not in COMPANIES:
        available = ", ".join(COMPANIES.keys())
        return f"ERROR: Unknown company '{company}'. Available: {available}"

    path = DOCUMENT_FILES[company]
    if not path.exists():
        return f"ERROR: Local document is not available for '{company}' at {path}."

    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"ERROR reading local document for '{company}': {e}"


def _read_local_lines(company: str):
    company = company.lower().strip()
    if company not in COMPANIES:
        available = ", ".join(COMPANIES.keys())
        return None, f"ERROR: Unknown company '{company}'. Available: {available}"

    path = DOCUMENT_FILES[company]
    if not path.exists():
        return None, f"ERROR: Local document is not available for '{company}' at {path}."

    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines(), None
    except Exception as e:
        return None, f"ERROR reading local document for '{company}': {e}"


@function_tool
def search_document(company: str, query: str, max_results: int = 8) -> str:
    lines, error = _read_local_lines(company)
    if error:
        return error

    query_terms = [term.strip(" ,.;:()[]{}\"'").lower() for term in query.split()]
    query_terms = [term for term in query_terms if len(term) >= 2]
    if not query_terms:
        return (
            "ERROR: Empty query. Use 2-6 specific keywords from the task, "
            "for example 'H20 charge', 'operating income', or 'State Aid Decision'."
        )

    max_results = max(1, min(int(max_results), 20))
    scored_matches = []
    for idx, line in enumerate(lines, start=1):
        start = max(1, idx - 2)
        end = min(len(lines), idx + 2)
        window_text = " ".join(lines[line_no - 1] for line_no in range(start, end + 1)).lower()
        score = sum(1 for term in query_terms if term in window_text)
        if score == 0:
            continue
        if len(query_terms) > 1 and score == 1:
            continue
        snippet = "\n".join(
            f"{line_no}: {lines[line_no - 1]}"
            for line_no in range(start, end + 1)
        )
        scored_matches.append((score, idx, snippet))

    if not scored_matches:
        return f"No matches found in {company} for query: {query!r}"

    scored_matches.sort(key=lambda item: (-item[0], item[1]))
    matches = [snippet for _, _, snippet in scored_matches[:max_results]]
    return "\n\n---\n\n".join(matches)


@function_tool
def read_document_window(company: str, start_line: int, line_count: int = 60) -> str:
    lines, error = _read_local_lines(company)
    if error:
        return error

    start_line = max(1, int(start_line))
    line_count = max(1, min(int(line_count), 160))
    end_line = min(len(lines), start_line + line_count - 1)
    if start_line > len(lines):
        return f"ERROR: start_line {start_line} is beyond the end of {company}'s document ({len(lines)} lines)."

    return "\n".join(
        f"{line_no}: {lines[line_no - 1]}"
        for line_no in range(start_line, end_line + 1)
    )


def _eval_math_node(node):
    if isinstance(node, ast.Expression):
        return _eval_math_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_math_node(node.left), _eval_math_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_math_node(node.operand))
    raise ValueError("Only numeric expressions with +, -, *, / and parentheses are allowed.")


@function_tool
def calculator(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_math_node(tree)
        return str(float(result))
    except Exception as e:
        return f"ERROR calculating expression: {e}"
