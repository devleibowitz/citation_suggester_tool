from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from citation_suggester.config import AppConfig


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_search_queries(paragraph: str, cfg: AppConfig) -> list[str]:
    if not cfg.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set (required for Gemini query generation).")

    llm = ChatGoogleGenerativeAI(
        model=cfg.gemini.model,
        temperature=cfg.gemini.temperature,
        google_api_key=cfg.google_api_key,
    )

    nmin, nmax = cfg.queries_per_paragraph_min, cfg.queries_per_paragraph_max
    system = SystemMessage(
        content=(
            "You assist with academic literature search. Respond with a single JSON array only, "
            "no markdown or commentary. Each array element is one search query string "
            f"(between {nmin} and {nmax} queries inclusive), suitable for Semantic Scholar: "
            "concise keyword or short natural-language queries, no numbering."
        )
    )
    human = HumanMessage(
        content=(
            "From the following manuscript paragraph, produce distinct search queries "
            "to find peer-reviewed papers to cite.\n\n---\n"
            f"{paragraph}\n---"
        )
    )

    msg = llm.invoke([system, human])
    raw = msg.content if isinstance(msg.content, str) else str(msg.content)
    data = json.loads(_strip_code_fence(raw))
    if not isinstance(data, list):
        raise ValueError("Expected JSON array of query strings from the model.")

    queries = [str(q).strip() for q in data if str(q).strip()]
    if len(queries) < nmin:
        raise ValueError(f"Model returned fewer than {nmin} queries: {queries!r}")
    queries = queries[:nmax]
    queries = queries[: cfg.semantic_scholar.max_queries]
    return queries
