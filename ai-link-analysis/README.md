# AI-Powered Website Link Analysis API

A production-minded, asynchronous **FastAPI** backend application that fetches any public website URL with defense-in-depth **SSRF protection**, extracts clean factual content using **HTTPX** and **BeautifulSoup4**, and generates a comprehensive, schema-validated **5-part marketing, SEO, and competitive intelligence report** powered by **Google Gemini** (`gemini-2.5-flash`) with optional **OpenAI** (`gpt-4o-mini`) fallback.

---

## 1. Project Overview

Modern growth, SEO, and product marketing teams spend hours manually auditing websites, researching competitors, mapping customer search intent across social/search platforms, and identifying target audiences.

The **AI-Powered Website Link Analysis API** (`POST /link-analysis`) automates this workflow end-to-end:
1. **Validates & Secures**: Enforces strict URL validation, blocks private/loopback/link-local/metadata IP ranges (SSRF protection), validates every redirect hop, enforces per-IP sliding-window rate limiting, and applies response timeout and byte-size limits.
2. **Extracts Ground-Truth Website Facts**: Parses HTML with BeautifulSoup4, stripping `<script>`, `<style>`, `<nav>`, `<footer>`, and duplicate boilerplate while extracting the page title, meta description, canonical URL, H1–H3 headings, clean body paragraphs, internal/external links, and business signals (emails, phone numbers, social links, JSON-LD `Schema.org` types, and CTAs).
3. **Generates 5 Structured AI Analysis Sections**: Uses **Google Gemini** (`gemini-2.5-flash`) structured JSON outputs validated through **Pydantic v2** to return:
   - **Section 1: Competitor Analysis**
   - **Section 2: Target Search Queries** (across Google, Facebook, Instagram, LinkedIn, and X — never fabricating search volumes)
   - **Section 3: SEO Improvements**
   - **Section 4: Top Five Services**
   - **Section 5: Target Audience**
4. **Separates Website Facts from AI Inferences**: Explicitly distinguishes ground-truth HTML extractions (`website_derived_facts` and `provenance="website_derived_fact"`) from strategic AI recommendations (`ai_market_inference`, `ai_inferred_offering`, `ai_generated_recommendation`).

---

## 2. Main Features & Security Architecture

- **Primary Gemini AI Engine + Automatic Fallback**:
  - Primary model: **Google Gemini** (`gemini-2.5-flash` via `google-genai` SDK) using native `response_schema=LLMAnalysisPayload` enforcement.
  - Fallback model: **OpenAI** (`gpt-4o-mini` via `openai` SDK) when `ENABLE_LLM_FALLBACK=true` and `OPENAI_API_KEY` is configured.
  - Built-in transient retry backoff (`LLM_MAX_RETRIES=2`) and strict timeout (`LLM_TIMEOUT_SECONDS=45.0`).
  - Demo mode is **disabled by default** (`ENABLE_DEMO_MODE_WITHOUT_API_KEY=false`) so production never returns synthetic data.
- **Defense-in-Depth SSRF Protection (`app/utils/validators.py`)**:
  - Blocks `localhost`, `.local`, `.internal`, `.corp`, `0.0.0.0`, `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254` (cloud metadata), `100.64.0.0/10` (CGNAT), IPv6 loopback `::1`, IPv4-mapped IPv6 addresses, and decimal/hex-encoded IP hostnames.
  - Restricts outbound ports to standard web ports (`80`, `443`, `8080`, `8443`).
  - Performs DNS resolution checks (`socket.getaddrinfo`) prior to connection to block DNS rebinding attacks.
  - Manually validates every HTTP redirect hop (`301`, `302`, `303`, `307`, `308`) up to `MAX_REDIRECTS=5`.
  - Streams responses with a hard byte ceiling (`MAX_RESPONSE_BYTES=2097152`, 2 MB).
- **Per-IP Sliding-Window Rate Limiting (`app/utils/rate_limiter.py`)**:
  - Protects `POST /link-analysis` from abuse (default `20` requests per `60` seconds per client IP), returning `HTTP 429 Too Many Requests` with a `Retry-After` header.
- **Secret Redaction & Safe Error Handling (`app/services/llm_service.py`, `app/main.py`)**:
  - Automatically scrubs `AIza...` (Gemini), `sk-...` (OpenAI), `key=...`, and `Bearer ...` tokens from all logs and error responses.
  - Returns `HTTP 503` (`missing_api_key`) when credentials are unconfigured and `HTTP 401` (`invalid_api_key`) when rejected by the upstream provider.
  - `GET /health` exposes only boolean configuration status (`gemini_key_configured: true/false`), never raw secret values.

