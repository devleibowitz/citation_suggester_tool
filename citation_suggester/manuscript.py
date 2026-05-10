from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Section:
    title: str
    paragraphs: list[str]


def _split_paragraphs_blankline(body: str) -> list[str]:
    parts = re.split(r"\n\s*\n", body)
    return [p.strip() for p in parts if p.strip()]


def _split_paragraphs_line(body: str) -> list[str]:
    return [ln.strip() for ln in body.splitlines() if ln.strip()]


def _split_paragraphs_auto(body: str) -> list[str]:
    blocks = _split_paragraphs_blankline(body)
    if len(blocks) >= 2:
        return blocks
    return _split_paragraphs_line(body)


def split_paragraphs(body: str, mode: str) -> list[str]:
    mode = (mode or "auto").lower()
    if mode == "blankline":
        return _split_paragraphs_blankline(body)
    if mode == "line":
        return _split_paragraphs_line(body)
    if mode == "auto":
        return _split_paragraphs_auto(body)
    raise ValueError(f"Unknown paragraph_mode: {mode!r}")


def parse_sections(raw: str) -> list[tuple[str, str]]:
    """Split manuscript into (section_title, body) pairs. Headers are lines starting with '# '."""
    current_title: str | None = None
    current_lines: list[str] = []
    sections: list[tuple[str, str]] = []

    for line in raw.splitlines():
        if line.startswith("# "):
            if current_title is not None:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line[2:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title is not None:
        sections.append((current_title, "\n".join(current_lines).strip()))

    return sections


def build_sections(
    raw: str,
    *,
    exclude_sections: list[str],
    paragraph_mode: str,
    min_paragraph_chars: int,
) -> list[Section]:
    exclude = {e.strip().lower() for e in exclude_sections}
    out: list[Section] = []
    for title, body in parse_sections(raw):
        if title.strip().lower() in exclude:
            continue
        paras = split_paragraphs(body, paragraph_mode)
        filtered = [p for p in paras if len(p) >= min_paragraph_chars]
        if filtered:
            out.append(Section(title=title, paragraphs=filtered))
    return out
