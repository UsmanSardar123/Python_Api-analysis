# AI-Powered Website Link Analysis API

Production-minded **FastAPI** backend application that extracts factual content from public websites with **SSRF protection** and generates a structured **5-part AI marketing, SEO, and competitor analysis** using **Google Gemini** (`gemini-2.5-flash`) and **OpenAI** (`gpt-4o-mini` fallback).

## Repository

- **GitHub Repository**: https://github.com/UsmanSardar123/Python_Api-analysis
- **Full Documentation**: [`ai-link-analysis/README.md`](./ai-link-analysis/README.md)
- **Final Verification Report**: [`FINAL_VERIFICATION_REPORT.md`](./FINAL_VERIFICATION_REPORT.md)
- **Render Blueprint**: [`render.yaml`](./render.yaml)

## Quick Start

```bash
cd ai-link-analysis
pip install -r requirements.txt
cp .env.example .env
# Set GEMINI_API_KEY in .env (keep ENABLE_DEMO_MODE_WITHOUT_API_KEY=false)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Run Automated Tests (57 Passing)

```bash
pytest ai-link-analysis/tests/test_link_analysis.py -v
```

## Run Live 3-Website Gemini Verification

```bash
python ai-link-analysis/verify_live_gemini.py
```
