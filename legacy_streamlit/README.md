# Legacy Streamlit Application

This is the original Streamlit-based prototype.
The production application is now at `backend/` (FastAPI) + `frontend/` (Next.js).

## Run the legacy Streamlit app

```bash
# From the project root, with venv activated:
python -m streamlit run legacy_streamlit/app.py
```

Note: The `agent_core` package is at the project root so imports still resolve.
