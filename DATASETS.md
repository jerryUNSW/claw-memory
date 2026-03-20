# Datasets for Agent Memory Retrieval Benchmarking

## Our Angle

**Problem:** OpenClaw stores agent memories in SQLite. When a user asks a question, OpenClaw must retrieve the right memory chunk from potentially thousands of stored memories. The current implementation uses RRF (BM25 keyword + vector search). Our research question is: **can hybrid retrieval be done better, faster, and more accurately in this SQLite-native setting?**

**What we are NOT doing:** We are not benchmarking general document retrieval (BEIR-style). We are benchmarking *agent memory retrieval* — finding the right episodic memory chunk when a user asks a question about past agent activity.

**Why hybrid retrieval specifically:** Pure semantic search misses exact keyword matches (names, IDs, tool calls). Pure keyword search misses paraphrased or conceptually related queries. Hybrid BM25+vector is the natural fit for agent memory, which contains both structured (tool names, file paths) and unstructured (observations, plans) content.

---

Datasets below are ordered from most to least relevant to this specific problem.

---

## Tier 1 — Agent Memory / Agentic Task Datasets (Most Relevant)

These datasets are specifically designed for agent memory evaluation, not generic IR.

---

### 1. AMA-Bench (Feb 2026) — Most relevant to our problem

