#!/usr/bin/env python3
import json

with open("rrf_failure_analysis.json") as f:
    data = json.load(f)

worst = data["worst_queries"][:81]  # zero-hit queries

recoverable_expand_topk = []
only_ceiling = []
for e in worst:
    d = e["diagnosis"]
    found_by_index = d["missed_vec_only"] + d["missed_fts_only"] + d["missed_both_found"]
    not_found_at_all = d["missed_in_neither"]
    if found_by_index > 0 and not_found_at_all == 0:
        recoverable_expand_topk.append(e)
    elif not_found_at_all > 0 and found_by_index == 0:
        only_ceiling.append(e)

mixed = 81 - len(recoverable_expand_topk) - len(only_ceiling)

vec_only_docs  = sum(e["diagnosis"]["missed_vec_only"]    for e in worst)
fts_only_docs  = sum(e["diagnosis"]["missed_fts_only"]    for e in worst)
fusion_fail    = sum(e["diagnosis"]["missed_both_found"]  for e in worst)
not_in_either  = sum(e["diagnosis"]["missed_in_neither"]  for e in worst)
total_missed   = sum(e["num_relevant"]                    for e in worst)
recoverable    = vec_only_docs + fts_only_docs + fusion_fail

print("=" * 60)
print("IS top-100 -> top-10 TOO STRICT? Analysis")
print("=" * 60)
print(f"Zero-hit queries total: 81")
print()
print("--- Expanding final top-k (10 -> 20/50) ---")
print(f"  Queries where ALL misses were in at least one index")
print(f"  (expanding top-k WOULD recover them):          {len(recoverable_expand_topk):3d} queries")
print(f"  Queries where ALL misses were in NEITHER index")
print(f"  (expanding top-k would NOT help at all):       {len(only_ceiling):3d} queries")
print(f"  Mixed (some in index, some not):               {mixed:3d} queries")
print()
print("--- Doc-level: what caused each miss? ---")
print(f"  In vec top-100 but not top-10 (top-k too strict): {vec_only_docs:5d} docs")
print(f"  In FTS top-100 but not top-10 (top-k too strict): {fts_only_docs:5d} docs")
print(f"  In BOTH top-100, fusion buried it:                 {fusion_fail:5d} docs")
print(f"  Not in FTS nor vec top-100 (ceiling problem):      {not_in_either:5d} docs")
print(f"  Total missed docs:                                 {total_missed:5d} docs")
print()
print(f"  Recoverable by expanding top-k (10->20/50):  {recoverable} docs ({100*recoverable/total_missed:.1f}%)")
print(f"  NOT recoverable without a better retriever:  {not_in_either} docs ({100*not_in_either/total_missed:.1f}%)")
print()
print("--- Verdict ---")
print(f"  The top-10 cutoff is a minor issue ({100*recoverable/total_missed:.0f}% of missed docs).")
print(f"  The real problem is the 100-candidate ceiling: {100*not_in_either/total_missed:.0f}% of missed docs")
print(f"  were never in either index's top-100 to begin with.")
print(f"  Expanding top-k to 20 or 50 would only help {len(recoverable_expand_topk)}/81 queries.")
print(f"  To fix the other {81-len(recoverable_expand_topk)}/81, you need a better first-stage retriever.")
print("=" * 60)
