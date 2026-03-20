#!/usr/bin/env python3
"""Generate RRF_FAILURE_ANALYSIS.md from rrf_failure_analysis.json"""

import json

with open("rrf_failure_analysis.json") as f:
    data = json.load(f)

worst = data["worst_queries"][:81]  # bottom 25%, all NDCG=0

lines = []
lines.append("# RRF Zero-Hit Failures — Bottom 25% Queries")
lines.append("")
lines.append("All 81 queries below scored **NDCG@10 = 0** — RRF retrieved zero relevant documents in the top-10.")
lines.append("")
lines.append("Dataset: BEIR NFCorpus (3,633 medical/nutrition documents)")
lines.append("")
lines.append("---")
lines.append("")
lines.append("## Summary")
lines.append("")
lines.append("| Stat | Value |")
lines.append("|---|---|")
lines.append("| Queries with NDCG=0 | 81 / 323 (25%) |")
total_missed = sum(e["num_relevant"] for e in worst)
lines.append(f"| Total relevant docs missed | {total_missed} |")
fts_nothing = sum(1 for e in worst if not e["diagnosis"]["fts5_returned_any"])
lines.append(f"| FTS5 returned nothing | {fts_nothing} queries |")
in_neither = sum(e["diagnosis"]["missed_in_neither"] for e in worst)
lines.append(f"| Relevant docs not in FTS nor vec top-100 | {in_neither} |")
vec_only = sum(e["diagnosis"]["missed_vec_only"] for e in worst)
lines.append(f"| Relevant docs in vec top-100 only (RRF ranked too low) | {vec_only} |")
fusion_fail = sum(e["diagnosis"]["missed_both_found"] for e in worst)
lines.append(f"| Relevant docs in both top-100 (pure fusion fail) | {fusion_fail} |")
lines.append("")
lines.append("---")
lines.append("")
lines.append("## Root Cause Categories")
lines.append("")
lines.append("### Category A — FTS5 returned nothing (query vocabulary not in index)")
lines.append("Query terms have no keyword match in the corpus. Vector search alone was not enough to surface relevant docs.")
lines.append("")
lines.append("### Category B — Relevant docs outside both top-100 candidates")
lines.append("Neither FTS5 nor vector search retrieved the relevant doc in their top-100.")
lines.append("RRF never had a chance — the hard ceiling of 100 candidates per index is the bottleneck.")
lines.append("")
lines.append("### Category C — Fusion score too low (both indexes found it, RRF buried it)")
lines.append("Both FTS5 and vector found the doc, but the combined RRF score ranked it below position 10.")
lines.append("")
lines.append("---")
lines.append("")
lines.append("## All 81 Zero-Hit Queries")
lines.append("")
lines.append("| # | Query | Relevant Docs | FTS5 hit | Vec hit | Missed in neither | Vec-only misses | Fusion fails |")
lines.append("|---|---|---|---|---|---|---|---|")

for i, e in enumerate(worst, 1):
    d = e["diagnosis"]
    fts_hit = "yes" if d["fts5_returned_any"] else "**NO**"
    vec_hit = "yes" if d["vec_returned_any"] else "**NO**"
    q = e["query_text"].replace("|", "\\|")
    lines.append(
        f"| {i} | {q} | {e['num_relevant']} | {fts_hit} | {vec_hit} "
        f"| {d['missed_in_neither']} | {d['missed_vec_only']} | {d['missed_both_found']} |"
    )

lines.append("")
lines.append("---")
lines.append("")
lines.append("## Detailed Breakdown — Top 20 by Relevant Doc Count")
lines.append("")
lines.append("These are the queries with the most relevant docs that RRF completely failed on.")
lines.append("")

detailed = sorted(worst, key=lambda x: x["num_relevant"], reverse=True)[:20]

for e in detailed:
    d = e["diagnosis"]
    q = e["query_text"]
    fts_str = "yes" if d["fts5_returned_any"] else "NO - vocabulary mismatch"
    lines.append(f'### "{q}"')
    lines.append("")
    lines.append(f"- **Relevant docs in corpus:** {e['num_relevant']}")
    lines.append("- **NDCG@10:** 0.0")
    lines.append(f"- **FTS5 returned results:** {fts_str}")
    lines.append(f"- **Missed - not in FTS nor vec top-100:** {d['missed_in_neither']}")
    lines.append(f"- **Missed - vec top-100 only (RRF ranked too low):** {d['missed_vec_only']}")
    lines.append(f"- **Missed - in both top-100 (fusion failed):** {d['missed_both_found']}")
    lines.append("")
    lines.append("**Top-5 retrieved by RRF (all irrelevant):**")
    lines.append("")
    for j, doc in enumerate(e["top10_retrieved"][:5], 1):
        snippet = doc["text"].replace("\n", " ").strip()[:160]
        lines.append(f"{j}. *(score={doc['score']})* {snippet}...")
    lines.append("")
    if e["missed_relevant"]:
        lines.append("**Sample missed relevant docs:**")
        lines.append("")
        for m in e["missed_relevant"][:3]:
            snippet = m["text"].replace("\n", " ").strip()[:160]
            loc = []
            if m["in_fts100"]:
                loc.append("FTS top-100")
            if m["in_vec100"]:
                loc.append("vec top-100")
            if not loc:
                loc.append("neither index")
            lines.append(f"- [rel={m['relevance']}, found in: {', '.join(loc)}] {snippet}...")
        lines.append("")
    lines.append("---")
    lines.append("")

with open("RRF_FAILURE_ANALYSIS.md", "w") as f:
    f.write("\n".join(lines))

print("Done: RRF_FAILURE_ANALYSIS.md")
