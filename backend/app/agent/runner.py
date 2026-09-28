"""
runner.py
Async-friendly wrapper around the existing AutonomousDataScientistAgent.

The orchestrator is CPU/IO-bound (sklearn training, file I/O, LLM calls).
We run it in a ThreadPoolExecutor so FastAPI's event loop stays unblocked,
and we emit SSE progress events via an asyncio.Queue passed in from the
route handler.
"""
from __future__ import annotations
import asyncio
import base64
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

# Ensure the project root is importable (agent_core lives there)
# __file__ is backend/app/agent/runner.py, so the project root is three
# levels up from this file, not four.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agent_core.orchestrator import AutonomousDataScientistAgent, AgentRunResult
from agent_core.chat import DataChatAgent, build_context_md
from ..utils.config import get_settings

settings = get_settings()


# ── In-memory store of completed AgentRunResult objects ──────────────
# Keyed by conversation_id. In a multi-process deployment you'd use Redis.
_run_results: Dict[str, AgentRunResult] = {}


def store_result(conversation_id: str, result: AgentRunResult) -> None:
    _run_results[conversation_id] = result


def get_result(conversation_id: str) -> Optional[AgentRunResult]:
    return _run_results.get(conversation_id)


# ── Progress stage descriptions ──────────────────────────────────────

STAGES = [
    "Loading dataset",
    "Data profiling",
    "Data cleaning",
    "Exploratory analysis",
    "Feature engineering",
    "Model selection",
    "Training models",
    "Evaluating best model",
    "Generating report",
]


def _image_to_base64(path: str) -> Optional[str]:
    """Convert a plot PNG to a base64 data-URI."""
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return None


def _run_agent_sync(
    csv_path: str,
    target_col: str,
    business_objective: str,
    output_dir: str,
    test_size: float,
    cv_folds: int,
    progress_callback,  # callable(stage_index: int)
) -> AgentRunResult:
    """
    Runs the full pipeline synchronously (called in a thread).
    progress_callback is called between stages to emit SSE events.
    """
    from ..services.file_service import get_file_service

    class _ProgressAgent(AutonomousDataScientistAgent):
        """Subclass that emits progress callbacks between stages."""
        def run(self, csv_path, target_col, business_objective=""):
            progress_callback(0)  # Loading
            dataset_path = Path(csv_path)
            extension = dataset_path.suffix.lower().lstrip(".")
            df = get_file_service().read_dataframe(dataset_path, extension)

            progress_callback(1)  # Profiling
            profile = self.profiler.profile(df, target_col=target_col)
            if profile.task_type is None:
                raise ValueError(f"Target column '{target_col}' not found.")

            progress_callback(2)  # Cleaning
            # Get LLM advice on cleaning strategy if available
            cleaning_advice = None
            if self.llm_advisor:
                try:
                    cleaning_advice = self.llm_advisor.advise_cleaning(
                        df=df,
                        profile=profile,
                        business_objective=business_objective,
                    )
                except Exception:
                    pass
            
            cleaned_df = self.cleaner.clean(df, profile, advice=cleaning_advice)
            clean_profile = self.profiler.profile(cleaned_df, target_col=target_col)
            clean_profile.task_type = profile.task_type

            progress_callback(3)  # EDA
            eda_plots = self.eda_engine.run(cleaned_df, clean_profile)

            progress_callback(4)  # Feature engineering
            preprocessor = self.feature_engineer.build_preprocessor(cleaned_df, clean_profile)
            X_train, X_test, y_train, y_test = self.feature_engineer.split(cleaned_df, clean_profile)

            progress_callback(5)  # Model selection
            candidates = self.model_selector.get_candidates(
                task_type=profile.task_type, n_rows=len(cleaned_df), n_features=cleaned_df.shape[1]
            )
            
            # Get LLM advice on model selection if available
            model_advice = None
            if self.llm_advisor:
                try:
                    model_advice = self.llm_advisor.advise_models(
                        task_type=profile.task_type,
                        candidate_models=list(candidates.keys()),
                        n_rows=len(cleaned_df),
                        n_features=cleaned_df.shape[1],
                        business_objective=business_objective,
                    )
                    if model_advice and model_advice.source == "llm" and model_advice.selected_models:
                        candidates = {m: candidates[m] for m in model_advice.selected_models if m in candidates}
                except Exception:
                    pass

            progress_callback(6)  # Training
            from agent_core.trainer import Trainer
            trainer = Trainer(preprocessor=preprocessor, task_type=profile.task_type, cv_folds=self.cv_folds)
            trainer.train_all(candidates, X_train, y_train)
            best = trainer.best()

            progress_callback(7)  # Evaluation
            from agent_core.evaluator import Evaluator
            self.evaluator = Evaluator(output_dir=self.output_dir, task_type=profile.task_type)
            class_names = None
            if self.feature_engineer.label_encoder is not None:
                class_names = list(self.feature_engineer.label_encoder.classes_)
            metrics = self.evaluator.evaluate(best.pipeline, X_test, y_test, class_names=class_names)

            progress_callback(8)  # Report
            dataset_name = os.path.basename(csv_path)
            
            # Generate summary using LLM if available
            summary = None
            if self.narrator:
                try:
                    summary = self.narrator.narrate(
                        dataset_name=dataset_name,
                        business_objective=business_objective or "Not specified.",
                        profile_md=clean_profile.to_markdown(),
                        cleaning_log=self.cleaner.log,
                        feature_log=self.feature_engineer.log,
                        leaderboard_md=trainer.leaderboard_markdown(),
                        best_model_name=best.name,
                        evaluation_md=self.evaluator.metrics_markdown(),
                    )
                except Exception:
                    pass
            
            report_path = self.reporter.generate(
                dataset_name=dataset_name,
                business_objective=business_objective or "Not specified.",
                profile_md=clean_profile.to_markdown(),
                cleaning_log=self.cleaner.log,
                feature_log=self.feature_engineer.log,
                eda_plots=eda_plots,
                leaderboard_md=trainer.leaderboard_markdown(),
                best_model_name=best.name,
                evaluation_md=self.evaluator.metrics_markdown(),
                evaluation_plot=self.evaluator.plot_path,
                summary=summary,
            )

            context_md = build_context_md(
                dataset_name=dataset_name,
                business_objective=business_objective,
                profile_md=clean_profile.to_markdown(),
                cleaning_log=self.cleaner.log,
                feature_log=self.feature_engineer.log,
                leaderboard_md=trainer.leaderboard_markdown(),
                best_model_name=best.name,
                evaluation_md=self.evaluator.metrics_markdown(),
            )
            chat_agent = DataChatAgent(self.llm_client, context_md)

            result = AgentRunResult(
                profile=clean_profile,
                cleaned_df=cleaned_df,
                best_model_name=best.name,
                best_pipeline=best.pipeline,
                metrics=metrics,
                report_path=report_path,
                output_dir=self.output_dir,
                llm_enabled=self.llm_client.available,
                llm_status=self.llm_status,
                chat_agent=chat_agent,
                eda_plots=eda_plots,
                evaluation_plot=self.evaluator.plot_path,
            )
            return result

    agent = _ProgressAgent(
        output_dir=output_dir,
        test_size=test_size,
        cv_folds=cv_folds,
        use_llm=settings.llm_enabled,
        api_key=settings.anthropic_api_key,
        llm_model=settings.llm_model,
    )
    return agent.run(
        csv_path=csv_path,
        target_col=target_col,
        business_objective=business_objective,
    )


