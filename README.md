# FactStack

[English](README.md) | [中文](README_zh.md)

**Evidence-first RAG Q&A system for technical documentation**

FactStack is a Retrieval-Augmented Generation (RAG) system designed for technical documentation and runbooks. It prioritizes **grounded answers with citations** and includes built-in **refusal logic** for cases where evidence is insufficient.

## Key Features

- 📚 **Evidence-First Answers**: All answers are grounded in retrieved documents with explicit citations
- 🚫 **Refusal Logic**: System refuses to answer when evidence is insufficient, avoiding hallucinations
- 🔍 **Hybrid Retrieval**: Combines vector search (semantic) with BM25 (keyword) for better recall
- 🌐 **Cross-lingual Retrieval**: Ask questions in Chinese against English documents with dual-channel retrieval
- 📊 **Reranking**: Multi-stage pipeline with reranking for improved precision
- 📝 **Full Traceability**: JSONL traces for every query showing pipeline stages and timing
- 🧪 **Built-in Evaluation**: Evaluation framework with metrics for recall, citation precision, and refusal accuracy
- 🔧 **Configurable Prompts**: Multiple prompt configurations for different use cases

## Quick Start

### Installation

```bash
# Clone and install
pip install -r requirements.txt
pip install -e .
```

### One-Command Demo (No API Key Required)

FactStack includes a DummyLLM that allows running the complete pipeline without an OpenAI API key:

```bash
# 1. Ingest documents
python -m factstack.ingest --docs ./docs --persist ./db

# 2. Ask a question
python -m factstack.ask --db ./db --question "How do I troubleshoot a CrashLoopBackOff in Kubernetes?"

# 3. Run evaluation
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml
```

### With OpenAI API

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your-key-here

python -m factstack.ask --db ./db --question "What are the steps to deploy a service?"
```

## Project Structure

```
factstack/
├── docs/                      # Sample technical documentation
├── prompts/
│   ├── base.yaml             # Default prompt configuration
│   └── strict.yaml           # Stricter refusal configuration
├── artifacts/                 # Generated outputs (traces, answers)
├── src/factstack/
│   ├── config.py             # Configuration management
│   ├── ingest.py             # Document ingestion CLI
│   ├── ask.py                # Q&A CLI
│   ├── eval.py               # Evaluation CLI
│   ├── pipeline/
│   │   ├── chunking.py       # Document chunking
│   │   ├── embeddings.py     # Embedding generation
│   │   ├── vector_store.py   # ChromaDB vector storage
│   │   ├── bm25_store.py     # BM25 keyword index
│   │   ├── rerank.py         # Reranking logic
│   │   ├── assemble.py       # Context assembly
│   │   └── refusal.py        # Refusal/uncertainty logic
│   ├── llm/
│   │   ├── base.py           # LLM interface
│   │   ├── openai_llm.py     # OpenAI implementation
│   │   ├── dummy_llm.py      # Testing without API
│   │   └── schemas.py        # Pydantic output schemas
│   └── observability/
│       └── tracer.py         # Pipeline tracing
└── tests/
    └── eval_set.yaml         # Evaluation test cases
```

## Usage Guide

### Document Ingestion

```bash
# Basic ingestion
python -m factstack.ingest --docs ./docs --persist ./db

# Custom chunk settings
python -m factstack.ingest --docs ./docs --persist ./db --chunk-size 600 --chunk-overlap 100
```

### Asking Questions

```bash
# Basic question
python -m factstack.ask --db ./db --question "How do I rollback a deployment?"

# With different prompt configuration
python -m factstack.ask --db ./db --question "..." --prompt strict

# Output as JSON
python -m factstack.ask --db ./db --question "..." --json

# Custom top-k retrieval
python -m factstack.ask --db ./db --question "..." --topk 10
```

### Evaluation

```bash
# Run evaluation suite
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml

# Use strict prompts
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml --prompt strict

# Custom output location
python -m factstack.eval --db ./db --eval ./tests/eval_set.yaml --output ./results.json
```

## Output Format

### Answer Structure

Every answer includes:

```json
{
  "answer": "Answer with [C1], [C2] citations",
  "citations": [
    {"chunk_id": "...", "source": "file.md", "text": "...", "score": 0.85}
  ],
  "confidence": 0.75,
  "missing_info": ["additional context needed"],
  "reasoning": "explanation of answer derivation",
  "is_refusal": false,
  "refusal_reason": null
}
```

### Trace Format (JSONL)

Each query generates a trace file in `artifacts/`:

```json
{"ts": "...", "run_id": "abc123", "stage": "vector_search", "input_summary": "...", "output_summary": "5 results", "latency_ms": 45.2, "ok": true}
{"ts": "...", "run_id": "abc123", "stage": "rerank", "input_summary": "...", "output_summary": "3 results", "latency_ms": 120.5, "ok": true}
```

## Adding New Documents

1. Add Markdown or TXT files to `./docs/`
2. Re-run ingestion: `python -m factstack.ingest --docs ./docs --persist ./db`
3. The index will be rebuilt with new documents

## Adding Evaluation Cases

Edit `tests/eval_set.yaml`:

```yaml
cases:
  - question: "Your test question"
    expected_sources:
      - "document_name"  # Partial match on source path
    expected_answer_contains:
      - "expected keyword"
    difficulty: medium  # easy/medium/hard
    should_refuse: false  # true if question should be refused
