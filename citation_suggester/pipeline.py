from __future__ import annotations

import csv
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from citation_suggester.config import AppConfig
from citation_suggester.manuscript import build_sections
from citation_suggester.models import PaperCandidate, RankedPaper, UnifiedPaperRow
from citation_suggester.query_generation import generate_search_queries
from citation_suggester.ranker import hybrid_rank
from citation_suggester.semantic_scholar import dedupe_candidates, search_papers

logger = logging.getLogger(__name__)

RESUME_QUERIES_LATEST = "__LATEST__"


def resolve_resume_queries_dir(cfg: AppConfig, arg: str | None) -> Path | None:
    """Resolve CLI value for --resume-queries-dir; None means resume disabled."""
    if arg is None:
        return None
    if arg == RESUME_QUERIES_LATEST:
        base = cfg.project_root / "outputs" / "queries"
        if not base.is_dir():
            raise FileNotFoundError(
                f"Cannot resume from latest: queries directory missing ({base}). "
                "Run the pipeline once without --resume-queries-dir or create that folder."
            )
        candidates = [p for p in base.iterdir() if p.is_dir()]
        if not candidates:
            raise FileNotFoundError(f"No query run folders found under {base}")
        chosen = max(candidates, key=lambda p: p.stat().st_mtime)
        logger.info("Using newest query run folder (by mtime): %s", chosen)
        return chosen

    path = Path(arg).expanduser()
    if not path.is_absolute():
        path = (cfg.project_root / path).resolve()
    else:
        path = path.resolve()
    if not path.is_dir():
        raise NotADirectoryError(f"Resume queries path is not a directory: {path}")
    return path


def _load_queries_from_resume_file(
    path: Path,
    *,
    section_title: str,
    paragraph_index: int,
    cfg: AppConfig,
) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("section") != section_title:
        raise ValueError(
            f"{path}: section mismatch (file has {raw.get('section')!r}, expected {section_title!r})"
        )
    if raw.get("paragraph_index") != paragraph_index:
        raise ValueError(
            f"{path}: paragraph_index mismatch "
            f"(file has {raw.get('paragraph_index')}, expected {paragraph_index})"
        )
    qs = raw.get("queries")
    if not isinstance(qs, list):
        raise ValueError(f"{path}: expected 'queries' JSON array")
    out = [str(q).strip() for q in qs if str(q).strip()]
    out = out[: cfg.semantic_scholar.max_queries]
    return out


def _section_slug(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip()).strip("_").lower()
    return s or "section"


def _run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}_{uuid.uuid4().hex[:8]}"


def _ranked_to_jsonable(r: RankedPaper) -> dict:
    return {
        "paper_id": r.paper.paper_id,
        "title": r.paper.title,
        "link": r.paper.s2_link(),
        "year": r.paper.year,
        "citation_count": r.paper.citation_count,
        "similarity_score": r.similarity_score,
        "citation_score": r.citation_score,
        "recency_score": r.recency_score,
        "final_score": r.final_score,
    }


