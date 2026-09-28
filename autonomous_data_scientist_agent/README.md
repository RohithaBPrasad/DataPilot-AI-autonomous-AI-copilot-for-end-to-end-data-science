# Autonomous Data Scientist Agent

An AI agent that automatically performs data analysis and machine-learning
workflows from raw datasets — matching the pipeline:

```
Data Profiling → Cleaning → EDA → Feature Engineering → Model Selection → Training → Evaluation → Report
```

The agent inspects a dataset, autonomously decides whether the task is
classification or regression, cleans and transforms the data, generates
visual EDA, trains and cross-validates several candidate models
(Logistic/Linear Regression, Random Forest, KNN, SVM, XGBoost), picks the
best one, evaluates it on a held-out test set, and writes a complete Markdown
report with embedded charts.

Optionally, an LLM (Claude, via the Anthropic API) sits on top of that
rule-based pipeline as a genuine agentic layer: it can review and adjust the
cleaning strategy and model shortlist, it writes the report's executive
summary in plain language, and it powers a chat tab for asking follow-up
questions about a completed run. All of this is opt-in and fail-soft — with
no API key configured, the pipeline runs exactly as the pure rule-based
version above.

## Project structure

```
autonomous_data_scientist_agent/
├── main.py                        # CLI entry point
├── app.py                         # Streamlit web app (upload → run → view/download)
├── requirements.txt
├── agent_core/
│   ├── profiler.py                # Stage 1: Data Profiling
│   ├── cleaner.py                 # Stage 2: Data Cleaning
│   ├── eda.py                     # Stage 3: EDA (plots)
│   ├── feature_engineer.py        # Stage 4: Feature Engineering
│   ├── model_selector.py          # Stage 5: Model Selection
│   ├── trainer.py                 # Stage 6: Training + CV
│   ├── evaluator.py               # Stage 7: Evaluation
│   ├── reporter.py                # Stage 8: Report Generation
│   ├── orchestrator.py            # The Agent: runs all 8 stages
│   ├── llm_client.py              # Fail-soft wrapper around the Anthropic API
│   ├── llm_advisor.py             # Agentic layer: LLM-advised cleaning & model shortlist
│   ├── narrator.py                # LLM-written report executive summary
│   └── chat.py                    # "Ask the Agent" — Q&A over a completed run
├── sample_data/
│   └── make_sample_dataset.py     # Generates a synthetic churn dataset
└── outputs/                       # Report + plots land here after a run
```

## Web app (recommended)

The project includes a Streamlit app (`app.py`) that turns the agent into a
point-and-click tool: upload a CSV, pick the target column, click **Run
Agent**, and browse the profiling summary, EDA charts, model leaderboard,
and evaluation results in tabs — with one-click download of the report and
all plots as a zip.

```powershell
python -m streamlit run app.py
```

This opens a browser tab (usually `http://localhost:8501`). Use
`python -m streamlit run app.py` rather than a bare `streamlit run app.py` —
on Windows, `streamlit.exe` isn't always on PATH, but `python -m streamlit`
always works once it's installed in your active virtual environment.

To make it deployable elsewhere, either:
- Push this folder to a GitHub repo and deploy for free on
  [Streamlit Community Cloud](https://streamlit.io/cloud) (point it at
  `app.py`), or
- Containerize it (`Dockerfile` running
  `CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]`)
  and deploy to any host that runs Docker (Render, Railway, Azure
  Container Apps, etc.).

## LLM / agent features (optional)

Set an Anthropic API key and three things activate automatically, both in
the CLI and the Streamlit app:

1. **Agentic decisions** (`agent_core/llm_advisor.py`) — before cleaning,
   the LLM reviews the data profile and business objective and may adjust
   the missing-data threshold, toggle outlier capping, or flag extra
   columns to drop (never the target column). Before training, it may
   narrow the rule-selected model shortlist down to the models it judges
   most worth training. Every suggestion is validated against the actual
   dataset/candidate list before it's allowed to affect the run — the LLM
   can only pick from options the rule-based stages already vetted, never
   invent new ones.
2. **Narrative report summary** (`agent_core/narrator.py`) — the report's
   `## Summary` section becomes an LLM-written, plain-language executive
   summary grounded in the actual profile/logs/leaderboard/metrics, ending
   with concrete next-step recommendations.
