import pandas as pd

from agent_core.orchestrator import AgentRunResult


def test_agent_run_result_supports_chat_agent():
    result = AgentRunResult(
        profile=type("P", (), {"task_type": "classification"})(),
        cleaned_df=pd.DataFrame({"x": [1, 2, 3]}),
        best_model_name="model",
        best_pipeline=None,
        metrics={"accuracy": 0.9},
        report_path="/tmp/report.md",
        output_dir="/tmp",
        chat_agent=None,
    )

    assert result.chat_agent is None
