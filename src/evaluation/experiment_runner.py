"""
Evaluation experiment orchestrator for the Egyptian Law Assistant.

Responsibilities:
  - Define the test question set for MVP evaluation.
  - For each question: run the query pipeline, score with Ragas, log to MLflow.
  - Return a summary of all scored records for inspection or further analysis.

Orchestration contract:
  This module is the only caller of ``execute_query()``, ``score_response()``,
  and ``MLflowTracker`` in combination. It knows about all three bounded
  contexts (query_engine, evaluation) but introduces no new logic of its own
  — it is pure orchestration.

  It does NOT import ``mlflow`` directly. All MLflow calls flow through
  ``MLflowTracker``, maintaining the isolation contract from Code Quality
  Decision #4.

Async note:
  ``execute_query()`` is an async function (Performance Decision #4).
  ``score_response()`` and ``MLflowTracker`` methods are synchronous.
  The runner uses ``asyncio.run()`` at the CLI entry point and
  ``await execute_query()`` inside an async orchestrator so the event
  loop is never blocked.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.core.config import Settings, get_settings
from src.core.exceptions import EgyptianLawAssistantError
from src.core.schemas import QueryRequest
from src.evaluation.metrics import EvaluationRecord
from src.evaluation.mlflow_tracker import MLflowTracker
from src.evaluation.ragas_evaluator import score_response
from src.query_engine.query_pipeline import execute_query

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── MVP Test Question Set ──────────────────────────────────────────────────────

#
# These questions cover the core legal concepts present in the ingested corpus.
# Each question should have at least one relevant article in the ChromaDB index.
# Expand this list as the corpus grows or as specific weak spots are identified
# through prior evaluation runs.
#
# Format: plain Arabic question strings — no ground-truth answers needed for
# the two MVP metrics (faithfulness, answer_relevancy).
DEFAULT_EVAL_QUESTIONS: list[str] = [
    "ما هي شروط تأسيس شركة المساهمة في القانون المصري؟",
    "ما هي البيانات الواجب توافرها في عقد الشركة؟",
    "متى تكتسب الشركة الشخصية الاعتبارية وفقاً للقانون؟",
]

# ── Result container ───────────────────────────────────────────────────────────

@dataclass
class ExperimentResult:
    """
    Summary of a complete evaluation run.

    Returned by ``run_evaluation()`` and printed by ``main()``.
    Also available to the ``scripts/run_evaluation.py`` CLI entry point
    for programmatic use (e.g., CI pass/fail gating).

    Attributes:
        run_id:       MLflow run ID, usable for direct UI deep-link.
        records:      All scored ``EvaluationRecord`` objects, one per question.
        n_passed:     Number of questions that met all metric thresholds.
        n_failed:     Number of questions below at least one threshold.
        n_errored:    Number of questions where scoring raised an exception.
        mean_faithfulness:     Mean faithfulness across scored questions.
        mean_answer_relevancy: Mean answer relevancy across scored questions.
    """
    run_id:                 str
    records:                list[EvaluationRecord] = field(default_factory=list)
    n_passed:               int = 0
    n_failed:               int = 0
    n_errored:              int = 0
    mean_faithfulness:      float | None = None
    mean_answer_relevancy:  float | None = None

    @property
    def all_passed(self) -> bool:
        """True only if every question met the thresholds and none errored."""
        return self.n_passed == len(self.records) and self.n_errored == 0

# ── Core orchestrator ──────────────────────────────────────────────────────────

async def run_evaluation(
    questions: list[str] | None = None,
    settings: Settings | None = None,
    run_name: str | None = None,
    persist_dir: str = "./chroma_db",
) -> ExperimentResult:
    """
    Run a full evaluation experiment: query → score → log → summarise.

    For each question in ``questions``:
      1. Build a ``QueryRequest`` and call ``execute_query()`` (async).
      2. Pass the ``QueryResponse`` to ``score_response()`` (sync Ragas).
      3. Log the ``EvaluationRecord`` to MLflow via ``MLflowTracker``.

    All steps for a single question are wrapped in a try/except so one
    failing question (e.g., Ollama timeout on a complex query) never
    aborts the experiment — the error is recorded and the run continues.

    Args:
        questions:   List of Arabic question strings to evaluate.
                     Defaults to ``DEFAULT_EVAL_QUESTIONS`` if None.
        settings:    Active settings. Defaults to global singleton.
        run_name:    Human-readable MLflow run name shown in the UI.
                     Auto-generated from config if None.
        persist_dir: ChromaDB directory — must match the ingestion run.

    Returns:
        An ``ExperimentResult`` with all records and aggregate statistics.
    """
    active_settings = settings or get_settings()
    eval_questions  = questions or DEFAULT_EVAL_QUESTIONS

    # Auto-generate a descriptive run name if none provided
    if run_name is None:
        run_name = (
            f"{active_settings.llm_provider}"
            f"_{active_settings.ollama_model}"
            f"_chunk{active_settings.chunk_size}"
            f"_top{active_settings.chunk_overlap}"
        )

    logger.info(
        "Starting evaluation run: %d questions  run_name=%r  provider=%r",
        len(eval_questions),
        run_name,
        active_settings.llm_provider,
    )

    tracker = MLflowTracker(active_settings)
    records: list[EvaluationRecord] = []

    with tracker.start_run(run_name=run_name) as run_id:

        # Log the experiment configuration first so it's available even
        # if the run is interrupted mid-way.
        tracker.log_config_params(active_settings)

        for step, question in enumerate(eval_questions):
            logger.info(
                "Question %d/%d: %r",
                step + 1,
                len(eval_questions),
                question[:60],
            )

            record: EvaluationRecord | None = None

            # ── Step A: Run the query pipeline ───────────────────────────────
            try:
                request  = QueryRequest(query=question, top_k=5)
                response = await execute_query(
                    request=request,
                    settings=active_settings,
                    persist_dir=persist_dir,
                )
            except EgyptianLawAssistantError as exc:
                # Domain errors (empty retrieval, LLM failure, etc.) are
                # non-fatal for the experiment run — log and continue.
                logger.error(
                    "Query failed for question %d (%r): %s",
                    step,
                    question[:40],
                    exc.message,
                )
                record = EvaluationRecord(
                    query=question,
                    answer="",
                    contexts=[],
                    scoring_error=f"Query pipeline error: {exc.message}",
                )
                records.append(record)
                tracker.log_evaluation_record(record, step=step)
                continue

            except Exception as exc:
                # Unexpected errors are also non-fatal — logged with full context.
                logger.exception(
                    "Unexpected error during query for question %d: %s", step, exc
                )
                record = EvaluationRecord(
                    query=question,
                    answer="",
                    contexts=[],
                    scoring_error=f"Unexpected error: {type(exc).__name__}: {exc}",
                )
                records.append(record)
                tracker.log_evaluation_record(record, step=step)
                continue

            # ── Step B: Score with Ragas ──────────────────────────────────────
            # score_response() never raises — it catches Ragas exceptions
            # internally and stores them in record.scoring_error.
            record = score_response(
                query=question,
                response=response,
                settings=active_settings,
            )
            records.append(record)

            # ── Step C: Log to MLflow ──────────────────────────────────────────
            tracker.log_evaluation_record(record, step=step)

        # ── Aggregate and log summary ──────────────────────────────────────────
        tracker.log_aggregate_metrics(records)

    # ── Build ExperimentResult ─────────────────────────────────────────────────
    def _mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    faith_vals = [r.faithfulness     for r in records if r.faithfulness     is not None]
    relev_vals = [r.answer_relevancy  for r in records if r.answer_relevancy is not None]

    result = ExperimentResult(
        run_id                = run_id,
        records               = records,
        n_passed              = sum(1 for r in records if r.passed_thresholds),
        n_failed              = sum(1 for r in records if not r.passed_thresholds and not r.scoring_error),
        n_errored             = sum(1 for r in records if r.scoring_error),
        mean_faithfulness     = _mean(faith_vals),
        mean_answer_relevancy = _mean(relev_vals),
    )

    logger.info(
        "Evaluation complete: passed=%d  failed=%d  errored=%d  run_id=%r",
        result.n_passed,
        result.n_failed,
        result.n_errored,
        result.run_id,
    )
    return result

# ── CLI / Inspection Entry Point ───────────────────────────────────────────────

async def _main_async() -> None:
    """
    Async body of the CLI entry point.

    Separated from ``main()`` so ``asyncio.run()`` is only called once at
    the outermost level, avoiding nested event loop issues in Jupyter.
    """
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"\n{'=' * 60}")
    print("  Egyptian Law Assistant — Evaluation Runner")
    print(f"{'=' * 60}\n")

    print(f"  Questions  : {len(DEFAULT_EVAL_QUESTIONS)}")
    print(f"  Metrics    : faithfulness, answer_relevancy")
    print(f"  MLflow URI : {get_settings().mlflow_tracking_uri}")
    print(f"  Experiment : {get_settings().mlflow_experiment_name}\n")

    result = await run_evaluation()

    # ── Print per-question results ─────────────────────────────────────────────
    print(f"{'─' * 60}")
    print("  PER-QUESTION RESULTS")
    print(f"{'─' * 60}")

    for i, record in enumerate(result.records, 1):
        status = "✓ PASS" if record.passed_thresholds else ("✗ ERR " if record.scoring_error else "✗ FAIL")
        faith  = f"{record.faithfulness:.3f}"     if record.faithfulness     is not None else "N/A "
        relev  = f"{record.answer_relevancy:.3f}" if record.answer_relevancy is not None else "N/A "
        print(f"\n  [{i}] {status}  faith={faith}  relevancy={relev}")
        print(f"       Q: {record.query[:70]}")
        if record.scoring_error:
            print(f"       Error: {record.scoring_error[:80]}")
        elif record.source_articles:
            print(f"       Cited: {', '.join(record.source_articles[:5])}")

    # ── Print run summary ──────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("  RUN SUMMARY")
    print(f"{'─' * 60}")
    mf = f"{result.mean_faithfulness:.3f}"     if result.mean_faithfulness     is not None else "N/A"
    mr = f"{result.mean_answer_relevancy:.3f}" if result.mean_answer_relevancy is not None else "N/A"
    print(f"  Mean faithfulness     : {mf}")
    print(f"  Mean answer relevancy : {mr}")
    print(f"  Passed / Total        : {result.n_passed}/{len(result.records)}")
    print(f"  MLflow run ID         : {result.run_id}")
    print(f"  MLflow UI             : {get_settings().mlflow_tracking_uri}")
    print(f"\n  View results: open {get_settings().mlflow_tracking_uri}")
    print(f"{'=' * 60}\n")

    # Exit with code 1 if thresholds not met — enables CI pass/fail gating
    if not result.all_passed:
        sys.exit(1)

def main() -> None:
    """CLI entry point — wraps async main in asyncio.run()."""
    asyncio.run(_main_async())

if __name__ == "__main__":
    main()