#!/usr/bin/env python3
"""
Keyword vs Semantic failure analysis.
For ALL 323 queries (not just zero-hit), break down:
  - How often did FTS5 fail to retrieve relevant docs?
  - How often did vector search fail to retrieve relevant docs?
  - Which is the weaker link?
"""
import json
from collections import defaultdict

with open("rrf_failure_analysis.json") as f:
    data = json.load(f)

all_queries = data["worst_queries"]  # all 323, sorted worst-first

# Per-query stats
fts_missed_any   = 0   # queries where FTS5 missed at least one relevant doc in top-100
vec_missed_any   = 0   # queries where vector missed at least one relevant doc in top-100
both_missed_any  = 0   # queries where BOTH missed at least one relevant doc
neither_missed   = 0   # queries where both found all relevant docs in top-100

fts_total_missed = 0   # total relevant docs not in FTS top-100
vec_total_missed = 0   # total relevant docs not in vec top-100

fts_returned_nothing = 0  # queries where FTS returned zero results
vec_returned_nothing = 0  # queries where vec returned zero results (shouldn't happen)

total_relevant_docs  = 0
total_queries        = len(all_queries)

# For each missed doc, was it in FTS? in vec? in neither?
doc_in_fts_not_vec   = 0  # FTS found it, vec did not
doc_in_vec_not_fts   = 0  # vec found it, FTS did not  
doc_in_neither       = 0  # neither found it
doc_in_both_but_missed = 0  # both found it but RRF still ranked below top-10

for e in all_queries:
    d = e["diagnosis"]
    relevant = e["num_relevant"]
    total_relevant_docs += relevant

    if not d["fts5_returned_any"]:
        fts_returned_nothing += 1

    if not d["vec_returned_any"]:
        vec_returned_nothing += 1

    # missed_relevant contains all relevant docs NOT in top-10
    missed = e["missed_relevant"]

    # Count per-doc failures
    for m in missed:
        if m["in_fts100"] and not m["in_vec100"]:
            doc_in_fts_not_vec += 1
            vec_total_missed += 1
        elif m["in_vec100"] and not m["in_fts100"]:
            doc_in_vec_not_fts += 1
            fts_total_missed += 1
        elif not m["in_fts100"] and not m["in_vec100"]:
            doc_in_neither += 1
            fts_total_missed += 1
            vec_total_missed += 1
        elif m["in_fts100"] and m["in_vec100"]:
            doc_in_both_but_missed += 1  # fusion failure

    # Per-query: did FTS miss any relevant doc in top-100?
    fts_missed_count = sum(1 for m in missed if not m["in_fts100"])
    vec_missed_count = sum(1 for m in missed if not m["in_vec100"])

    if fts_missed_count > 0:
        fts_missed_any += 1
    if vec_missed_count > 0:
        vec_missed_any += 1
    if fts_missed_count > 0 and vec_missed_count > 0:
        both_missed_any += 1
    if fts_missed_count == 0 and vec_missed_count == 0:
        neither_missed += 1

print("=" * 65)
print("KEYWORD vs SEMANTIC: Which Fails More?")
print("=" * 65)
print(f"Total queries:         {total_queries}")
print(f"Total relevant docs:   {total_relevant_docs}")
print()
print("--- Query-level (did the index miss ANY relevant doc?) ---")
print(f"  FTS5 returned nothing at all:          {fts_returned_nothing:4d} / {total_queries} ({100*fts_returned_nothing/total_queries:.0f}%)")
print(f"  Vec returned nothing at all:           {vec_returned_nothing:4d} / {total_queries} ({100*vec_returned_nothing/total_queries:.0f}%)")
print()
print(f"  FTS5 missed >=1 relevant doc in top-100: {fts_missed_any:4d} / {total_queries} ({100*fts_missed_any/total_queries:.0f}%)")
print(f"  Vec  missed >=1 relevant doc in top-100: {vec_missed_any:4d} / {total_queries} ({100*vec_missed_any/total_queries:.0f}%)")
print(f"  Both missed >=1 relevant doc:            {both_missed_any:4d} / {total_queries} ({100*both_missed_any/total_queries:.0f}%)")
print(f"  Neither missed any (both complete):      {neither_missed:4d} / {total_queries} ({100*neither_missed/total_queries:.0f}%)")
print()
print("--- Doc-level (where was each missed relevant doc?) ---")
total_missed_docs = doc_in_fts_not_vec + doc_in_vec_not_fts + doc_in_neither + doc_in_both_but_missed
print(f"  Doc in FTS top-100 but NOT vec top-100:   {doc_in_fts_not_vec:5d}  (vec failed, FTS helped)")
print(f"  Doc in vec top-100 but NOT FTS top-100:   {doc_in_vec_not_fts:5d}  (FTS failed, vec helped)")
print(f"  Doc in NEITHER FTS nor vec top-100:       {doc_in_neither:5d}  (both failed)")
print(f"  Doc in BOTH top-100 (fusion fail):        {doc_in_both_but_missed:5d}  (retrieval ok, fusion failed)")
print(f"  Total missed docs:                        {total_missed_docs:5d}")
print()
print("--- Retriever recall comparison ---")
print(f"  Total relevant docs FTS5 failed to retrieve in top-100: {fts_total_missed:5d} ({100*fts_total_missed/total_relevant_docs:.1f}% of all relevant)")
print(f"  Total relevant docs vec  failed to retrieve in top-100: {vec_total_missed:5d} ({100*vec_total_missed/total_relevant_docs:.1f}% of all relevant)")
print()
print("--- Verdict ---")
if fts_total_missed > vec_total_missed:
    gap = fts_total_missed - vec_total_missed
    print(f"  FTS5 (keyword) missed MORE: {fts_total_missed} vs {vec_total_missed} docs")
    print(f"  Keyword search is the weaker link by {gap} docs")
else:
    gap = vec_total_missed - fts_total_missed
    print(f"  Vector (semantic) missed MORE: {vec_total_missed} vs {fts_total_missed} docs")
    print(f"  Semantic search is the weaker link by {gap} docs")
print("=" * 65)
