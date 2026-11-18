# AI-Powered Website Link Analysis API

This repository contains the complete **AI-Powered Website Link Analysis API** built with Python, FastAPI, Uvicorn, Pydantic v2, HTTPX, BeautifulSoup4, and Google Gemini / OpenAI.

- **Application Root**: [`ai-link-analysis/`](./ai-link-analysis/)
- **Full Documentation & LLM Research**: [`ai-link-analysis/README.md`](./ai-link-analysis/README.md)

## Quick Start

```bash
cd ai-link-analysis
pip install -r requirements.txt
cp .env.example .env
# Add your GEMINI_API_KEY or OPENAI_API_KEY to .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run Tests
```bash
pytest ai-link-analysis/tests/test_link_analysis.py -v
```