---

## 3. Architecture & Technology Stack

```text
ai-link-analysis/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, routes (/, /health, /link-analysis), error handlers
│   ├── config.py                  # Environment settings via Pydantic BaseSettings & python-dotenv
│   ├── schemas.py                 # Strict Pydantic v2 models for requests, extracted facts & 5 sections
│   ├── services/
│   │   ├── __init__.py
│   │   ├── website_extractor.py   # Async HTTPX streaming fetch, BeautifulSoup4 cleaning & extraction
│   │   ├── llm_service.py         # Gemini & OpenAI structured JSON integration, retries & redaction
│   │   ├── analysis_service.py    # End-to-end orchestration & fact-vs-inference enrichment
│   │   └── competitor_service.py  # Brand inference, comparison signal detection & provenance tagging
│   └── utils/
│       ├── __init__.py
│       ├── rate_limiter.py        # Per-IP sliding-window rate limiter (HTTP 429)
│       └── validators.py          # URL normalization, port restrictions, DNS & IP SSRF protection
├── tests/
│   ├── __init__.py
│   └── test_link_analysis.py      # 57 unit & integration tests
├── .env.example                   # Template environment variables (no secrets)
├── .gitignore                     # Git ignore rules protecting .env and build artifacts
├── Dockerfile                     # Non-root production container image definition
├── Procfile                       # Process file for Render/Railway/Heroku
├── railway.toml                   # Railway deployment configuration
├── render.yaml                    # Render Blueprint deployment configuration
├── requirements.txt               # Pinned Python dependencies
├── run_server.py                  # Convenience server launcher script
├── verify_live_gemini.py          # End-to-end live Gemini verification script for 3 public websites
└── README.md                      # Project documentation
```

---

## 4. Installation & Local Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.12 and 3.13)
- A valid **Google Gemini API Key** (`GEMINI_API_KEY`) from [Google AI Studio](https://aistudio.google.com/)

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/UsmanSardar123/ai-link-analysis.git
cd ai-link-analysis/ai-link-analysis

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
```

---

## 5. Environment Variables & Gemini API Configuration

Edit `ai-link-analysis/.env` (never committed to Git):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `gemini` | Primary AI provider (`gemini` or `openai`) |
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key (e.g., `AIzaSy...`) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model identifier |
| `OPENAI_API_KEY` | *(optional)* | OpenAI API key for fallback (`sk-...`) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI fallback model identifier |
| `ENABLE_LLM_FALLBACK` | `true` | Automatically fall back to secondary provider if primary fails |
| `ENABLE_DEMO_MODE_WITHOUT_API_KEY` | `false` | **Must remain `false` in production** |
| `LLM_TIMEOUT_SECONDS` | `45.0` | Timeout in seconds for upstream LLM calls |
| `LLM_MAX_RETRIES` | `2` | Retries on transient 429/503 LLM errors |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `20` | Max `POST /link-analysis` requests per IP per minute |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window duration in seconds |
| `HTTP_TIMEOUT_SECONDS` | `15.0` | Timeout for fetching target websites |
| `MAX_RESPONSE_BYTES` | `2097152` | Max HTML response size in bytes (2 MB) |
| `MAX_REDIRECTS` | `5` | Max safe redirects to follow per request |

---

## 6. Running the Server & Automated Tests

### Start the FastAPI Server
```bash
cd ai-link-analysis
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON**: `http://127.0.0.1:8000/openapi.json`
- **Health Check**: `http://127.0.0.1:8000/health`

### Run the Automated Test Suite (57 Tests)
```bash
pytest ai-link-analysis/tests/test_link_analysis.py -v
```

### Run Live End-to-End Gemini Verification on 3 Public Websites
Once `GEMINI_API_KEY` is set in `ai-link-analysis/.env`:
```bash
python ai-link-analysis/verify_live_gemini.py
```
This script analyzes `https://stripe.com`, `https://www.python.org`, and `https://www.shopify.com` with `gemini-2.5-flash` and saves the full JSON responses under `ai-link-analysis/verification_evidence/`.

---

## 7. API Endpoint Documentation

### `GET /health`
Returns service readiness and non-sensitive boolean provider flags:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "configured_primary_provider": "gemini",
  "configured_gemini_model": "gemini-2.5-flash",
  "configured_openai_model": "gpt-4o-mini",
  "gemini_key_configured": true,
  "openai_key_configured": false,
  "demo_mode_enabled": false
}
```

### `POST /link-analysis`
Fetches, validates, and analyzes a public website URL.

#### Request Body
```json
{
  "url": "https://stripe.com"
}
```

#### HTTP Status Codes
| Status Code | Error Code | Condition |
| :--- | :--- | :--- |
| `200 OK` | — | Website extracted and all 5 AI analysis sections validated. |
| `400 Bad Request` | `invalid_url` / `ssrf_protection_blocked` | Malformed URL, unsupported scheme (`ftp://`, `javascript:`), or SSRF violation (`localhost`, private IPs, disallowed port). |
| `401 Unauthorized` | `invalid_api_key` | Configured `GEMINI_API_KEY` or `OPENAI_API_KEY` was rejected by the AI provider (secrets redacted). |
| `413 Payload Too Large` | `website_extraction_failed` | Target webpage exceeded `MAX_RESPONSE_BYTES` (2 MB). |
| `422 Unprocessable Entity` | `website_extraction_failed` / Validation | Missing `url` field, non-HTML content type, HTTP 4xx from target site, or redirect limit exceeded. |
| `429 Too Many Requests` | `rate_limit_exceeded` | Client IP exceeded `RATE_LIMIT_REQUESTS_PER_MINUTE` (includes `Retry-After` header). |
| `502 Bad Gateway` | `website_extraction_failed` / `llm_generation_failed` | Target website unreachable or upstream LLM provider failed. |
| `503 Service Unavailable` | `missing_api_key` | No valid `GEMINI_API_KEY` or `OPENAI_API_KEY` configured (and demo mode is `false`). |
| `504 Gateway Timeout` | `website_extraction_failed` | Target website timed out (`HTTP_TIMEOUT_SECONDS`). |

