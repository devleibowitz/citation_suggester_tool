# citation_suggester

`citation_suggester` helps you turn a manuscript draft into citation suggestions. It reads your manuscript section-by-section, generates search queries with Gemini, fetches papers from Semantic Scholar, and ranks results with a hybrid score (semantic similarity + citation count + recency).

The tool writes outputs to `outputs/` as:
- `.csv` for a unified bibliography suggestion list
- `.json` for detailed per-paragraph suggestions
- `.json` for saved generated queries and run metadata

---

## 1) Set up the repo

### Prerequisites
- Python `3.12+`
- [Poetry](https://python-poetry.org/docs/#installation)

### Install

```bash
git clone <your-repo-url>
cd citation_suggester_tool
poetry install
```

Verify the CLI:

```bash
poetry run cite-suggest --help
```

---

## 2) Add your manuscript (plain text)

Put your manuscript in the `papers/` folder, for example:

```text
papers/my_manuscript.txt
```

Important format rule:
- Start each section with a heading line that begins with `# ` (hash + space)
- Example section headers:
  - `# Introduction`
  - `# Methods`
  - `# Results`
  - `# Discussion`

This is required because section parsing is based on lines that start with `# `.

---

## 3) Configure environment variables and API keys

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Then set your keys:

```dotenv
GOOGLE_API_KEY=your_google_ai_studio_key
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_key_optional
```

Where to get keys:
- `GOOGLE_API_KEY` (required): [Google AI Studio API key](https://aistudio.google.com/app/apikey)
- `SEMANTIC_SCHOLAR_API_KEY` (optional): [Semantic Scholar API key form](https://www.semanticscholar.org/product/api#api-key-form)

Notes:
- `GOOGLE_API_KEY` is required for Gemini query generation.
- `SEMANTIC_SCHOLAR_API_KEY` is only required if `semantic_scholar.use_api_key: true`.
- Do not commit `.env`.

---

## 4) Configure `config/citation_suggester.yaml`

By default, the CLI reads:

```text
config/citation_suggester.yaml
```

Example:

```yaml
input_path: papers/my_manuscript.txt

exclude_sections:
  - references
  - appendix

paragraph_mode: auto
min_paragraph_chars: 40

queries_per_paragraph_min: 3
queries_per_paragraph_max: 5
top_k: 5

semantic_scholar:
  papers_per_query: 10
  max_queries: 5
  request_timeout_seconds: 30
  max_results_per_paragraph: 60
  use_api_key: false

gemini:
  model: gemini-2.0-flash
  temperature: 0.2

embeddings:
  model: all-MiniLM-L6-v2

ranking:
  weight_similarity: 0.35
  weight_citations: 0.50
  weight_recency: 0.15
```

### Parameter walkthrough

- `input_path`  
  Path to one manuscript `.txt` file.

- `exclude_sections`  
  Skip specific section titles (case-insensitive), such as `references`.

- `paragraph_mode`  
  Paragraph splitting strategy: `auto`, `blankline`, or `line`.

- `min_paragraph_chars`  
  Ignore very short paragraphs.

- `queries_per_paragraph_min` and `queries_per_paragraph_max`  
  Min/max number of queries Gemini should generate per paragraph.

- `top_k`  
  Final number of ranked suggestions kept per paragraph.

- `semantic_scholar.papers_per_query`  
  Number of papers requested per query.

- `semantic_scholar.max_queries`  
  Hard cap on total queries used per paragraph.

- `semantic_scholar.request_timeout_seconds`  
  API request timeout.

- `semantic_scholar.max_results_per_paragraph`  
  Maximum deduplicated candidate papers kept before final ranking.

- `semantic_scholar.use_api_key`  
  If `true`, adds `SEMANTIC_SCHOLAR_API_KEY` to Semantic Scholar requests.

- `gemini.model`, `gemini.temperature`  
  Gemini model and generation temperature for query creation.

- `embeddings.model`  
  Sentence-transformers embedding model for semantic similarity.

- `ranking.weight_similarity`, `ranking.weight_citations`, `ranking.weight_recency`  
  Relative weights for the final ranking score.

---

## 5) Run the tool

Run using default config path:

```bash
poetry run cite-suggest
```

Run with a custom config path:

```bash
poetry run cite-suggest --config path/to/citation_suggester.yaml
```

Optional flags:
- `--sections "Introduction" "Discussion"` to process only selected sections
- `--resume-queries-dir` to reuse the newest saved query run
- `--resume-queries-dir <dir>` to reuse a specific `outputs/queries/<run_id>` directory

---

## 6) Output files explained

Each run writes files under `outputs/`:

- `outputs/runs/suggestions_unified_<run_id>.csv`  
  One row per suggested paper with:
  - `paper_id`, `title`, `link`, `citation_count`, `year`
  - `sections` where it appears
  - `paragraph_refs` (for example `Introduction#2`)

- `outputs/runs/suggestions_by_paragraph_<run_id>.json`  
  Ranked suggestions per paragraph, including similarity/citation/recency/final scores.

- `outputs/runs/run_meta_<run_id>.json`  
  Run metadata including input path and generated file paths.

- `outputs/queries/<run_id>/<section_slug>/paragraph_XXX.json`  
  Saved queries per paragraph (used by resume mode).

---

## Troubleshooting

- **`GOOGLE_API_KEY` missing**  
  Add it in `.env` and rerun.

- **No sections detected**  
  Make sure your section headers start with `# ` exactly.

- **Sparse or weak suggestions**  
  Increase `semantic_scholar.papers_per_query`, `semantic_scholar.max_queries`, or adjust ranking weights.

- **Semantic Scholar 403/429**  
  Retry later, reduce request volume, or enable API-key mode with a valid `SEMANTIC_SCHOLAR_API_KEY`.
