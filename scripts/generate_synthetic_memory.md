# Synthetic Agent Memory Dataset Generation

## Goal
Create a realistic agent memory dataset for hybrid retrieval research without requiring real user data.

## Approach

### 1. Seed Memory Corpus (1000-5000 entries)

Generate diverse memory types:

```markdown
# Technical Discussions
- "Implemented SQLite connection pooling with max_connections=10"
- "Fixed memory leak in vector embedding cache"
- "Discussed trade-offs between FTS5 and Elasticsearch"

# Code Snippets
- "Created Python script to batch process embeddings"
- "Refactored database schema to add temporal_weight column"

# Project Planning
- "Decided to use BEIR benchmark for evaluation"
- "Set research timeline: 12 weeks for unified operator"

# Debugging Sessions
- "Traced segfault to sqlite-vec extension loading"
- "Found that BM25 scores need normalization before fusion"

# Meeting Notes
- "Team agreed on hybrid_score = 0.5*vector + 0.3*text + 0.2*temporal"
```

### 2. Generate Query Pairs

For each memory entry, create 3-5 queries with varying specificity:

**Memory Entry:**
```
"Implemented hybrid search using weighted fusion: 
vectorWeight=0.5, textWeight=0.3, temporalDecay=0.2"
```

**Generated Queries:**
1. **Exact keyword**: "hybrid search weighted fusion"
2. **Semantic paraphrase**: "how did we combine vector and text scores?"
3. **Temporal**: "that search algorithm we implemented last week"
4. **Partial recall**: "the weights we used for ranking"
5. **Conversational**: "remind me about the fusion approach"

### 3. Relevance Annotations

Label each query-memory pair:
- **2 (Highly Relevant)**: Direct answer to query
- **1 (Relevant)**: Related but not primary answer
- **0 (Irrelevant)**: No connection

### 4. Temporal Distribution

Simulate realistic memory age distribution:
- 20% recent (0-7 days)
- 30% medium (7-30 days)
- 30% old (30-90 days)
- 20% archived (90+ days)

## Implementation Script

```python
import random
from datetime import datetime, timedelta

# Memory templates by category
MEMORY_TEMPLATES = {
    "technical": [
        "Implemented {feature} using {technology}",
        "Fixed {bug_type} in {component}",
        "Optimized {operation} by {improvement}",
    ],
    "planning": [
        "Decided to use {tool} for {purpose}",
        "Set {metric} target to {value}",
        "Planned {phase} for {duration}",
    ],
    "debugging": [
        "Traced {error} to {root_cause}",
        "Found that {component} needs {fix}",
        "Discovered {issue} when {condition}",
    ]
}

# Query templates
QUERY_TEMPLATES = {
    "keyword": "{main_terms}",
    "semantic": "how did we {action}?",
    "temporal": "that {topic} we {action} {time_ref}",
    "conversational": "remind me about {topic}",
}

def generate_memory_entry(category, age_days):
    template = random.choice(MEMORY_TEMPLATES[category])
    # Fill template with domain-specific terms
    # Add timestamp
    return {
        "content": filled_template,
        "timestamp": datetime.now() - timedelta(days=age_days),
        "category": category
    }

def generate_queries(memory_entry):
    queries = []
    for query_type, template in QUERY_TEMPLATES.items():
        query = fill_query_template(template, memory_entry)
        relevance = compute_relevance(query, memory_entry)
        queries.append({
            "query": query,
            "memory_id": memory_entry["id"],
            "relevance": relevance,
            "type": query_type
        })
    return queries
```

## Dataset Size Recommendations

- **Development**: 1K memories, 3K queries
- **Validation**: 5K memories, 15K queries  
- **Final Evaluation**: 10K memories, 30K queries

## Advantages

✅ No privacy concerns
✅ Controlled distribution (temporal, category, complexity)
✅ Ground-truth relevance labels
✅ Can generate unlimited data for ablation studies
✅ Reproducible by other researchers