async def run_agent_streaming(
    csv_path: str,
    target_col: str,
    business_objective: str,
    output_dir: str,
    test_size: float,
    cv_folds: int,
    conversation_id: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Async generator that yields SSE-style event dicts.
    Runs the agent in a thread and surfaces progress + final results.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def progress_callback(stage_idx: int):
        label = STAGES[stage_idx] if stage_idx < len(STAGES) else "Processing"
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"event": "progress", "data": {"stage": stage_idx, "label": label, "total": len(STAGES)}}
        )

    def _run():
        try:
            result = _run_agent_sync(
                csv_path=csv_path,
                target_col=target_col,
                business_objective=business_objective,
                output_dir=output_dir,
                test_size=test_size,
                cv_folds=cv_folds,
                progress_callback=progress_callback,
            )
            loop.call_soon_threadsafe(queue.put_nowait, {"event": "_done", "data": result})
        except Exception as e:
            tb = traceback.format_exc()
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"event": "error", "data": {"message": str(e), "traceback": tb}}
            )

    # Run the blocking agent in a thread pool
    executor_future = loop.run_in_executor(None, _run)

    result: Optional[AgentRunResult] = None
    while True:
        item = await queue.get()
        if item["event"] == "_done":
            result = item["data"]
            break
        elif item["event"] == "error":
            yield item
            return
        else:
            yield item

    if result is None:
        yield {"event": "error", "data": {"message": "Agent returned no result."}}
        return

    # Store result for subsequent chat calls
    store_result(conversation_id, result)

    # Emit dataset/model cards and charts
    yield {
        "event": "dataset_card",
        "data": {
            "rows": result.profile.n_rows,
            "cols": result.profile.n_cols,
            "task_type": result.profile.task_type,
            "target": result.profile.target_col,
            "duplicates": result.profile.n_duplicates,
            "missing_cols": sum(1 for v in result.profile.missing_pct.values() if v > 0),
        }
    }

    # Emit every plot generated by EDA and test-set evaluation.
    plot_paths = list(getattr(result, "eda_plots", []))
    if getattr(result, "evaluation_plot", None):
        plot_paths.append(result.evaluation_plot)
    seen_paths: set[str] = set()
    for plot_path in plot_paths:
        if not plot_path or plot_path in seen_paths:
            continue
        seen_paths.add(plot_path)
        b64 = _image_to_base64(plot_path)
        if b64:
            yield {
                "event": "chart",
                "data": {
                    "type": "image",
                    "src": b64,
                    "caption": os.path.splitext(os.path.basename(plot_path))[0].replace("_", " ").title()
                }
            }

    # Emit model leaderboard
    if hasattr(result, "metrics"):
        yield {
            "event": "model_card",
            "data": {
                "best_model": result.best_model_name,
                "metrics": result.metrics,
                "task_type": result.profile.task_type,
                "llm_enabled": result.llm_enabled,
            }
        }

    # Emit final narrative text (streamed word-by-word for effect)
    # Read narrative from report
    try:
        with open(result.report_path, "r", encoding="utf-8") as f:
            report_text = f.read()
        try:
            summary = report_text.split("## Summary")[1].strip()
        except IndexError:
            summary = f"Analysis complete. Best model: **{result.best_model_name}**\n\nMetrics: {result.metrics}"
    except Exception:
        summary = f"Analysis complete. Best model: **{result.best_model_name}**"

    # Stream the summary as chunks
    words = summary.split(" ")
    chunk_size = 5
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size]) + (" " if i + chunk_size < len(words) else "")
        yield {"event": "chunk", "data": {"text": chunk}}
        await asyncio.sleep(0.02)

    yield {"event": "done", "data": {"conversation_id": conversation_id}}