---

## 8. Verified Test Results (Local, Mocked & Live Extraction vs. Live Gemini)

### A. Automated Test Suite (`pytest`) — **57 Passed, 0 Failed**
All 57 automated tests in `tests/test_link_analysis.py` pass:
- **URL Validation & SSRF Protection (32 tests)**: Public URLs, malformed URLs, `ftp://`/`javascript:`/`file://` rejection, `localhost`, `127.0.0.1`, `10.0.0.1`, `172.16.0.10`, `192.168.1.1`, `169.254.169.254` (cloud metadata), `100.64.0.1` (CGNAT), IPv6 `[::1]`, decimal/hex encoded IPs, embedded credentials, non-web ports (`22`, `6379`), and DNS rebinding to private IPs.
- **Website Extraction & Redirect Security (4 tests)**: HTML metadata/heading/paragraph/business signal extraction, script/style/nav/footer removal, 302 redirect to `169.254.169.254` blocked, timeout (`504`) and oversized payload (`413`) handling.
- **LLM Provider Selection, Retries, Fallback & Secret Redaction (10 tests)**: Default `gemini` (`gemini-2.5-flash`) selection, demo mode disabled by default, Gemini -> OpenAI fallback, OpenAI -> Gemini fallback, transient `429 RESOURCE_EXHAUSTED` retry recovery, missing API key (`503`), invalid API key (`401`), and secret redaction of `AIza...` and `sk-...` tokens.
- **FastAPI Endpoint Integration & Rate Limiting (11 tests)**: `/health` secret safety, `/docs` Swagger UI, full 5-section `POST /link-analysis` response schema validation, `422` malformed body handling, and `429` sliding-window rate limiting.

### B. Live Multi-Website Extraction Verification (Real HTTP Requests)
Verified live extraction against three public production websites across distinct business categories:
1. **`https://stripe.com`** (FinTech): `HTTP 200 OK` | Title: `"Stripe | Financial Infrastructure to Grow Your Revenue"` | `720` words, `40` paragraphs, `40` links, `7` Schema.org types (`Organization`, `WebSite`, etc.).
2. **`https://www.python.org`** (Developer / Open Source): `HTTP 200 OK` | Title: `"Welcome to Python.org"` | `950` words, `38` paragraphs, `9` H2 headings, `40` links.
3. **`https://www.shopify.com`** (E-Commerce SaaS): `HTTP 200 OK` | Title: `"Shopify: The All-in-One Commerce Platform for Businesses - Shopify"` | `384` words, `22` paragraphs, `5` H2 headings, `6` social links.

*(Note: Live Gemini API generation for these 3 websites requires a user-supplied `GEMINI_API_KEY` in `.env` and can be executed with a single command: `python ai-link-analysis/verify_live_gemini.py`.)*

