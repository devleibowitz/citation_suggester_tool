from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from citation_suggester.config import AppConfig
from citation_suggester.models import PaperCandidate

logger = logging.getLogger(__name__)

S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
# Single string (not parenthesized as a one-tuple): comma-separated field names for the Graph API.
S2_PAPER_SEARCH_FIELDS = "paperId,title,abstract,year,citationCount,url,externalIds,authors"

# Identifiable client string; some networks/API edges reject generic library defaults.
DEFAULT_S2_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; rag-coding-cite-suggest/0.1; academic paper tooling)",
}


def _paper_from_hit(hit: dict[str, Any]) -> PaperCandidate | None:
    pid = hit.get("paperId")
    if not pid:
        return None
    title = hit.get("title") or ""
    abstract = hit.get("abstract")
    year = hit.get("year")
    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = None
    cc = hit.get("citationCount")
    if cc is None:
        cc = 0
    try:
        cc = int(cc)
    except (TypeError, ValueError):
        cc = 0
    return PaperCandidate(
        paper_id=str(pid),
        title=str(title),
        abstract=str(abstract) if abstract else None,
        year=year,
        citation_count=cc,
        url=hit.get("url"),
    )


def search_papers(
    client: httpx.Client,
    query: str,
    cfg: AppConfig,
) -> list[PaperCandidate]:
    headers = dict(DEFAULT_S2_HEADERS)
    if cfg.semantic_scholar.use_api_key and cfg.semantic_scholar_api_key:
        headers["x-api-key"] = cfg.semantic_scholar_api_key

    params = {
        "query": query,
        "limit": cfg.semantic_scholar.papers_per_query,
        "fields": S2_PAPER_SEARCH_FIELDS,
    }

    backoff = 2.0
    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            r = client.get(
                S2_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=cfg.semantic_scholar.request_timeout_seconds,
            )
            if r.status_code == 429:
                wait = min(backoff, 60.0)
                logger.warning("Semantic Scholar 429; sleeping %.1fs", wait)
                time.sleep(wait)
                backoff *= 1.5
                continue
            if r.status_code == 403:
                body = (r.text or "")[:800].replace("\n", " ")
                if cfg.semantic_scholar.use_api_key:
                    logger.error(
                        "Semantic Scholar 403 (authenticated mode): invalid or rejected "
                        "SEMANTIC_SCHOLAR_API_KEY — see https://www.semanticscholar.org/product/api "
                        "— Response excerpt: %s",
                        body,
                    )
                else:
                    logger.error(
                        "Semantic Scholar 403 on public (no-key) request — often IP/rate or "
                        "edge policy; try again later, reduce request rate, or set "
                        "semantic_scholar.use_api_key: true with a valid key. Response excerpt: %s",
                        body,
                    )
                r.raise_for_status()
            r.raise_for_status()
            payload = r.json()
            data = payload.get("data") or []
            out: list[PaperCandidate] = []
            for hit in data:
                p = _paper_from_hit(hit)
                if p:
                    out.append(p)
            return out
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 403:
                raise
            last_exc = e
            logger.warning("S2 request error (%s), attempt %s", e, attempt + 1)
            time.sleep(min(backoff, 30.0))
            backoff *= 1.5
        except (httpx.HTTPError, ValueError) as e:
            last_exc = e
            logger.warning("S2 request error (%s), attempt %s", e, attempt + 1)
            time.sleep(min(backoff, 30.0))
            backoff *= 1.5

    if last_exc:
        raise last_exc
    return []


def dedupe_candidates(papers: list[PaperCandidate]) -> list[PaperCandidate]:
    seen: set[str] = set()
    out: list[PaperCandidate] = []
    for p in papers:
        if p.paper_id in seen:
            continue
        seen.add(p.paper_id)
        out.append(p)
    return out