3. **"Ask the Agent" chat** (`agent_core/chat.py`) — a chat tab in the
   Streamlit app (and a `result.chat_agent` object from the CLI/library)
   for asking follow-up questions about a completed run, answered from that
   run's actual context.

Every one of these has a rule-based/templated fallback and never raises —
if the key is missing, the `anthropic` package isn't installed, or a call
fails (network, rate limit, bad JSON), the pipeline behaves exactly as the
plain rule-based version.

**Setup:**

```powershell
python -m pip install anthropic   # already in requirements.txt
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # PowerShell, current session only
```

Or pass a key directly:

```powershell
python main.py --csv sample_data\customer_churn.csv --target Churn `
    --objective "Predict churn." --api-key sk-ant-...
```

In the Streamlit app, expand **🧠 LLM / Agent settings** in the sidebar to
paste a key, pick a model, or turn LLM features off entirely for a given
run.

CLI flags:

| Flag | Description | Default |
|---|---|---|
| `--no-llm` | Force rule-only behavior even if a key is set | off |
| `--api-key` | Anthropic API key (else reads `ANTHROPIC_API_KEY`) | — |
| `--llm-model` | Anthropic model ID | `claude-sonnet-4-6` |

Model IDs change over time — check
[Anthropic's models overview](https://docs.claude.com/en/docs/about-claude/models/overview)
for the current lineup before relying on a specific string in production.

## Setup in VS Code (Windows)

1. Open the `autonomous_data_scientist_agent` folder in VS Code
   (`File → Open Folder…`).
2. Open a PowerShell terminal in VS Code (`` Ctrl+` ``).
3. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```
   (If PowerShell blocks the script, run
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.)
4. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
5. In VS Code, select this `venv` as the interpreter
   (`Ctrl+Shift+P → Python: Select Interpreter`).

## Try it immediately with sample data

```powershell
python sample_data\make_sample_dataset.py
python main.py --csv sample_data\customer_churn.csv --target Churn --objective "Predict customer churn to prioritize retention outreach."
```

Open `outputs\report.md` (VS Code renders Markdown with images — press
`Ctrl+Shift+V` to preview) to see the full profiling summary, cleaning log,
EDA charts, model leaderboard, and evaluation metrics.

## Running on your own dataset

```powershell
python main.py --csv path\to\your_data.csv --target YourTargetColumn --objective "Describe the business goal here." --output-dir outputs\my_run
```

CLI options:

| Flag | Description | Default |
|---|---|---|
| `--csv` | Path to input CSV (required) | — |
| `--target` | Column to predict (required) | — |
| `--objective` | Free-text business context, included in the report | `""` |
| `--output-dir` | Where plots/report are written | `outputs` |
| `--test-size` | Fraction held out for testing | `0.2` |
| `--cv-folds` | Cross-validation folds during training | `5` |

## How the agent makes decisions

- **Task type**: classification if the target is text/categorical or has
  few unique integer values; otherwise regression.
- **Cleaning**: drops constant columns, drops identifier-like
  high-cardinality columns (e.g. IDs), drops columns with excessive
  missingness, imputes remaining missing values (median/mode), removes
  duplicate rows, caps outliers with the IQR rule, and expands detected
  date columns into year/month/day-of-week features.
- **Feature engineering**: numeric columns are median-imputed + scaled,
  categorical columns are most-frequent-imputed + one-hot encoded, all
  inside a single scikit-learn `ColumnTransformer`.
- **Model selection**: shortlists 4–5 candidate models appropriate to the
  task type and dataset size (e.g. skips SVM/KNN on very large datasets).
- **Training**: every candidate is cross-validated inside the full
  preprocessing pipeline; the highest mean CV score wins.
- **Evaluation**: accuracy/precision/recall/F1 + confusion matrix for
  classification, or MAE/RMSE/R² + residual plots for regression.
- **Report**: everything above is assembled into `outputs/report.md`.

## Extending the agent

- Swap in your own models in `agent_core/model_selector.py`.
- Add hyperparameter tuning (e.g. `GridSearchCV`) inside `trainer.py`.
- Give the LLM advisor more decisions to make (e.g. feature-engineering
  choices) by adding a method to `agent_core/llm_advisor.py` following the
  same pattern: build a prompt, call `client.complete_json`, validate/clamp
  the result against the actual dataset, and fall back to the existing
  default when the LLM is unavailable.
- Add a `--config.yaml` if you want to override thresholds
  (missing-value cutoff, outlier capping, etc.) without touching code.