def run_pipeline(
    cfg: AppConfig,
    *,
    section_filter: set[str] | None = None,
    resume_queries_dir: Path | None = None,
) -> Path:
    if not cfg.input_path.is_file():
        raise FileNotFoundError(f"Manuscript not found: {cfg.input_path}")

    raw = cfg.input_path.read_text(encoding="utf-8")
    sections = build_sections(
        raw,
        exclude_sections=cfg.exclude_sections,
        paragraph_mode=cfg.paragraph_mode,
        min_paragraph_chars=cfg.min_paragraph_chars,
    )

    if section_filter is not None:
        sf = {s.strip().lower() for s in section_filter}
        sections = [s for s in sections if s.title.strip().lower() in sf]

    run_id = _run_id()
    queries_root = cfg.project_root / "outputs" / "queries" / run_id
    runs_dir = cfg.project_root / "outputs" / "runs"
    queries_root.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    if cfg.semantic_scholar.use_api_key and not cfg.semantic_scholar_api_key:
        logger.warning(
            "semantic_scholar.use_api_key is true but SEMANTIC_SCHOLAR_API_KEY is missing."
        )

    if resume_queries_dir is not None:
        logger.info("Resume mode: loading queries from %s when paragraph_*.json exists", resume_queries_dir)

    logger.info("Loading embedding model %s", cfg.embeddings.model)
    from sentence_transformers import SentenceTransformer

    encoder = SentenceTransformer(cfg.embeddings.model)

    by_paragraph: list[dict] = []

    with httpx.Client() as client:
        for sec in sections:
            slug = _section_slug(sec.title)
            sec_dir = queries_root / slug
            sec_dir.mkdir(parents=True, exist_ok=True)

            for pi, paragraph in enumerate(sec.paragraphs):
                p1 = pi + 1
                logger.info("Section %r paragraph %s", sec.title, p1)
                resume_file = (
                    (resume_queries_dir / slug / f"paragraph_{p1:03d}.json")
                    if resume_queries_dir is not None
                    else None
                )
                if resume_file is not None and resume_file.is_file():
                    queries = _load_queries_from_resume_file(
                        resume_file,
                        section_title=sec.title,
                        paragraph_index=p1,
                        cfg=cfg,
                    )
                    if not queries:
                        logger.warning(
                            "Resume file %s has no queries; generating with Gemini instead.",
                            resume_file,
                        )
                        queries = generate_search_queries(paragraph, cfg)
                    elif len(queries) < cfg.queries_per_paragraph_min:
                        logger.warning(
                            "Resume file %s has only %s queries (config min %s); using them as-is.",
                            resume_file,
                            len(queries),
                            cfg.queries_per_paragraph_min,
                        )
                else:
                    if resume_file is not None:
                        logger.info(
                            "No resume file at %s; generating queries with Gemini.",
                            resume_file,
                        )
                    queries = generate_search_queries(paragraph, cfg)

                q_path = sec_dir / f"paragraph_{p1:03d}.json"
                q_path.write_text(
                    json.dumps(
                        {
                            "section": sec.title,
                            "paragraph_index": p1,
                            "queries": queries,
                            "paragraph_excerpt": paragraph[:500],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                collected: list[PaperCandidate] = []
                for q in queries:
                    collected.extend(search_papers(client, q, cfg))

                collected = dedupe_candidates(collected)
                cap = cfg.semantic_scholar.max_results_per_paragraph
                if len(collected) > cap:
                    collected = collected[:cap]

                ranked = hybrid_rank(paragraph, collected, encoder, cfg)
                by_paragraph.append(
                    {
                        "section": sec.title,
                        "paragraph_index": p1,
                        "paragraph_ref": f"{sec.title}#{p1}",
                        "top_suggestions": [_ranked_to_jsonable(r) for r in ranked],
                    }
                )

    unified: dict[str, UnifiedPaperRow] = {}
    for block in by_paragraph:
        sec_title = block["section"]
        pref: str = block["paragraph_ref"]
        for row in block["top_suggestions"]:
            pid = row["paper_id"]
            u = unified.get(pid)
            if u is None:
                u = UnifiedPaperRow(
                    paper_id=pid,
                    title=row["title"],
                    link=row["link"],
                    citation_count=int(row["citation_count"]),
                    year=row.get("year"),
                )
                unified[pid] = u
            u.sections.add(sec_title)
            u.paragraph_refs.add(pref)

    unified_path = runs_dir / f"suggestions_unified_{run_id}.csv"
    with unified_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "paper_id",
                "title",
                "link",
                "citation_count",
                "year",
                "sections",
                "paragraph_refs",
            ]
        )
        for u in sorted(unified.values(), key=lambda x: (-x.citation_count, x.title)):
            w.writerow(
                [
                    u.paper_id,
                    u.title,
                    u.link,
                    u.citation_count,
                    u.year if u.year is not None else "",
                    ";".join(sorted(u.sections)),
                    ";".join(sorted(u.paragraph_refs)),
                ]
            )

    detail_path = runs_dir / f"suggestions_by_paragraph_{run_id}.json"
    detail_path.write_text(json.dumps(by_paragraph, indent=2), encoding="utf-8")

    meta_path = runs_dir / f"run_meta_{run_id}.json"
    meta_payload = {
        "run_id": run_id,
        "input_path": str(cfg.input_path),
        "unified_csv": str(unified_path.relative_to(cfg.project_root)),
        "by_paragraph_json": str(detail_path.relative_to(cfg.project_root)),
        "queries_dir": str(queries_root.relative_to(cfg.project_root)),
        "resume_queries_dir": (
            str(resume_queries_dir.relative_to(cfg.project_root))
            if resume_queries_dir is not None
            and resume_queries_dir.is_relative_to(cfg.project_root)
            else (str(resume_queries_dir) if resume_queries_dir else None)
        ),
    }
    meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

    logger.info("Wrote %s", unified_path)
    return unified_path