- **Paper:** [AMA-Bench: Evaluating Long-Horizon Memory for Agentic Applications](https://arxiv.org/abs/2602.22769)
- **Authors:** Yujie Zhao et al.
- **Dataset:** [HuggingFace — AMA-bench/AMA-bench](https://huggingface.co/datasets/AMA-bench/AMA-bench)
- **Size:** Real-world agentic trajectories + synthetic trajectories at arbitrary scale

**What it contains:**
- Real agent-environment interaction trajectories (not human-human conversations)
- Expert-curated QA pairs for real trajectories
- Rule-based QA pairs for synthetic trajectories (scalable to any length)

**Memory task types evaluated:**
1. **Recall** — directly retrieve a specific piece of information
2. **Causal Inference** — understand cause-effect relationships across memory
3. **State Updating** — track how states change over time
4. **State Abstraction** — high-level understanding of what happened

**Key finding:** Existing memory systems fail because they are "constrained by the lossy nature of similarity-based retrieval" — directly validates our RRF failure analysis (89.9% of missed docs were outside both FTS and vector top-100).

**Why use it:** This is the closest to OpenClaw's actual use case. Agentic trajectories = agent task logs, tool results, observations. Directly applicable to our problem.

**How to test on it:**
```bash
pip install datasets
from datasets import load_dataset
ds = load_dataset("AMA-bench/AMA-bench")
```

---

### 2. MemoryArena (2025)

- **Paper:** [MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks](https://memoryarena.github.io/)
- **Dataset:** Available at memoryarena.github.io

**What it contains:**
- Multi-session tasks where future tasks depend on past memory
- Four task types: web navigation, preference-constrained planning, progressive information search, sequential formal reasoning
- Agents must *acquire* memory while acting, then *use* it in later sessions

**Key finding:** Agents that perform well on LoCoMo "perform poorly in our agentic setting" — memorisation and action are isolated in existing benchmarks, but coupled in real agents.

**Why use it:** Tests the full memory lifecycle — storage, retrieval, and downstream task use — rather than just retrieval quality.

---

### 3. MemoryAgentBench (2025)

- **Paper:** Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions
- **Dataset:** [HuggingFace — ai-hyz/MemoryAgentBench](https://huggingface.co/datasets/ai-hyz/MemoryAgentBench)

**What it contains:**
- Four memory competency tasks:
  1. **Accurate Retrieval** — locate specific information from dialogue history
  2. **Test-Time Learning** — continuously learn new skills during interactions
  3. **Long-Range Understanding** — form global understanding from long conversations
  4. **Conflict Resolution** — update outdated or contradictory information
- Includes EventQA and FactConsolidation sub-datasets

**Why use it:** The Accurate Retrieval task directly measures what we optimise — can the right memory chunk be retrieved? Good for ablation studies on retrieval architecture.

**How to test on it:**
```bash
from datasets import load_dataset
ds = load_dataset("ai-hyz/MemoryAgentBench")
```

---

## Tier 2 — Conversational Memory Datasets (Somewhat Relevant)

These benchmark conversational memory — not agent task memory — but are widely used in the community and allow comparison with published baselines.

---

### 4. LoCoMo (ACL 2024)

- **Paper:** [Evaluating Very Long-Term Conversational Memory of LLM Agents](https://arxiv.org/abs/2402.17753)
- **Authors:** Adyasha Maharana et al. (Snap Research)
- **Dataset:** [GitHub — snap-research/locomo](https://github.com/snap-research/locomo)
- **Project page:** https://snap-research.github.io/locomo/

**What it contains:**
- 10 long-term conversations between LLM-based agents with assigned personas
- ~588 turns and 16,618 tokens per conversation on average
- Up to 600 turns per conversation (much longer than prior benchmarks)
- 4 question types: single-hop, multi-hop, temporal, open-domain
- 3 topic domains: sports, music, movies

**Why use it:** The most widely cited conversational memory benchmark. Published baselines from HyMem, MemR3, MAGMA etc. all report on LoCoMo, so it enables direct comparison. However it is human-to-human conversation, not agent task logs.

**Retrieval relevance judgements:** Yes — each QA pair maps to specific turns in the conversation history, so retrieval recall can be measured.

---

### 5. LongMemEval (ICLR 2025)

- **Paper:** [LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory](https://arxiv.org/abs/2410.10813)
- **Dataset:** [HuggingFace — xiaowu0162/longmemeval](https://huggingface.co/datasets/xiaowu0162/longmemeval)

**What it contains:**
- Synthetic multi-session chat logs between a user and an AI assistant
- 500 questions spanning 5 memory categories:
  1. **Single-session** — retrieve from one session
  2. **Cross-session** — combine information across sessions
  3. **Temporal reasoning** — time-aware retrieval
  4. **Knowledge update** — handle contradictory or updated facts
  5. **Absent information** — correctly abstain when the answer is not in memory
- Two sizes: S (115 sessions avg) and M (500 sessions avg)

**Why use it:** Strong for testing temporal reasoning and conflicting-memory handling. LongMemEval-M is especially challenging and exposes retrieval limits at scale.

**How to test on it:**
```bash
from datasets import load_dataset
ds = load_dataset("xiaowu0162/longmemeval")
```

---

## Tier 3 — General IR Datasets (Currently Used — Less Ideal for Agent Memory)

These are the datasets we benchmarked on in the first phase of the project. They are well-understood and have large communities, but they benchmark document retrieval, not agent memory.

---

### 6. BEIR NFCorpus (currently used)

- **Paper:** [BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663)
- **Dataset:** [HuggingFace — BeIR/nfcorpus](https://huggingface.co/datasets/BeIR/nfcorpus)
- **Local copy:** `beir_nfcorpus.db`

**What it contains:**
- NFCorpus: Nutrition Facts domain
- 3,633 documents, 323 queries, dense relevance judgements
- Used to benchmark RRF, Cascaded, and ColBERT in this project

**Why we used it:** Small, fast to iterate on, standard community benchmark. Good for algorithmic comparison.

**Limitation for our research:** Documents are medical/nutrition articles, not conversation turns or agent task logs. Retrieval is over static documents, not episodic memory. Results may not transfer to agent memory settings.

---

## Ground Truth Evidence Annotations

A critical question for our research: do these datasets annotate *which specific chunk* contains the answer, so we can compute Recall@K directly?

**Answer: Yes — both primary datasets provide this.**

| Dataset | Annotation | Detail |
|---------|-----------|--------|
| **LongMemEval** | `longmemeval_oracle.json` | Each question maps to its ground-truth evidence session(s). Oracle retrieval = answering with only those sessions provided. Recall@K is directly computable at session level. |
| **LoCoMo** | `qa[*].evidence` field | Each QA pair includes the dialog IDs of the specific turns containing the answer. Recall@K is directly computable at turn/chunk level. |
| MemoryAgentBench | Not confirmed | Dataset structure does not explicitly document evidence span annotations. |
| AMA-Bench | Partial | Expert-curated QA pairs for real trajectories; evidence spans present for real trajectories, less clear for synthetic. |

### Why This Matters

Every existing paper (HyMem, MAGMA, MemR3, xMemory) has used these datasets but only reported **end-to-end LLM-as-Judge accuracy** — they never used the evidence annotations to measure retrieval quality directly.

We will use the existing evidence annotations to compute **Recall@K**, measuring whether the retriever returned the right chunk, independently of the LLM layer. This is a new use of existing annotations that no prior work has exploited.

### Recall@K Computation Plan

**LoCoMo:**
- Chunk conversations into fixed-size segments (e.g., 5-turn windows)
- Each QA pair has `evidence` = list of dialog IDs
- Map dialog IDs → chunks
- Run retriever → top-K chunks
- Recall@K = fraction of questions where at least one evidence chunk appears in top-K

**LongMemEval:**
- Use session as the retrieval unit (already segmented into sessions)
- Each question has oracle evidence sessions in `longmemeval_oracle.json`
- Run retriever → top-K sessions
- Recall@K = fraction of questions where at least one evidence session appears in top-K

### Caveat on LoCoMo Annotation Quality

The LoCoMo GitHub repo (issue #27) documents known annotation errors: hallucinated answer keys, temporal mismatches, speaker misattribution. These errors affect all systems equally and do not invalidate cross-system comparisons, but should be noted as a limitation in the paper.

---

## Recommended Testing Sequence

| Priority | Dataset | Why | Effort |
|----------|---------|-----|--------|
| 1st | **AMA-Bench** | Closest to OpenClaw's real use case (agentic trajectories) | Medium — HuggingFace |
| 2nd | **LongMemEval** | Strong retrieval annotations, well-scoped tasks | Low — HuggingFace |
| 3rd | **MemoryAgentBench** | Accurate Retrieval task directly tests our method | Low — HuggingFace |
| 4th | **LoCoMo** | Required for baseline comparison with published systems | Medium — GitHub |
| 5th | **MemoryArena** | Most realistic but harder to set up | High — custom env |
| (done) | **BEIR NFCorpus** | Algorithmic comparison only, not agent memory | Done |

---

## Evaluation Metrics

### Primary Metric: Recall@K

The core question is: **did the retriever return the right memory chunk in the top-K results?**

- Each dataset annotates which specific memory chunk(s) are the ground-truth evidence for each question
- We check whether our retriever included that chunk in its top-K results
- K = 5 or 10 (whatever gets passed to the LLM as context)
- **No LLM involved** — purely measures the retrieval layer in isolation
- Fully reproducible and directly attributable to our system

This is the primary metric for a retrieval research paper because it isolates the retrieval system from everything else.

### Secondary Metric: MRR@10 (Mean Reciprocal Rank)

- Where did the right chunk rank — 1st, 5th, 10th?
- Matters because LLMs have limited context windows; a chunk ranked 10th may be ignored or truncated
- Higher rank = LLM is more likely to use the right memory

### What We Are NOT Using as Primary Metric

**NDCG@10** — graded relevance metric designed for document retrieval where multiple docs can be partially relevant. Agent memory is more binary (one chunk has the answer), so NDCG is a poor fit.

**Answer Accuracy** — confounded by the LLM layer. If the LLM gives the wrong answer, it could be:
1. Retrieval failed (right chunk wasn't retrieved)
2. LLM failed (right chunk was retrieved but LLM ignored it)
3. Both failed

You cannot isolate retrieval quality from Answer Accuracy alone. It measures the full pipeline, not our contribution. We may include it as supporting evidence with a **fixed, frozen LLM** (e.g., always GPT-4o-mini) to hold the LLM constant across ablations — but Recall@K and MRR@10 are the primary claims.

### Summary

| Metric | Role | Why |
|--------|------|-----|
| **Recall@K** | Primary | Directly measures if retriever found the right chunk; no LLM dependency |
| **MRR@10** | Secondary | Measures rank quality; relevant for context window budget |
| Answer Accuracy | Supporting only | Full-pipeline signal; confounded by LLM, useful only with fixed LLM |
| NDCG@10 | Avoid | Designed for graded multi-doc relevance; not a natural fit for memory retrieval |
