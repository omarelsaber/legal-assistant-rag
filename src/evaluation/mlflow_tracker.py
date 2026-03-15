"""
MLflow experiment tracking for the Egyptian Law Assistant.

ISOLATION CONTRACT:
  This is the ONLY file in the entire project that imports ``mlflow``.
  All other modules that need to record experiment data call methods on
  ``MLflowTracker`` — they never import mlflow directly.

  Consequence: removing or replacing MLflow requires changing exactly
  this one file. The experiment_runner, evaluator, and API layer are
  completely decoupled from the tracking backend.

MLflow concepts used here:
  Experiment  — a named group of related runs (one per project, e.g.
                "egyptian-law-rag"). Created automatically if absent.
  Run         — one evaluation pass with a specific config. Contains
                params (inputs) and metrics (outputs).
  Params      — string key-value pairs logged once per run: model names,
                chunk sizes, provider names.
  Metrics     — float key-value pairs: faithfulness, answer_relevancy.
                Can be logged multiple times per run (with a step) to
                track per-question progression within a run.
  Tags        — string metadata attached to runs for filtering in the UI.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import mlflow

from src.core.config import Settings, get_settings
from src.evaluation.metrics import EvaluationRecord, METRIC_THRESHOLDS

logger = logging.getLogger(__name__)

class MLflowTracker:
    """
    Thin wrapper around MLflow that speaks in domain terms.

    Usage pattern (context manager — recommended):

        tracker = MLflowTracker(settings)
        with tracker.start_run(run_name="chunk_size_512") as run_id:
            tracker.log_config_params(settings)
            for record in evaluation_records:
                tracker.log_evaluation_record(record)
            tracker.log_aggregate_metrics(evaluation_records)

    Usage pattern (manual — for scripts that manage their own run lifecycle):

        tracker = MLflowTracker(settings)
        tracker.start_active_run(run_name="experiment_1")
        tracker.log_config_params(settings)
        # ... log records ...
        tracker.end_run()

    Args:
        settings: Active Settings singleton. Used to configure the MLflow
                  tracking URI and experiment name at construction time.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        mlflow.set_tracking_uri(self._settings.mlflow_tracking_uri)
        mlflow.set_experiment(self._settings.mlflow_experiment_name)
        logger.info(
            "MLflowTracker initialised: uri=%r  experiment=%r",
            self._settings.mlflow_tracking_uri,
            self._settings.mlflow_experiment_name,
        )

    # ── Context manager interface ──────────────────────────────────────────────

    @contextmanager
    def start_run(
        self,
        run_name: str | None = None,
    ) -> Generator[str, None, None]:
        """
        Context manager that starts an MLflow run and yields the run ID.

        The run is ended automatically (with status=FINISHED) when the
        context exits normally, or marked FAILED if an exception propagates.

        Args:
            run_name: Human-readable label shown in the MLflow UI.
                      Defaults to an auto-generated timestamp-based name.

        Yields:
            The MLflow run ID string (useful for linking to artifacts).
        """
        with mlflow.start_run(run_name=run_name) as active_run:
            run_id = active_run.info.run_id
            logger.info("MLflow run started: id=%r  name=%r", run_id, run_name)
            try:
                yield run_id
            except Exception:
                mlflow.set_tag("run_status", "FAILED")
                raise
            else:
                mlflow.set_tag("run_status", "FINISHED")

    # ── Logging methods ────────────────────────────────────────────────────────

    def log_config_params(self, settings: Settings) -> None:
        """
        Log the active experiment configuration as MLflow params.

        Params are logged once per run and appear in the "Parameters" tab
        of the MLflow UI. They represent the inputs that define a run's
        identity — useful for comparing runs in the experiment view.

        Logged params:
          embedding_model, chunk_size, chunk_overlap, llm_provider,
          ollama_model, mlflow_experiment_name, ragas_faithfulness_threshold,
          ragas_answer_relevancy_threshold.

        Args:
            settings: The settings instance whose values to log.
                      Must be called inside an active MLflow run.
        """
        mlflow.log_params(
            {
                "embedding_model":                  settings.embedding_model,
                "chunk_size":                       settings.chunk_size,
                "chunk_overlap":                    settings.chunk_overlap,
                "llm_provider":                     settings.llm_provider,
                "ollama_model":                     settings.ollama_model,
                "ragas_faithfulness_threshold":     settings.ragas_faithfulness_threshold,
                "ragas_answer_relevancy_threshold":  settings.ragas_answer_relevancy_threshold,
            }
        )
        logger.debug("Logged config params to MLflow.")

    def log_evaluation_record(
        self,
        record: EvaluationRecord,
        step: int = 0,
    ) -> None:
        """
        Log the Ragas scores from a single ``EvaluationRecord`` to MLflow.

        Scores are logged as metrics with a ``step`` so the MLflow UI can
        plot per-question score progression within a run. Step 0 is the
        first question, step 1 the second, etc.

        If ``record.scoring_error`` is set (Ragas failed), the error is
        logged as a tag rather than silently swallowed. This makes scoring
        failures visible in the MLflow UI without crashing the run.

        Args:
            record: A scored ``EvaluationRecord`` from ``ragas_evaluator``.
            step:   The question index within this run (0-based).
        """
        if record.scoring_error:
            mlflow.set_tag(
                f"scoring_error_step_{step}",
                record.scoring_error[:250],  # MLflow tag value limit
            )
            logger.warning(
                "Step %d: scoring error logged as tag: %s",
                step,
                record.scoring_error,
            )
            return

        # Log per-question scores at the given step
        metrics_to_log: dict[str, float] = {}
        for metric_name, score in record.scores_dict().items():
            if score is not None:
                metrics_to_log[metric_name] = score

        if metrics_to_log:
            mlflow.log_metrics(metrics_to_log, step=step)

        # Log question + answer as a tag for human inspection in the MLflow UI
        # (truncated — MLflow tag values are limited to 5000 chars)
        mlflow.set_tag(f"question_step_{step}", record.query[:200])
        mlflow.set_tag(f"provider_step_{step}", record.llm_provider_used)

        passed = record.passed_thresholds
        mlflow.set_tag(f"passed_thresholds_step_{step}", str(passed))

        logger.info(
            "Step %d logged: faithfulness=%.3f  answer_relevancy=%.3f  passed=%s",
            step,
            record.faithfulness     or 0.0,
            record.answer_relevancy or 0.0,
            passed,
        )

    def log_aggregate_metrics(
        self,
        records: list[EvaluationRecord],
    ) -> None:
        """
        Log mean scores across all records as summary metrics for this run.

        These appear as the run's top-level metrics in the MLflow experiment
        view, making it easy to compare runs at a glance without opening
        individual steps.

        Args:
            records: All ``EvaluationRecord`` objects produced in this run.
                     Records with ``None`` scores are excluded from the mean.
        """
        def _mean(values: list[float]) -> float | None:
            return sum(values) / len(values) if values else None

        faith_scores = [r.faithfulness     for r in records if r.faithfulness     is not None]
        relev_scores = [r.answer_relevancy  for r in records if r.answer_relevancy is not None]

        summary: dict[str, float] = {}
        mean_faith = _mean(faith_scores)
        mean_relev = _mean(relev_scores)

        if mean_faith is not None:
            summary["mean_faithfulness"]     = mean_faith
        if mean_relev is not None:
            summary["mean_answer_relevancy"] = mean_relev

        if summary:
            mlflow.log_metrics(summary)
            logger.info("Aggregate metrics logged: %s", summary)

        # Overall pass/fail tag for the run
        n_passed = sum(1 for r in records if r.passed_thresholds)
        mlflow.set_tag("questions_passed", f"{n_passed}/{len(records)}")
        mlflow.set_tag("thresholds", str(METRIC_THRESHOLDS))

        logger.info(
            "Run summary: %d/%d questions passed thresholds.",
            n_passed,
            len(records),
        )