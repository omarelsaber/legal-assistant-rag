"""
Ragas metric definitions for the Egyptian Law Assistant evaluation harness.



This module defines:

  1. Which Ragas metrics are active for this project.

  2. A domain ``EvaluationRecord`` dataclass that carries one complete

     (query, response, scores) triple — the unit of work for the evaluator

     and the MLflow tracker.

  3. ``METRIC_THRESHOLDS`` — the pass/fail gates used in e2e tests

     (Test Decision #2: Ragas gates at the e2e tier).



Metric selection rationale for an MVP legal RAG system:



  Faithfulness (priority: HIGH)

    Measures whether every claim in the answer is supported by the retrieved

    context. In a legal domain, an unfaithful answer means citing a law that

    says something different from what the LLM claims — a serious liability.

    Does NOT require ground-truth answers. Suitable for production monitoring.



  Answer Relevancy (priority: HIGH)

    Measures whether the answer actually addresses the question asked.

    Uses embeddings to compare the question against the answer semantically.

    Does NOT require ground-truth answers. Suitable for production monitoring.



  Context Recall (priority: MEDIUM — requires ground truth)

    Measures whether the retriever fetched all relevant passages.

    Requires human-annotated ground-truth answers — not available at MVP.

    Kept here as a placeholder for when a golden dataset is curated.



  Why we exclude Context Precision for MVP:

    Context Precision also requires ground truth and is more expensive to

    compute (one LLM call per retrieved chunk). Add it when the golden

    dataset is ready.

"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Ragas metric imports ───────────────────────────────────────────────────────

# Imported at module level so import errors surface immediately at startup,

# not silently at first evaluation run.

from ragas.metrics import answer_relevancy, faithfulness
from ragas.metrics import context_recall  # available but not active at MVP

# ── Active metrics — the set passed to ragas.evaluate() ──────────────────────

# IMPORTANT: These are module-level *instances*, not classes.

# Ragas metric instances carry mutable state (the .llm and .embeddings

# attributes set by ragas_evaluator.py). Using module-level instances means

# the evaluator's LLM configuration persists for the process lifetime.

# This is intentional and documented in ragas_evaluator.py.

#

MVP_METRICS = [faithfulness, answer_relevancy]

# Context recall is here for reference but excluded from MVP_METRICS

# until a ground-truth dataset is available.

ALL_METRICS  = [faithfulness, answer_relevancy, context_recall]

# ── Evaluation thresholds (Test Decision #2 — Ragas gates at e2e tier) ────────

#

# These are the minimum acceptable scores for the CI/CD e2e gate.

# Failing these thresholds triggers a test failure in tests/e2e/test_query_api.py.

# The values are intentionally conservative for MVP; tighten them as the

# system matures.

METRIC_THRESHOLDS: dict[str, float] = {
    "faithfulness":     0.7,   # < 0.7 means LLM is likely hallucinating
    "answer_relevancy": 0.6,   # < 0.6 means answers are off-topic
}

# ── Domain evaluation record ───────────────────────────────────────────────────

@dataclass
class EvaluationRecord:
    """
    A single (query, response, scores) triple — the unit of evaluation work.

    Produced by ``ragas_evaluator.score_response()`` and consumed by

    ``mlflow_tracker.MLflowTracker.log_evaluation_record()``.

    This is a pure data container with no behaviour. Using a dataclass

    (not Pydantic) because it never crosses an API boundary — it stays

    entirely within the ``evaluation/`` bounded context.

    Attributes:
        query:              The original question string.
        answer:             The LLM-generated answer.
        contexts:           List of retrieved chunk texts used as context.
        source_articles:    Article numbers cited (for human inspection).
        llm_provider_used:  Which provider generated the answer.
        faithfulness:       Ragas faithfulness score [0, 1]. None if scoring failed.
        answer_relevancy:   Ragas answer relevancy score [0, 1]. None if scoring failed.
        scoring_error:      Error message if Ragas scoring raised an exception.
                            Storing the error (not raising it) means one bad
                            evaluation question never aborts the entire run.
    """

    query:             str
    answer:            str
    contexts:          list[str]
    source_articles:   list[str]  = field(default_factory=list)
    llm_provider_used: str        = "unknown"

    # Ragas scores — None means "not computed yet" or "scoring failed"
    faithfulness:       float | None = None
    answer_relevancy:   float | None = None

    # Populated when Ragas raises an exception rather than returning scores
    scoring_error: str | None = None

    @property
    def passed_thresholds(self) -> bool:
        """
        Return True if all computed scores meet or exceed METRIC_THRESHOLDS.

        Returns False immediately if ``scoring_error`` is set — a record with
        an evaluation error cannot be considered passing, even if partial scores
        happen to be present. This prevents a partially-scored record (e.g.,
        faithfulness computed before an embedding timeout on answer_relevancy)
        from being incorrectly marked as passing.

        A score of None (not computed) also counts as a failure — if we cannot
        measure quality, we cannot assert it passes.
        """
        if self.scoring_error:
            return False
        for metric_name, threshold in METRIC_THRESHOLDS.items():
            score: float | None = getattr(self, metric_name, None)
            if score is None or score < threshold:
                return False
        return True

    def scores_dict(self) -> dict[str, float | None]:
        """
        Return all metric scores as a flat dict for MLflow logging.

        Only includes metrics that are in MVP_METRICS so we don't log
        None placeholders for metrics we haven't computed.
        """
        return {
            "faithfulness":     self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
        }