from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from citation_suggester.config import AppConfig
from citation_suggester.models import PaperCandidate, RankedPaper


def _min_max_norm(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    lo, hi = float(values.min()), float(values.max())
    if hi - lo < 1e-12:
        return np.full_like(values, 0.5)
    return (values - lo) / (hi - lo)


def _normalize_weights(ws: tuple[float, float, float]) -> tuple[float, float, float]:
    a, b, c = max(ws[0], 0.0), max(ws[1], 0.0), max(ws[2], 0.0)
    s = a + b + c
    if s < 1e-12:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return a / s, b / s, c / s


def hybrid_rank(
    paragraph: str,
    candidates: list[PaperCandidate],
    encoder: object,
    cfg: AppConfig,
) -> list[RankedPaper]:
    if not candidates:
        return []

    rk = cfg.ranking
    w_sim, w_cite, w_rec = _normalize_weights(
        (rk.weight_similarity, rk.weight_citations, rk.weight_recency)
    )

    paper_texts = [f"{p.title}\n{p.abstract or ''}" for p in candidates]
    embeddings = encoder.encode(
        [paragraph] + paper_texts,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    sims = cosine_similarity(embeddings[0:1], embeddings[1:])[0]
    sims = np.clip(sims, 0.0, 1.0)

    cite_raw = np.array([np.log1p(max(p.citation_count, 0)) for p in candidates], dtype=np.float64)
    cite_scores = _min_max_norm(cite_raw)

    years = []
    for p in candidates:
        if p.year is not None:
            years.append(float(p.year))
        else:
            years.append(np.nan)
    year_arr = np.array(years, dtype=np.float64)
    valid = np.isfinite(year_arr)
    if valid.any():
        ymin = float(year_arr[valid].min())
        ymax = float(year_arr[valid].max())
        recency = np.zeros_like(year_arr)
        if ymax - ymin < 1e-6:
            recency[valid] = 0.5
        else:
            recency[valid] = (year_arr[valid] - ymin) / (ymax - ymin)
        recency[~valid] = 0.0
    else:
        recency = np.full_like(year_arr, 0.0)

    final = w_sim * sims + w_cite * cite_scores + w_rec * recency

    ranked: list[RankedPaper] = []
    for i, p in enumerate(candidates):
        ranked.append(
            RankedPaper(
                paper=p,
                similarity_score=float(sims[i]),
                citation_score=float(cite_scores[i]),
                recency_score=float(recency[i]),
                final_score=float(final[i]),
            )
        )
    ranked.sort(key=lambda r: r.final_score, reverse=True)
    return ranked[: cfg.top_k]
