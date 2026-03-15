"""
Ragas evaluator for the Egyptian Law Assistant.

CRITICAL — Local LLM configuration:
  Ragas 0.1.x defaults to OpenAI for both LLM calls (faithfulness NLI,
  answer relevancy question generation) and embeddings (answer relevancy
  semantic similarity). If you do not explicitly override these, every
  evaluation run will fail with an OpenAI API key error.

  The correct override pattern for LlamaIndex-backed local models is:

    from ragas.llms import LlamaIndexLLMWrapper
    from ragas.embeddings import LlamaIndexEmbeddingsWrapper

    faithfulness.llm        = LlamaIndexLLMWrapper(ollama_llm)
    answer_relevancy.llm    = LlamaIndexLLMWrapper(ollama_llm)
    answer_relevancy.embeddings = LlamaIndexEmbeddingsWrapper(embed_model)

  This module centralises that configuration so it happens exactly once,
  in exactly one place, before evaluate() is called.

Ragas dataset format (ragas 0.1.x):
  ``ragas.evaluate()`` consumes a HuggingFace ``datasets.Dataset`` with
  these mandatory columns:
    - question  : str       — the original user query
    - answer    : str       — the LLM-generated answer
    - contexts  : list[str] — the retrieved chunk texts (NOT the full chunks)

  ``ground_truth`` is optional and only needed for context_recall /
  context_precision. We omit it for MVP metrics (faithfulness,
  answer_relevancy).
"""

from __future__ import annotations

import logging

from datasets import Dataset
from ragas import evaluate
from ragas.embeddings import LlamaIndexEmbeddingsWrapper
from ragas.llms import LlamaIndexLLMWrapper

from src.core.config import Settings, get_settings
from src.core.schemas import QueryRequest, QueryResponse
from src.evaluation.metrics import MVP_METRICS, EvaluationRecord
from src.knowledge_base.embeddings import get_embedding_model
from src.llm_providers.llm_factory import get_llm

logger = logging.getLogger(__name__)

# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_ragas_dataset(
    query: str,
    response: QueryResponse,
) -> Dataset:
    """
    Construct a single-row HuggingFace ``Dataset`` from a ``QueryResponse``.

    Ragas ``evaluate()`` processes a batch, but for simplicity each query
    is scored individually. The ``experiment_runner`` collects and logs the
    results. Batching multiple queries would require constructing a multi-row
    Dataset — straightforward to add later but unnecessary for MVP.

    Args:
        query:    The original query string (from ``QueryRequest.query``).
        response: The ``QueryResponse`` produced by the query pipeline.

    Returns:
        A single-row ``datasets.Dataset`` with columns:
        ``question``, ``answer``, ``contexts``.
    """
    # Extract plain text from each source chunk.
    # Ragas expects List[str] for contexts — not DocumentChunk objects.
    contexts: list[str] = [
        chunk.content
        for chunk in response.source_chunks
        if chunk.content.strip()  # skip any accidental empty chunks
    ]

    # If retrieval returned nothing, Ragas faithfulness will score poorly
    # (correct behaviour: an answer with no grounding is unfaithful).
    # We still proceed rather than raising, so the bad score is logged.
    if not contexts:
        logger.warning(
            "Building Ragas dataset with 0 contexts for query %r. "
            "Faithfulness score will likely be 0.0.",
            query[:60],
        )
        # Ragas requires at least one context string; use a sentinel.
        contexts = ["[no context retrieved]"]

    return Dataset.from_dict(
        {
            "question": [query],
            "answer":   [response.answer],
            "contexts": [contexts],
        }
    )

def _configure_metrics(settings: Settings) -> None:
    """
    Inject local Ollama LLM and embeddings into every active Ragas metric.

    Why mutate module-level metric instances?
    Ragas 0.1.x does not support per-call LLM injection — the LLM is stored
    as an attribute on the metric object. Since ``MVP_METRICS`` contains the
    same instances throughout the process, this configuration is effectively
    a one-time setup. Calling it multiple times is safe (idempotent overwrite).

    Why LlamaIndexLLMWrapper / LlamaIndexEmbeddingsWrapper?
    Ragas has its own LLM abstraction layer (``ragas.llms.BaseRagasLLM``).
    The wrappers translate LlamaIndex's ``LLM`` interface to Ragas's expected
    interface, so we can reuse the same Ollama/Claude objects from llm_factory
    without duplicating provider configuration.

    Args:
        settings: Active settings — determines which Ollama model to use.
    """
    llm         = get_llm(settings)
    embed_model = get_embedding_model(settings)

    ragas_llm    = LlamaIndexLLMWrapper(llm)
    ragas_embeds = LlamaIndexEmbeddingsWrapper(embed_model)

    for metric in MVP_METRICS:
        # All MVP metrics need an LLM for NLI / question-generation steps.
        metric.llm = ragas_llm  # type: ignore[attr-defined]

        # answer_relevancy additionally needs embeddings for semantic similarity.
        if hasattr(metric, "embeddings"):
            metric.embeddings = ragas_embeds  # type: ignore[attr-defined]

    logger.info(
        "Ragas metrics configured with local Ollama: llm=%r  embed_model=%r",
        settings.ollama_model,
        settings.embedding_model,
    )

