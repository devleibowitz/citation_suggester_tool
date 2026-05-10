from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PaperCandidate:
    paper_id: str
    title: str
    abstract: str | None
    year: int | None
    citation_count: int
    url: str | None

    def s2_link(self) -> str:
        if self.url:
            return self.url
        return f"https://www.semanticscholar.org/paper/{self.paper_id}"


@dataclass
class RankedPaper:
    paper: PaperCandidate
    similarity_score: float
    citation_score: float
    recency_score: float
    final_score: float


@dataclass
class UnifiedPaperRow:
    paper_id: str
    title: str
    link: str
    citation_count: int
    year: int | None
    sections: set[str] = field(default_factory=set)
    paragraph_refs: set[str] = field(default_factory=set)
