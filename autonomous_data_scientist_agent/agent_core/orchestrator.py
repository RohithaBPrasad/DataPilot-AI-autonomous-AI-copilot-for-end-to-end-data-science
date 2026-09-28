"""
orchestrator.py
THE AGENT
Chooses and runs the analytical pipeline end-to-end:
Profiling -> Cleaning -> EDA -> Feature Engineering -> Model Selection ->
Training -> Evaluation -> Report.

This is the class that behaves as the "autonomous" decision-maker: it reads
the dataset, decides the task type, decides which columns to keep, which
models to try, and which one wins — without the user hand-specifying any of
those choices.

LLM assist (optional): when an Anthropic API key is configured, two of
those decisions (cleaning strategy, model shortlist) are additionally
reviewed by an LLM advisor (agent_core.llm_advisor), and the final report
gets an LLM-written narrative summary plus a chat agent for follow-up
questions. Everything here works exactly as before with no API key — the
LLM layer is fail-soft and every method it touches has a rule-based
fallback.
"""

from __future__ import annotations
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

from .profiler import DataProfiler, DataProfile
from .cleaner import DataCleaner
from .eda import EDAEngine
from .feature_engineer import FeatureEngineer
from .model_selector import ModelSelector
from .trainer import Trainer
from .evaluator import Evaluator
from .reporter import ReportGenerator
from .llm_client import LLMClient, DEFAULT_MODEL
from .llm_advisor import LLMAdvisor, CleaningAdvice, ModelAdvice
from .narrator import Narrator
from .chat import DataChatAgent, build_context_md


@dataclass
class AgentRunResult:
    profile: DataProfile
    cleaned_df: pd.DataFrame
    best_model_name: str
    best_pipeline: object
    metrics: dict
    report_path: str
    output_dir: str
    llm_enabled: bool = False
    llm_status: str = ""
    cleaning_advice: Optional[CleaningAdvice] = None
    model_advice: Optional[ModelAdvice] = None
    chat_agent: Optional[DataChatAgent] = field(default=None, repr=False)


