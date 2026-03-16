<div align="center">

# ⚖️ المستشار القانوني الذكي
### Egyptian Legal AI Assistant

**A production-grade Arabic RAG system for Egyptian law — built end-to-end with LLMOps best practices.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.10.68-7C3AED)](https://www.llamaindex.ai)
[![Groq](https://img.shields.io/badge/LLM-Groq_Llama3_70B-F55036)](https://groq.com)
[![Cohere](https://img.shields.io/badge/Embeddings-Cohere_Multilingual_v3-39594C)](https://cohere.com)
[![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-FF6F3F)](https://www.trychroma.com)
[![MLflow](https://img.shields.io/badge/LLMOps-MLflow-0194E2?logo=mlflow)](https://mlflow.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Overview

Egyptian citizens and businesses need access to legal information, but law texts are dense, scattered, and require expert interpretation. This system provides instant, **grounded, citation-backed Arabic answers** by combining retrieval-augmented generation (RAG) with strict prompt engineering that refuses to hallucinate outside the retrieved legal text.

Engineered as a **production-grade LLMOps project** — every architectural decision is explicit, tested, and documented.

<details>
<summary><strong>Example interaction (click to expand)</strong></summary>

**User:** هل ينفع عضو مجلس محلي يشتغل مدير لشركة مساهمة موجودة في نفس الدايرة بتاعته؟

**Assistant:**
> وفقاً للتشريعات المصرية،
>
> **الحكم القانوني:** لا يجوز لعضو المجلس الشعبي المحلي أن يتولى منصباً إدارياً في شركة مساهمة تعمل داخل دائرة اختصاص مجلسه.
>
> **السند القانوني:** قانون الشركات 159 لسنة 1981 — المادة 180
>
> **التفاصيل:** تحظر المادة 180 صراحةً على أعضاء المجالس الشعبية المحلية — بصفتهم الشخصية أو عبر وسيط — العمل مديراً أو عضو مجلس إدارة في أي شركة مساهمة تستغل مرفقاً عاماً داخل نطاق اختصاص مجلسهم. يترتب على المخالفة بطلان التصرف وإلزام المخالف برد ما قبضه للخزانة العامة.

</details>

---

## Architecture

```
User Query (Arabic — colloquial or formal)
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                FastAPI  /api/v1                       │
│  POST /query    GET /health    GET /ready             │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                  Query Pipeline                       │
│                                                       │
│  1. Query Rewrite ──── colloquial → formal legal     │
│     (Groq Llama3-70B · Arabic-only validator)         │
│                                                       │
│  2. Retrieval ──────── top-20 by cosine similarity   │
│     (Cohere embed-multilingual-v3.0 → ChromaDB)       │
│                                                       │
│  3. Reranking ──────── top-20 → top-5                │
│     (BAAI/bge-reranker-v2-m3 cross-encoder)           │
│                                                       │
│  4. Citation Formatting                               │
│     [المصدر: القانون - المادة N]                      │
│                                                       │
│  5. Synthesis ──────── strict Arabic QA prompt       │
│     (Groq Llama3-70B · simple_summarize mode          │
│      forced "وفقاً للتشريعات المصرية،" prefix)         │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
             QueryResponse (domain type)
      answer · source_chunks · llm_provider_used
```

### Bounded Contexts

```
src/
├── core/                       Shared kernel
│   ├── config.py               Pydantic BaseSettings singleton
│   ├── schemas.py              Domain types: QueryRequest, QueryResponse, DocumentChunk
│   └── exceptions.py           Typed exception hierarchy (EmptyRetrievalError, LLMProviderError…)
│
├── document_processing/        Ingestion context
│   └── ingestion_pipeline.py   Arabic مادة-regex parser · deterministic chunk IDs
│
├── knowledge_base/             Vector store context
│   ├── embeddings.py           Embedding factory (Cohere cloud / Ollama local)
│   ├── vector_store.py         Config-hash collection naming in ChromaDB
│   └── indexer.py              DocumentChunk → TextNode → ChromaDB upsert
│
├── llm_providers/              LLM abstraction
│   └── llm_factory.py          get_llm(settings) → Groq | Ollama | Claude
│
├── query_engine/               Query context
│   ├── query_pipeline.py       Full RAG pipeline (rewrite→retrieve→rerank→synthesize)
│   ├── retriever.py            VectorIndexRetriever configuration
│   └── response_synthesizer.py LlamaIndex Response → QueryResponse
│
├── evaluation/                 LLMOps context
│   ├── ragas_evaluator.py      Faithfulness + Answer Relevancy scoring
│   ├── mlflow_tracker.py       THE ONLY file that imports mlflow
│   ├── metrics.py              EvaluationRecord, METRIC_THRESHOLDS
│   └── experiment_runner.py    Orchestrates eval runs
│
└── api/                        HTTP layer
    ├── main.py                 FastAPI factory · CORS · lifespan startup logs
    ├── dependencies.py         get_api_settings() — testable via dependency_overrides
    ├── exception_handlers.py   Domain exception → HTTP status mapping
    └── routers/
        ├── query.py            POST /api/v1/query
        ├── health.py           GET /health · GET /ready
        └── ingestion.py        POST /api/v1/ingest
```

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **LLM Generation** | Groq `llama3-70b-8192` | Free tier · fastest inference (~300ms) · strong Arabic |
| **Embeddings** | Cohere `embed-multilingual-v3.0` | Native Arabic · free tier · 1024-dim · no GPU |
| **Reranking** | `BAAI/bge-reranker-v2-m3` | Multilingual cross-encoder · improves precision ~20% |
| **Vector DB** | ChromaDB 0.5.5 | Local persistent · config-hash collection isolation |
| **RAG Framework** | LlamaIndex 0.10.68 | Purpose-built for document RAG · async-native |
| **API** | FastAPI 0.115 + Uvicorn | Async · typed · auto-documented Swagger UI |
| **Config** | Pydantic BaseSettings | Type-validated at startup · testable overrides |
| **Evaluation** | Ragas 0.1.21 | Faithfulness + Answer Relevancy scoring |
| **Tracking** | MLflow 2.16.2 | Experiment tracking · metric logging · isolated |
| **Frontend** | React + Tailwind | RTL-native Arabic chat interface |

---

## Key Engineering Decisions

<details>
<summary><strong>Why <code>response_mode="simple_summarize"</code> instead of <code>"compact"</code></strong></summary>

LlamaIndex's `compact` mode calls two templates: your custom Arabic prompt for the first synthesis pass, then a **hardcoded English `REFINE_PROMPT`** on subsequent passes when context overflows. This caused the LLM to switch to English mid-response — the model receives English context and mirrors the language.

`simple_summarize` calls our Arabic template exactly once. No refine template, no language leakage.

</details>

<details>
<summary><strong>Why <code>EMBEDDING_INPUT_TYPE</code> is set before config import in <code>ingest.py</code></strong></summary>

Cohere's Embed v3 is an asymmetric model. Documents embedded during ingestion must use `input_type="search_document"` and queries at runtime must use `input_type="search_query"`. Mixing these drops cosine similarity by ~15–20%.

`scripts/ingest.py` sets `os.environ["EMBEDDING_INPUT_TYPE"] = "search_document"` before any config import so the Pydantic settings singleton reads the correct value. The API defaults to `search_query`.

</details>

<details>
<summary><strong>Why the reranker runs before the citation formatter</strong></summary>

`CrossEncoderReranker` scores `(query, document_text)` pairs. If `MetadataMappingPostprocessor` runs first, it wraps the text in `[المصدر: ...]` citation headers — the cross-encoder then scores formatting noise rather than legal content. Postprocessor order is **enforced** and documented in `query_pipeline.py`.

</details>

<details>
<summary><strong>Why <code>mlflow_tracker.py</code> is the only file that imports MLflow</strong></summary>

If MLflow calls live inside `query_engine/` or `knowledge_base/`, the pipeline requires a running tracking server in tests. By isolating all `import mlflow` to one file, the entire pipeline is testable without MLflow. Removing or replacing the tracking backend is a one-file change.

</details>

<details>
<summary><strong>Why config-hash collection naming in ChromaDB</strong></summary>

Each combination of `(embedding_model, chunk_size, chunk_overlap)` produces vectors in a different space. Mixing vectors from different configurations in one collection causes silent retrieval degradation. The hash `f"egyptian_law_{md5(config)[:8]}"` automatically isolates collections — changing any parameter creates a new collection, never corrupts an existing one.

</details>

---

## Quickstart

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | |
| Docker + Docker Compose | For ChromaDB and MLflow |
| Groq API Key | Free at [console.groq.com/keys](https://console.groq.com/keys) — no credit card |
| Cohere API Key | Free at [dashboard.cohere.com/api-keys](https://dashboard.cohere.com/api-keys) — no credit card |

### 1 — Clone and install

```bash
git clone https://github.com/omarelsaber/legal-assistant-rag.git
cd legal-assistant-rag

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Configure

```bash
cp .env.example .env
```

The only required keys:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...               # console.groq.com/keys

EMBEDDING_PROVIDER=cohere
COHERE_API_KEY=...                 # dashboard.cohere.com/api-keys
```

### 3 — Start infrastructure

```bash
make up
# Starts ChromaDB on :8000 and MLflow on :5000 via Docker
```

### 4 — Prepare corpus

```bash
# Using the Hugging Face dataset (TawasulAI/egyptian-law-articles):
# 1. Download data/0000.parquet from the dataset
python scripts/convert_data.py     # → data/raw/egyptian_laws.txt

# Or: place any .txt file in data/raw/ using مادة N article headers
```

### 5 — Build the vector index

```bash
make ingest
# Embeds all articles via Cohere API (pure HTTPS — no GPU, no Ollama)
# Creates collection egyptian_law_{config-hash} in ChromaDB
```

### 6 — Start the API

```bash
python -m src.api.main
```

| Endpoint | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |

### 7 — Test a query

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "ما هي شروط تأسيس شركة المساهمة؟", "top_k": 5}'
```

---

## Environment Reference

### Required

| Variable | Example | Description |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` · `ollama` · `claude` |
| `GROQ_API_KEY` | `gsk_...` | Required when `LLM_PROVIDER=groq` |
| `EMBEDDING_PROVIDER` | `cohere` | `cohere` (cloud) · `ollama` (local dev) |
| `COHERE_API_KEY` | `...` | Required when `EMBEDDING_PROVIDER=cohere` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `GROQ_MODEL` | `llama3-70b-8192` | 70B recommended for Arabic quality |
| `EMBEDDING_MODEL` | `embed-multilingual-v3.0` | Cohere model name |
| `EMBEDDING_INPUT_TYPE` | `search_query` | Set to `search_document` during ingestion |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between consecutive chunks |
| `API_PORT` | `8000` | FastAPI server port |
| `LOG_LEVEL` | `INFO` | `DEBUG` · `INFO` · `WARNING` · `ERROR` |

---

## API Reference

### `POST /api/v1/query`

```json
// Request
{
  "query": "ما هو الحد الأدنى لعدد المؤسسين في شركة المساهمة؟",
  "top_k": 5
}

// Response
{
  "answer": "وفقاً للتشريعات المصرية،\n\n**الحكم القانوني:** ...",
  "source_chunks": [
    {
      "chunk_id": "ba346b8ae1052407",
      "source_file": "egyptian_laws.txt",
      "article_number": "المادة 8",
      "content": "لا يجوز أن يقل عدد الشركاء المؤسسين...",
      "metadata": { "law_name": "قانون الشركات 159 لسنة 1981" }
    }
  ],
  "confidence_score": null,
  "llm_provider_used": "groq"
}
```

**Error responses**

| Status | Exception | Meaning |
|---|---|---|
| `404` | `EmptyRetrievalError` | No relevant articles for query |
| `422` | Validation | Query < 3 chars or > 2000 chars |
| `503` | `LLMProviderError` | Groq unavailable · includes `Retry-After: 60` header |
| `500` | `ConfigurationError` | Missing key or misconfiguration |

### `GET /health` — Liveness probe
### `GET /ready` — Readiness probe (checks ChromaDB + non-empty collection)

---

## Development

### Commands

```bash
make test          # unit tests only — fast, no services needed
make test-int      # integration tests — requires ChromaDB running
make test-e2e      # end-to-end — requires full stack
make coverage      # unit tests + HTML coverage report
make evaluate      # Ragas evaluation + log to MLflow
make lint          # ruff check + format
make typecheck     # mypy strict
make clean         # remove __pycache__, .coverage, build artifacts
```

### LLMOps pipeline

```
PR opened
    │
    ▼
GitHub Actions
  ├── make lint
  ├── make typecheck
  ├── make test
  └── make evaluate ──── Ragas gates: faithfulness ≥ 0.7  relevancy ≥ 0.6
                                │
                    ┌───────────┴───────────┐
                    │ PASS                  │ FAIL
                    ▼                       ▼
              merge + deploy          block merge
                    │
                    ▼
              MLflow tracking
              ├── per-request: latency, token count, rewrite accepted
              ├── per-eval:    faithfulness, answer_relevancy
              └── per-run:     mean scores, pass rate
```

---

## Deployment

### Production setup (free tier)

```
Vercel ──── React frontend
Render ──── FastAPI backend
              ├── Groq API      (LLM generation)
              ├── Cohere API    (query embedding — real-time)
              └── ChromaDB      (pre-built index, committed to repo)
```

### Backend (Render)

Set in the Render dashboard — **never in Dockerfile**:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
EMBEDDING_PROVIDER=cohere
COHERE_API_KEY=...
```

Start command:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

> **ChromaDB on Render free tier:** The free tier has an ephemeral filesystem. Run `make ingest` locally, commit `chroma_db/` to git, and Render loads it read-only. For live re-ingestion, use Render Persistent Disk ($7/month) or migrate to Pinecone free tier.

### Frontend (Vercel)

```
VITE_API_URL=https://your-render-service.onrender.com
```

---

## License & Author

**Author**: Omar Elsaber  
**License**: MIT © 2026

---

<div align="center">

Built with Arabic-first engineering.  
Every prompt, parser, and chunk boundary was designed for the Arabic legal register — not retrofitted from an English baseline.

</div>