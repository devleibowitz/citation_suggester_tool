from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Smart citation suggester for manuscript drafts.")
    parser.add_argument(
        "--config",
        default="config/citation_suggester.yaml",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--sections",
        nargs="*",
        default=None,
        help="If set, only process these section titles (case-insensitive match).",
    )
    parser.add_argument(
        "--resume-queries-dir",
        nargs="?",
        const="__LATEST__",
        default=None,
        metavar="DIR",
        help=(
            "Reuse saved outputs/queries/.../paragraph_*.json query lists (skip Gemini when present). "
            "If DIR is omitted, use the newest outputs/queries/<run_id> folder (by modification time). "
            "Paths are relative to project root unless absolute. Missing JSON files fall back to Gemini."
        ),
    )
    args = parser.parse_args()

    from citation_suggester.config import load_config
    from citation_suggester.pipeline import resolve_resume_queries_dir, run_pipeline

    cfg = load_config(args.config)
    section_filter = (
        {s.strip().lower() for s in args.sections} if args.sections else None
    )
    resume_queries_dir = resolve_resume_queries_dir(cfg, args.resume_queries_dir)
    try:
        out = run_pipeline(
            cfg,
            section_filter=section_filter,
            resume_queries_dir=resume_queries_dir,
        )
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        sys.exit(1)
    logger.info("Done. Unified CSV: %s", out)


if __name__ == "__main__":
    main()
