GEO Audit with AG2 v0.10.0

1) Setup
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- cp .env.example .env and set GEMINI_API_KEY or OPENAI_API_KEY

2) Run the full pipeline (single command):
- python ag2_pipeline.py https://example.com

Outputs written to working directory:
- examples/sample_report.json     (summary JSON)
- ag2_report.md                   (AG2 synthesized report) OR fallback_report.md
- example_robots.txt
- example_llms.txt

Notes:
- This pipeline sends ONLY the summary JSON to AG2 (no raw HTML)
- If AG2/Gemini (or OpenAI) key is missing or AG2 fails, a robust local fallback produces fallback_report.md
