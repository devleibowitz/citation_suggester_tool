# citation_suggester

`citation_suggester` helps you build a bibliography from your manuscript text.  
You drop in a plain-text manuscript, configure a few options, and the tool suggests relevant papers you can review and cite.  
The output is written to the `outputs/` folder in machine-readable (`.json`) and human-readable (`.csv`) formats, including ranked citation suggestions and formatted bibliography entries based on your selected style. Each row in the output csv has a title paper, link, citation count, section in your manuscript to which it was ranked highly for, and the paragraph number within that section where you should consider inserting it in.

---

## 1) Set up the repository

### Prerequisites
- Python `3.12+`
- [Poetry](https://python-poetry.org/docs/#installation)

### Clone and install

```bash
git clone <your-repo-url>
cd citation_suggester_tool
poetry install
```

This installs the project and the CLI command:

```bash
poetry run cite-suggest --help
```

---

## 2) Add your manuscript (plain text)

Put your manuscript as a `.txt` file in the `papers/` folder:

```text
papers/
  my_manuscript.txt
```

Tips:
- Use plain UTF-8 text (`.txt`).
- Start each manuscript section with a hashtag heading (for example `# Introduction`, `# Methods`, `# Discussion`).
- Keep section headings in your manuscript; that usually improves retrieval quality.
- If you have multiple manuscripts, place all of them in `papers/`.

---

## 3) Configure environment variables and API keys

The project includes `.env.example`. Copy it to `.env`:

```bash
cp .env.example .env
```

Then edit `.env`:

```dotenv
GOOGLE_API_KEY=your_google_ai_studio_key
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_key_optional
```

### Where to get keys
- `GOOGLE_API_KEY` (required): create one in [Google AI Studio](https://aistudio.google.com/app/apikey)
- `SEMANTIC_SCHOLAR_API_KEY` (optional): request from [Semantic Scholar API](https://www.semanticscholar.org/product/api#api-key-form)

Notes:
- If your config enables Semantic Scholar authenticated usage (`semantic_scholar.use_api_key: true`), set `SEMANTIC_SCHOLAR_API_KEY`.
- Never commit your `.env` file.

---

## 4) Set up the config file

Create a file named `citation_suggester.yaml` in the repo root.

Example:

```yaml
input:
  papers_dir: "papers"
  file_glob: "*.txt"

output:
  output_dir: "outputs"
  write_json: true
  write_markdown: true

retrieval:
  top_k: 25
  min_relevance_score: 0.3

embedding:
  model_name: "sentence-transformers/all-MiniLM-L6-v2"

llm:
  provider: "google"
  model: "gemini-1.5-flash"
  temperature: 0.2

semantic_scholar:
  enabled: true
  use_api_key: false
  max_results_per_query: 20

bibliography:
  style: "apa"
  max_suggestions: 30
  include_abstract_snippets: true
```

### Parameter walkthrough

- `input.papers_dir`  
  Folder containing your manuscript `.txt` files.

- `input.file_glob`  
  Pattern used to pick files from `papers/` (for example `*.txt`).

- `output.output_dir`  
  Folder where generated bibliography suggestions are written.

- `retrieval.top_k`  
  Number of candidate papers fetched before final ranking.

- `retrieval.min_relevance_score`  
  Filters low-confidence matches; increase for stricter suggestions.

- `embedding.model_name`  
  Embedding model used for semantic matching.

- `llm.provider`, `llm.model`, `llm.temperature`  
  Controls the language model used for ranking/formatting suggestions.

- `semantic_scholar.enabled`  
  Turns Semantic Scholar querying on/off.

- `semantic_scholar.use_api_key`  
  Set `true` to use `SEMANTIC_SCHOLAR_API_KEY` from `.env`.

- `semantic_scholar.max_results_per_query`  
  How many API results to collect per query.

- `bibliography.style`  
  Output citation style (for example `apa`, `mla`, `chicago`).

- `bibliography.max_suggestions`  
  Maximum bibliography entries to return.

---

## 5) Run the tool

Typical run:

```bash
poetry run cite-suggest
```

If your CLI supports explicit config flags in your local version, use:

```bash
poetry run cite-suggest --config citation_suggester.yaml
```

Then check the `outputs/` folder for generated files.

---

## 6) Recommended first run checklist

- `.env` exists and contains a valid `GOOGLE_API_KEY`
- `papers/` has at least one `.txt` manuscript file
- `citation_suggester.yaml` exists and points to correct folders
- `poetry run cite-suggest` completes without auth/config errors

---

## Troubleshooting

- **No suggestions returned**  
  Lower `retrieval.min_relevance_score` and/or increase `retrieval.top_k`.

- **Authentication errors**  
  Recheck `.env` keys and ensure there are no extra quotes/spaces.

- **Nothing happens / no files produced**  
  Confirm manuscript files are in `papers/` and match `input.file_glob`.

- **Semantic Scholar limits**  
  Add `SEMANTIC_SCHOLAR_API_KEY` and set `semantic_scholar.use_api_key: true`.

---

If you want, the next improvement can be adding a sample manuscript and a sample output file so first-time users can verify expected behavior in under 2 minutes.