class AutonomousDataScientistAgent:
    """
    Usage:
        agent = AutonomousDataScientistAgent(output_dir="outputs/run1")
        result = agent.run(
            csv_path="data.csv",
            target_col="churn",
            business_objective="Predict customer churn to prioritize retention outreach.",
        )

    LLM assist:
        agent = AutonomousDataScientistAgent(
            output_dir="outputs/run1",
            use_llm=True,                 # default; set False to force rule-only behavior
            api_key="sk-ant-...",         # optional — falls back to ANTHROPIC_API_KEY env var
            llm_model="claude-sonnet-4-6",
        )
    """

    def __init__(
        self,
        output_dir: str = "outputs",
        test_size: float = 0.2,
        cv_folds: int = 5,
        use_llm: bool = True,
        api_key: Optional[str] = None,
        llm_model: str = DEFAULT_MODEL,
    ):
        self.output_dir = output_dir
        self.test_size = test_size
        self.cv_folds = cv_folds
        os.makedirs(self.output_dir, exist_ok=True)

        self.profiler = DataProfiler()
        self.cleaner = DataCleaner()
        self.eda_engine = EDAEngine(output_dir=self.output_dir)
        self.feature_engineer = FeatureEngineer(test_size=test_size)
        self.model_selector = ModelSelector()
        self.evaluator = None  # created after task_type is known
        self.reporter = ReportGenerator(output_dir=self.output_dir)

        self.llm_client = LLMClient(api_key=api_key, model=llm_model, enabled=use_llm)
        self.advisor = LLMAdvisor(self.llm_client)
        self.narrator = Narrator(self.llm_client)

    def run(self, csv_path: str, target_col: str, business_objective: str = "") -> AgentRunResult:
        dataset_name = os.path.basename(csv_path)
        print(f"[Agent] Loading dataset: {csv_path}")
        print(f"[Agent] {self.llm_client.status_message()}")
        df = pd.read_csv(csv_path)

        # ---- Stage 1: Data Profiling ----
        print("[Agent] Stage 1/8: Data Profiling")
        profile = self.profiler.profile(df, target_col=target_col)
        if profile.task_type is None:
            raise ValueError(f"Target column '{target_col}' not found in dataset.")
        self._validate_target(df, target_col, profile.task_type)
        print(f"[Agent]   -> Detected task type: {profile.task_type}")

        # ---- Stage 2: Data Cleaning (LLM-advised) ----
        print("[Agent] Stage 2/8: Data Cleaning")
        cleaning_advice = self.advisor.advise_cleaning(profile, business_objective)
        if cleaning_advice.missing_threshold is not None:
            self.cleaner.missing_threshold = cleaning_advice.missing_threshold
        if cleaning_advice.cap_outliers is not None:
            self.cleaner.cap_outliers = cleaning_advice.cap_outliers
        cleaned_df = self.cleaner.clean(df, profile)
        if cleaning_advice.extra_drop_cols:
            present = [c for c in cleaning_advice.extra_drop_cols if c in cleaned_df.columns]
            if present:
                cleaned_df = cleaned_df.drop(columns=present)
                self.cleaner.log.append(
                    f"[LLM Advisor] Dropped additional column(s) as not relevant to the "
                    f"stated objective: {present}"
                )
        self.cleaner.log.append(f"[LLM Advisor rationale] {cleaning_advice.rationale}")

        # re-profile the cleaned data so EDA/feature stages see accurate types
        clean_profile = self.profiler.profile(cleaned_df, target_col=target_col)
        clean_profile.task_type = profile.task_type  # preserve original decision

        # ---- Stage 3: EDA ----
        print("[Agent] Stage 3/8: Exploratory Data Analysis")
        eda_plots = self.eda_engine.run(cleaned_df, clean_profile)

        # ---- Stage 4: Feature Engineering ----
        print("[Agent] Stage 4/8: Feature Engineering")
        preprocessor = self.feature_engineer.build_preprocessor(cleaned_df, clean_profile)
        X_train, X_test, y_train, y_test = self.feature_engineer.split(cleaned_df, clean_profile)

        # ---- Stage 5: Model Selection (LLM-advised) ----
        print("[Agent] Stage 5/8: Model Selection")
        candidates = self.model_selector.get_candidates(
            task_type=profile.task_type, n_rows=len(cleaned_df), n_features=cleaned_df.shape[1]
        )
        print(f"[Agent]   -> Rule-based candidate models: {list(candidates.keys())}")
        model_advice = self.advisor.advise_models(clean_profile, list(candidates.keys()), business_objective)
        if model_advice.selected_models:
            candidates = {k: v for k, v in candidates.items() if k in model_advice.selected_models}
            print(f"[Agent]   -> LLM-narrowed candidate models: {list(candidates.keys())}")
        print(f"[Agent]   -> Rationale: {model_advice.rationale}")

        # ---- Stage 6: Training ----
        print("[Agent] Stage 6/8: Training & Cross-Validation")
        trainer = Trainer(preprocessor=preprocessor, task_type=profile.task_type, cv_folds=self.cv_folds)
        trainer.train_all(candidates, X_train, y_train)
        best = trainer.best()
        print(f"[Agent]   -> Best model: {best.name} (CV score {best.cv_mean:.4f})")

        # ---- Stage 7: Evaluation ----
        print("[Agent] Stage 7/8: Evaluation")
        self.evaluator = Evaluator(output_dir=self.output_dir, task_type=profile.task_type)
        class_names = None
        if self.feature_engineer.label_encoder is not None:
            class_names = list(self.feature_engineer.label_encoder.classes_)
        metrics = self.evaluator.evaluate(best.pipeline, X_test, y_test, class_names=class_names)
        print(f"[Agent]   -> Metrics: {metrics}")

        # ---- Stage 8: Report (LLM-narrated) ----
        print("[Agent] Stage 8/8: Report Generation")
        leaderboard_md = trainer.leaderboard_markdown()
        evaluation_md = self.evaluator.metrics_markdown()

        agent_decisions_md = (
            "## Agent Decisions\n\n"
            f"**Cleaning strategy** ({cleaning_advice.source}): {cleaning_advice.rationale}\n\n"
            f"**Model shortlist** ({model_advice.source}): {model_advice.rationale}"
        )

        narrative_md = self.narrator.narrate(
            dataset_name=dataset_name,
            business_objective=business_objective,
            profile_md=clean_profile.to_markdown(),
            cleaning_log=self.cleaner.log,
            feature_log=self.feature_engineer.log,
            leaderboard_md=leaderboard_md,
            best_model_name=best.name,
            evaluation_md=evaluation_md,
        )

        report_path = self.reporter.generate(
            dataset_name=dataset_name,
            business_objective=business_objective or "Not specified.",
            profile_md=clean_profile.to_markdown(),
            cleaning_log=self.cleaner.log,
            feature_log=self.feature_engineer.log,
            eda_plots=eda_plots,
            leaderboard_md=leaderboard_md,
            best_model_name=best.name,
            evaluation_md=evaluation_md,
            evaluation_plot=self.evaluator.plot_path,
            narrative_md=narrative_md,
            agent_decisions_md=agent_decisions_md,
        )
        print(f"[Agent] Done. Report saved to: {report_path}")

        # Build a ready-to-use chat agent grounded in this run's context.
        context_md = build_context_md(
            dataset_name=dataset_name,
            business_objective=business_objective,
            profile_md=clean_profile.to_markdown(),
            cleaning_log=self.cleaner.log,
            feature_log=self.feature_engineer.log,
            leaderboard_md=leaderboard_md,
            best_model_name=best.name,
            evaluation_md=evaluation_md,
            agent_decisions_md=agent_decisions_md,
        )
        chat_agent = DataChatAgent(self.llm_client, context_md)

        return AgentRunResult(
            profile=clean_profile,
            cleaned_df=cleaned_df,
            best_model_name=best.name,
            best_pipeline=best.pipeline,
            metrics=metrics,
            report_path=report_path,
            output_dir=self.output_dir,
            llm_enabled=self.llm_client.available,
            llm_status=self.llm_client.status_message(),
            cleaning_advice=cleaning_advice,
            model_advice=model_advice,
            chat_agent=chat_agent,
        )

    @staticmethod
    def _validate_target(df: pd.DataFrame, target_col: str, task_type: str) -> None:
        """Raise a clear, actionable error if the chosen target looks like an
        identifier column (e.g. a customer ID) rather than something
        meaningful to predict — instead of letting a downstream model
        crash on it."""
        n_rows = len(df)
        nunique = df[target_col].nunique(dropna=True)
        if task_type == "classification" and n_rows > 0:
            unique_ratio = nunique / n_rows
            if nunique > 50 and unique_ratio > 0.5:
                raise ValueError(
                    f"The target column '{target_col}' has {nunique} unique values across "
                    f"{n_rows} rows ({unique_ratio:.0%} unique) — this looks like an identifier "
                    f"column (e.g. a customer ID or row number), not something to predict. "
                    f"Please choose a different target column, such as an outcome label "
                    f"(e.g. Churn, Category, Approved) or a numeric quantity to predict."
                )
