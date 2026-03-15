# Egyptian Law Assistant

A Retrieval-Augmented Generation (RAG) system designed to assist with Egyptian legal documents, supporting Arabic text processing and multiple LLM providers.

## Architecture

The system follows a modular architecture with bounded contexts:

- **Document Processing**: Ingests and processes legal documents (PDFs, DOCX) into chunks with metadata extraction.
- **Knowledge Base**: Manages vector embeddings and indexing using ChromaDB.
- **Query Engine**: Handles retrieval and response generation.
- **LLM Providers**: Abstraction for Ollama and Claude APIs.
- **Evaluation**: Uses Ragas for metrics and MLflow for tracking.
- **API**: FastAPI-based REST API for queries and ingestion.

## Quick Start

1. **Setup Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

2. **Start Services**:
   ```bash
   make up
   ```

3. **Ingest Documents**:
   Place PDF/DOCX files in `data/raw/`
   ```bash
   make ingest
   ```

4. **Run Tests**:
   ```bash
   make test
   ```

5. **Query the API**:
   The API will be available at `http://localhost:8000`

## Decision Log

- **LLM Abstraction**: Supports both local (Ollama) and cloud (Claude) providers for flexibility.
- **Arabic Support**: Uses Arabic-aware chunking and metadata extraction.
- **Performance**: Streaming batch ingestion, two-level caching, async query pipeline.
- **Testing**: Comprehensive unit/integration/e2e tests with Ragas evaluation.
- **Deployment**: Separate containers for ingestion and query services.