```

## Evaluation Metrics

- **Recall@K**: Were expected sources retrieved?
- **Citation Precision**: Are citations from expected sources?
- **Answer Groundedness**: Does answer include citations?
- **Refusal Accuracy**: Does system refuse when it should?

## Configuration

### Environment Variables

- `LLM_PROVIDER`: `openai` or `dummy` (default: `dummy`)
- `LLM_MODEL`: Model to use for LLM (default: `gpt-4o-mini`)
- `EMBEDDING_MODEL`: Model to use for embeddings (default: `text-embedding-3-small`)
- `OPENAI_API_KEY`: Required when using OpenAI

Example with custom models:
```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4o
export EMBEDDING_MODEL=text-embedding-3-large
export OPENAI_API_KEY=your-key-here

python -m factstack.ask --db ./db --question "How do I deploy a service?"
```

### Prompt Configurations

- `base.yaml`: Balanced configuration for general use
- `strict.yaml`: Higher refusal threshold, stricter citation requirements

## Design Principles

1. **No Answer Without Evidence**: Every claim must be supported by retrieved chunks
2. **Explicit Uncertainty**: When evidence is insufficient, the system says so
3. **Full Traceability**: Every pipeline stage is logged for debugging
4. **Evaluation-Driven**: Built-in evaluation ensures quality over time

## Cross-lingual Retrieval

### The Problem

When asking questions in Chinese (or other CJK languages) against English documentation, traditional RAG systems often fail because:

1. **Embedding Space Mismatch**: Chinese query embeddings don't align well with English document embeddings
2. **Keyword Mismatch**: BM25/keyword search fails when query and documents use different languages

This results in very low relevance scores (e.g., ~0.01) and triggers refusal even when relevant documents exist.

### The Solution: Dual-Channel Retrieval

FactStack implements a dual-channel retrieval approach:

1. **Query Language Detection**: Automatically detects if the query contains CJK characters
2. **Query Translation**: Translates non-English queries to retrieval-friendly English keywords
3. **Dual Retrieval**: Runs parallel searches with both original and translated queries
4. **Multi-Recall Merge**: Combines results from both channels, deduplicating by chunk ID
5. **Unified Reranking**: Reranks merged results for final ordering

### Usage Examples

**Chinese question with English documents:**

```bash
# Ask in Chinese
python -m factstack.ask --db ./db --question "如何回滚部署？"

# Output:
# QueryLang=zh, CrossLingual=True, Translation=rule
# Translated query: "rollback deploy deployment"
# Citations from deployment_runbook.md
```

**Disable cross-lingual retrieval:**

```bash
python -m factstack.ask --db ./db --question "如何回滚部署？" --cross-lingual off
```

**Control translation mode:**

```bash
# Use LLM for translation (requires API key)
python -m factstack.ask --db ./db --question "如何回滚部署？" --translation-mode llm

# Use rule-based dictionary translation (no API key needed)
python -m factstack.ask --db ./db --question "如何回滚部署？" --translation-mode rule

# Disable translation
python -m factstack.ask --db ./db --question "如何回滚部署？" --translation-mode off
```

### CLI Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--cross-lingual` | `on`, `off` | `on` | Enable dual-channel retrieval |
| `--translate` | `on`, `off` | `on` | Enable query translation |
| `--translation-mode` | `llm`, `rule`, `off` | `llm` | Translation method |
| `--topk` | integer | 8 | Chunks per retrieval channel |
| `--rerank-topk` | integer | 5 | Chunks after reranking |

### Translation Modes

- **`llm`**: Uses the configured LLM for translation (best quality, requires API key)
- **`rule`**: Uses built-in Chinese-English dictionary (no API key, works offline)
- **`off`**: Disables translation entirely

When `--translation-mode llm` is set but no API key is available, the system automatically falls back to `rule` mode.

### Trace Fields for Cross-lingual

The trace includes additional fields for cross-lingual retrieval:

```json
{"stage": "language_detect", "metadata": {"query_language": "zh", "needs_translation": true}}
{"stage": "query_translate", "metadata": {"original_query": "如何回滚部署？", "translated_query": "rollback deploy deployment", "translation_mode": "rule"}}
{"stage": "dual_retrieval", "metadata": {"original_query": "...", "translated_query": "...", "total_candidates": 12, "multi_channel_hits": 3}}
```

### Multi-Indicator Refusal

The refusal logic uses multiple indicators instead of just the best score:

- **Top-N Average Score**: Average score of top 5 chunks
- **High-Quality Evidence Count**: Number of chunks above quality threshold
- **Coverage**: Percentage of top results that are relevant
- **Cross-lingual Boost**: More lenient thresholds when translation was used

This prevents false refusals when cross-lingual retrieval finds relevant documents through the translation channel.

## License

MIT
