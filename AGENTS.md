# AGENTS.md

## Cursor Cloud specific instructions

### Overview
This is a Python research project investigating hybrid retrieval strategies (keyword + vector search) for AI agent memory systems. There are **no long-running services** — the codebase consists of benchmark scripts, analysis tools, and plotting utilities that run against pre-computed SQLite databases.

### Key scripts
- `hybrid_retriever.py` — Core hybrid retrieval engine (runs standalone with no DB required)
- `scripts/benchmark_cascaded.py` — Main benchmark comparing cascaded vs RRF retrieval on BEIR NFCorpus
- `scripts/benchmark_beir_real.py` — RRF vs interleaved benchmark with real embeddings
- `scripts/plot_research_results.py` — Generates publication-quality figures in `figures/`
- `scripts/cascaded_retrieval.py` — Cascaded 3-stage retrieval implementation (imported by benchmark scripts)

### Running benchmarks
Most benchmark scripts require the pre-computed `beir_nfcorpus.db` (19MB SQLite file committed to the repo). Example:
```
python3 scripts/benchmark_cascaded.py --dataset nfcorpus
```
Some scripts (e.g., `scripts/compare_rrf_vs_interleaved.py`, `scripts/benchmark_baseline.py`) reference a local OpenClaw database at `~/.openclaw/memory/main.sqlite` which does **not** exist in the cloud environment. These scripts will fail with `FileNotFoundError` — this is expected.

### Dependencies
`requirements.txt` only lists plotting dependencies. The full set of runtime dependencies also includes: `sentence-transformers`, `sqlite-vec`, `tqdm`. All are installed by the update script.

### Linting
No project-level linting config exists. Use `ruff check .` for linting and `pyright` for type checking. The existing codebase has ~51 ruff warnings (unused variables, import order) — these are pre-existing.

### Gotchas
- The first run of any script using `sentence-transformers` downloads the `all-MiniLM-L6-v2` model (~80MB). Subsequent runs use the cached version.
- FTS5 queries with special characters (`&`, `'`, `.`) will print warnings — this is expected behavior documented in the research findings.
- Scripts in `scripts/` use `sys.path.append` to import from sibling files; always run them from the repo root (`/workspace`).