# ── Public interface ───────────────────────────────────────────────────────────

def score_response(
    query: str,
    response: QueryResponse,
    settings: Settings | None = None,
) -> EvaluationRecord:
    """
    Score a single ``QueryResponse`` using Ragas and return an ``EvaluationRecord``.

    This function is the primary public interface of the evaluation bounded
    context. It:
      1. Configures Ragas metrics to use local Ollama (not OpenAI).
      2. Builds the required HuggingFace Dataset from the QueryResponse.
      3. Calls ``ragas.evaluate()`` synchronously.
      4. Extracts scores and packages them into an ``EvaluationRecord``.

    Failure handling:
      If Ragas raises any exception (network timeout to Ollama, malformed
      output, etc.), the error is caught, logged, and stored in
      ``EvaluationRecord.scoring_error``. The record is returned with
      ``None`` scores rather than propagating the exception — a single bad
      evaluation should never abort an entire experiment run.

    Args:
        query:    The original user query string.
        response: The ``QueryResponse`` from ``execute_query()`` to score.
        settings: Active settings. Defaults to global singleton.

    Returns:
        An ``EvaluationRecord`` with populated (or None) Ragas scores.
    """
    active_settings = settings or get_settings()

    # Collect source article numbers for human-readable logging
    source_articles = [
        chunk.article_number
        for chunk in response.source_chunks
        if chunk.article_number
    ]

    # Pre-build the record so we can populate it in both success and error paths
    record = EvaluationRecord(
        query=query,
        answer=response.answer,
        contexts=[c.content for c in response.source_chunks],
        source_articles=source_articles,
        llm_provider_used=response.llm_provider_used,
    )

    logger.info(
        "Scoring response: query=%r  contexts=%d  provider=%r",
        query[:60],
        len(record.contexts),
        response.llm_provider_used,
    )

    try:
        # ── Step 1: Inject local LLM into Ragas metrics ───────────────────────
        _configure_metrics(active_settings)

        # ── Step 2: Build Ragas dataset ───────────────────────────────────────
        dataset = _build_ragas_dataset(query, response)

        # ── Step 3: Run evaluation ───────────────────────────────────────────
        # ragas.evaluate() returns a dict-like ``Result`` object.
        # Access scores by metric name string.
        result = evaluate(dataset=dataset, metrics=MVP_METRICS)

        # ── Step 4: Extract scores ───────────────────────────────────────────
        # result[metric_name] returns the mean score across the dataset rows.
        # For our single-row datasets this is just the one score.
        record.faithfulness     = _safe_extract_score(result, "faithfulness")
        record.answer_relevancy = _safe_extract_score(result, "answer_relevancy")

        logger.info(
            "Ragas scores: faithfulness=%.3f  answer_relevancy=%.3f",
            record.faithfulness   or 0.0,
            record.answer_relevancy or 0.0,
        )

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error("Ragas evaluation failed: %s", error_msg)
        record.scoring_error = error_msg
        # scores remain None — caller sees EvaluationRecord.scoring_error

    return record

def _safe_extract_score(result: object, metric_name: str) -> float | None:
    """
    Safely extract a named score from a Ragas ``Result`` object.

    Ragas ``Result`` supports dict-style access ``result[metric_name]`` but
    can raise ``KeyError`` if a metric failed internally. We catch that and
    return ``None`` rather than crashing the scoring run.

    Args:
        result:      The ``Result`` object returned by ``ragas.evaluate()``.
        metric_name: The metric key, e.g. ``"faithfulness"``.

    Returns:
        The float score, or ``None`` if the key is absent or the value is
        not a valid float.
    """
    try:
        value = result[metric_name]  # type: ignore[index]
        if value is None:
            return None
        score = float(value)
        # Clamp to [0, 1] — Ragas can occasionally return tiny negatives
        # due to floating-point arithmetic in cosine similarity.
        return max(0.0, min(1.0, score))
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "Could not extract score for metric %r: %s",
            metric_name,
            exc,
        )
        return None