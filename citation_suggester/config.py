from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class SemanticScholarConfig:
    """When use_api_key is False (default), calls are unauthenticated direct GETs to the public Graph API."""

    papers_per_query: int = 10
    max_queries: int = 5
    request_timeout_seconds: float = 30.0
    max_results_per_paragraph: int = 60
    use_api_key: bool = False


@dataclass
class GeminiConfig:
    model: str = "gemini-2.0-flash"
    temperature: float = 0.2


@dataclass
class EmbeddingsConfig:
    model: str = "all-MiniLM-L6-v2"


@dataclass
class RankingConfig:
    weight_similarity: float = 0.35
    weight_citations: float = 0.50
    weight_recency: float = 0.15


@dataclass
class AppConfig:
    input_path: Path
    project_root: Path
    exclude_sections: list[str]
    paragraph_mode: str
    min_paragraph_chars: int
    queries_per_paragraph_min: int
    queries_per_paragraph_max: int
    top_k: int
    semantic_scholar: SemanticScholarConfig
    gemini: GeminiConfig
    embeddings: EmbeddingsConfig
    ranking: RankingConfig
    semantic_scholar_api_key: str | None
    google_api_key: str | None


def _as_path(base: Path, p: str | Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _strip_optional_env(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped if stripped else None


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(config_path: str | Path) -> AppConfig:
    load_dotenv()
    config_path = Path(config_path).resolve()
    raw = _load_yaml(config_path)

    project_root_raw = raw.get("project_root")
    if project_root_raw:
        project_root = Path(project_root_raw).resolve()
    else:
        project_root = config_path.parent.parent.resolve()

    s2 = raw.get("semantic_scholar") or {}
    gem = raw.get("gemini") or {}
    emb = raw.get("embeddings") or {}
    rk = raw.get("ranking") or {}

    return AppConfig(
        input_path=_as_path(project_root, raw["input_path"]),
        project_root=project_root,
        exclude_sections=list(raw.get("exclude_sections") or []),
        paragraph_mode=str(raw.get("paragraph_mode") or "auto"),
        min_paragraph_chars=int(raw.get("min_paragraph_chars") or 40),
        queries_per_paragraph_min=int(raw.get("queries_per_paragraph_min") or 3),
        queries_per_paragraph_max=int(raw.get("queries_per_paragraph_max") or 5),
        top_k=int(raw.get("top_k") or 5),
        semantic_scholar=SemanticScholarConfig(
            papers_per_query=int(s2.get("papers_per_query") or 10),
            max_queries=int(s2.get("max_queries") or 5),
            request_timeout_seconds=float(s2.get("request_timeout_seconds") or 30.0),
            max_results_per_paragraph=int(s2.get("max_results_per_paragraph") or 60),
            use_api_key=bool(s2.get("use_api_key", False)),
        ),
        gemini=GeminiConfig(
            model=str(gem.get("model") or "gemini-2.0-flash"),
            temperature=float(gem.get("temperature") or 0.2),
        ),
        embeddings=EmbeddingsConfig(model=str(emb.get("model") or "all-MiniLM-L6-v2")),
        ranking=RankingConfig(
            weight_similarity=float(rk.get("weight_similarity") or 0.35),
            weight_citations=float(rk.get("weight_citations") or 0.50),
            weight_recency=float(rk.get("weight_recency") or 0.15),
        ),
        semantic_scholar_api_key=_strip_optional_env("SEMANTIC_SCHOLAR_API_KEY"),
        google_api_key=os.environ.get("GOOGLE_API_KEY") or None,
    )
