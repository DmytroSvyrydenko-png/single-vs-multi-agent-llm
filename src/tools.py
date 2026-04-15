import os
from functools import lru_cache

from agents import function_tool
from edgar import Company, set_identity

set_identity(os.getenv("EDGAR_IDENTITY", "student@university.lv"))


COMPANIES = {
    "apple":     "AAPL",
    "nvidia":    "NVDA",
    "amd":       "AMD",
    "intel":     "INTC",
    "microsoft": "MSFT",
}


@lru_cache(maxsize=16)
def _get_tenk(ticker: str):
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    return filing.obj()


@function_tool
def list_available_companies() -> str:
    lines = ["Companies with available 10-K annual reports (SEC EDGAR):\n"]
    for name, ticker in COMPANIES.items():
        lines.append(f"  {name} (ticker: {ticker})")
    lines.append("\nUsage: get_filing_sections('name_of_company')")
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
