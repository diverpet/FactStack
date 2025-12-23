# FactStack

**Evidence-first RAG Q&A system for technical documentation**

FactStack is a Retrieval-Augmented Generation (RAG) system designed for technical documentation and runbooks. It prioritizes **grounded answers with citations** and includes built-in **refusal logic** for cases where evidence is insufficient.

## Key Features

- 📚 **Evidence-First Answers**: All answers are grounded in retrieved documents with explicit citations
- 🚫 **Refusal Logic**: System refuses to answer when evidence is insufficient, avoiding hallucinations
- 🔍 **Hybrid Retrieval**: Combines vector search (semantic) with BM25 (keyword) for better recall
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
- `OPENAI_API_KEY`: Required when using OpenAI

### Prompt Configurations

- `base.yaml`: Balanced configuration for general use
- `strict.yaml`: Higher refusal threshold, stricter citation requirements

## Design Principles

1. **No Answer Without Evidence**: Every claim must be supported by retrieved chunks
2. **Explicit Uncertainty**: When evidence is insufficient, the system says so
3. **Full Traceability**: Every pipeline stage is logged for debugging
4. **Evaluation-Driven**: Built-in evaluation ensures quality over time

## License

MIT