---

## 9. LLM Research & Provider Comparison

| Provider & Model | Input Pricing (per 1M tokens) | Output Pricing (per 1M tokens) | Context Window | Typical Response Speed (Est. ~2K Output) | Structured JSON Output Capabilities |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini 2.5 Flash** *(Primary)* | **$0.30** | **$2.50** | **1,000,000** | **~2.5 – 4.5s** | Native `response_mime_type="application/json"` + Pydantic `response_schema` |
| **OpenAI GPT-4o-mini** *(Fallback)* | **$0.15** | **$0.60** | **128,000** | **~3.0 – 5.5s** | Native `response_format={"type": "json_object"}` & Structured Outputs |
| **Anthropic Claude 3.5 Haiku** | **$0.25** | **$1.25** | **200,000** | **~3.0 – 5.0s** | Tool-use JSON schema / prompt-guided JSON |
| **Google Gemini 2.5 Pro** | **$1.25** | **$5.00 – $10.00** | **2,000,000** | ~6.0 – 12.0s | Native `response_schema` enforcement |
| **OpenAI GPT-4o** | **$2.50** | **$10.00** | **128,000** | ~5.0 – 9.0s | Strict Structured Outputs (`json_schema`) |
| **Anthropic Claude 3.5 Sonnet** | **$3.00** | **$15.00** | **200,000** | ~5.5 – 10.0s | Tool-use JSON schema |

- **Estimated Tokens per Analysis**: ~2,500 input tokens + ~2,000 output tokens.
- **Estimated Cost per Analysis (`gemini-2.5-flash`)**: **~$0.00575** (~173 website analyses per $1.00 USD).
- **Estimated Cost per Analysis (`gpt-4o-mini` fallback)**: **~$0.00158** (~630 website analyses per $1.00 USD).

---

## 10. Docker & Cloud Deployment Instructions (Render & Railway)

### Option A: Docker
```bash
cd ai-link-analysis
docker build -t ai-link-analysis-api .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY="your_gemini_api_key" \
  -e LLM_PROVIDER="gemini" \
  -e GEMINI_MODEL="gemini-2.5-flash" \
  -e ENABLE_DEMO_MODE_WITHOUT_API_KEY="false" \
  ai-link-analysis-api
```

### Option B: Render Blueprint Deployment (`render.yaml` — Recommended)
Both the repository root and `ai-link-analysis/` include a production-ready `render.yaml` Blueprint:
1. Log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Blueprint** and select your GitHub repository (`UsmanSardar123/ai-link-analysis` or `UsmanSardar123/Python_Api-analysis`).
3. Render automatically configures `APP_ENV=production`, `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-2.5-flash`, and `ENABLE_DEMO_MODE_WITHOUT_API_KEY=false`.
4. When prompted for secret variables (`sync: false`), enter your `GEMINI_API_KEY` (and optional `OPENAI_API_KEY`).
5. Click **Apply**. Once live, verify with:
   ```bash
   python ai-link-analysis/verify_live_gemini.py --base-url https://<your-service>.onrender.com
   ```

### Option C: Railway Deployment (`railway.toml` & `Dockerfile`)
1. Log in to [Railway](https://railway.app/) and click **New Project** -> **Deploy from GitHub repo**.
2. Set the service **Root Directory** to `ai-link-analysis`.
3. In the **Variables** tab, add:
   - `GEMINI_API_KEY` = `<your_gemini_api_key>`
   - `LLM_PROVIDER` = `gemini`
   - `GEMINI_MODEL` = `gemini-2.5-flash`
   - `ENABLE_DEMO_MODE_WITHOUT_API_KEY` = `false`
4. Generate a public domain under **Settings -> Networking**.

---

## 11. Known Limitations

1. **JavaScript-Only Single Page Applications (SPAs)**: The extractor uses `httpx` + `BeautifulSoup4` for fast, lightweight, secure HTML fetching rather than a headless browser. Websites that render 100% of their body text client-side via JavaScript without SSR/meta tags will yield limited body paragraphs (though `<title>` and `<meta>` tags are still captured).
2. **Anti-Bot / WAF Challenges**: Websites gated behind Cloudflare Turnstile or CAPTCHA challenges will return HTTP `403`/`422` and are reported cleanly as `website_extraction_failed` rather than bypassed.
3. **In-Memory Rate Limiter Scope**: The sliding-window rate limiter stores per-IP timestamps in process memory; multi-worker deployments should back the rate limiter with Redis.
