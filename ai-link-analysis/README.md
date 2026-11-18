# AI-Powered Website Link Analysis API

A production-minded, asynchronous **FastAPI** backend application that fetches any public website URL with strict **SSRF protection**, extracts clean factual content using **HTTPX** and **BeautifulSoup4**, and generates a comprehensive, schema-validated **5-part marketing, SEO, and competitive intelligence report** powered by **Google Gemini** (`gemini-2.5-flash`) or **OpenAI** (`gpt-4o-mini`).

---

## 1. Project Overview

Modern growth, SEO, and product marketing teams spend hours manually auditing websites, researching competitors, mapping customer search intent across social/search platforms, and identifying target audiences.

The **AI-Powered Website Link Analysis API** (`POST /link-analysis`) automates this workflow end-to-end:
1. **Validates & Secures**: Enforces strict URL validation, blocks private/loopback/link-local/metadata IP ranges (SSRF protection), validates every redirect hop, and enforces response timeout and byte-size limits.
2. **Extracts Ground-Truth Website Facts**: Parses HTML with BeautifulSoup4, stripping `<script>`, `<style>`, `<nav>`, `<footer>`, and duplicate boilerplate while extracting the page title, meta description, canonical URL, H1–H3 headings, clean body paragraphs, internal/external links, and business signals (emails, phone numbers, social links, JSON-LD `Schema.org` types, and CTAs).
3. **Generates 5 Structured AI Analysis Sections**: Uses Google Gemini or OpenAI structured JSON outputs validated through **Pydantic v2** to return:
   - **Section 1: Competitor Analysis**
   - **Section 2: Target Search Queries** (across Google, Facebook, Instagram, LinkedIn, and X — never fabricating search volumes)
   - **Section 3: SEO Improvements**
   - **Section 4: Top Five Services**
   - **Section 5: Target Audience**
4. **Separates Website Facts from AI Inferences**: Explicitly distinguishes ground-truth HTML extractions (`website_derived_facts` and `provenance="website_derived_fact"`) from strategic AI recommendations (`ai_market_inference`, `ai_inferred_offering`, `ai_generated_recommendation`).

---

## 2. Features

- **Five Complete Analysis Sections**: Guaranteed by strict Pydantic v2 models (`LinkAnalysisResponse`).
- **Multi-Provider AI Engine**: Supports **Google Gemini** (`google-genai` SDK) and **OpenAI** (`openai` SDK) with automatic cross-provider fallback (`ENABLE_LLM_FALLBACK=true`).
- **Explicit Fact vs. Inference Attribution**: Never conflates scraped HTML facts with AI-generated recommendations.
- **Zero Fabricated Search Volumes**: Enforces an explicit policy against inventing monthly keyword volume numbers.
- **Defense-in-Depth SSRF Protection**:
  - Blocks `localhost`, `.local`, `.internal`, `.corp`, `0.0.0.0`, `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254` (cloud metadata), `100.64.0.0/10` (CGNAT), IPv6 loopback `::1`, and decimal/hex-encoded IP hostnames.
  - Performs DNS resolution checks (`socket.getaddrinfo`) prior to connection to prevent DNS rebinding.
  - Validates every HTTP redirect hop (`301`, `302`, `303`, `307`, `308`) up to `MAX_REDIRECTS`.
  - Streams responses with a hard byte ceiling (`MAX_RESPONSE_BYTES`, default 2 MB).
- **Comprehensive Test Suite**: 46 automated unit and integration tests covering valid URLs, invalid schemes, SSRF vectors, redirect attacks, timeouts, HTML parsing, missing API keys, LLM failures, and Pydantic validation.

---

## 3. Technologies

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ (tested on 3.12 / 3.13) | Core runtime |
| **Web Framework** | FastAPI | REST API routing, dependency injection, OpenAPI `/docs` |
| **ASGI Server** | Uvicorn | High-performance async HTTP server |
| **Data Validation** | Pydantic v2 & `pydantic-settings` | Request/response schemas & environment config |
| **HTTP Client** | HTTPX (`AsyncClient`) | Non-blocking streaming website fetcher with timeout controls |
| **HTML Parser** | BeautifulSoup4 | DOM cleaning, metadata & content extraction |
| **AI SDKs** | `google-genai` & `openai` | Structured JSON generation with Gemini and OpenAI |
| **Env Management** | `python-dotenv` | `.env` configuration loader |
| **Testing** | Pytest | Automated test suite (46 test cases) |

---

## 4. Architecture & Project Structure

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
│   │   ├── llm_service.py         # Gemini & OpenAI structured JSON integration, prompts & fallback
│   │   ├── analysis_service.py    # End-to-end orchestration & fact-vs-inference enrichment
│   │   └── competitor_service.py  # Brand inference, comparison signal detection & provenance tagging
│   └── utils/
│       ├── __init__.py
│       └── validators.py          # URL normalization, port restrictions, DNS & IP SSRF protection
├── tests/
│   ├── __init__.py
│   └── test_link_analysis.py      # 46 unit & integration tests
├── .env.example                   # Template environment variables (no secrets)
├── .gitignore                     # Git ignore rules protecting .env and build artifacts
├── Dockerfile                     # Production container image definition
├── Procfile                       # Process file for Heroku/Railway/Render
├── railway.toml                   # Railway deployment configuration
├── render.yaml                    # Render Blueprint deployment configuration
├── requirements.txt               # Pinned Python dependencies
├── run_server.py                  # Convenience server launcher script
└── README.md                      # Project documentation
```

---

## 5. Installation Instructions

### Prerequisites
- Python 3.10 or higher
- Git

### Step-by-Step Setup

```bash
# 1. Clone the repository
git clone https://github.com/UsmanSardar123/ai-link-analysis.git
cd ai-link-analysis/ai-link-analysis

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 6. Environment Setup

Copy the example environment file and configure your API key(s):

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```ini
# Primary LLM Provider: "gemini" or "openai"
LLM_PROVIDER=gemini

# Google Gemini API Configuration (Recommended Primary)
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# OpenAI API Configuration (Fallback or Primary if LLM_PROVIDER=openai)
OPENAI_API_KEY=your_actual_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Automatically fall back to secondary provider if primary fails
ENABLE_LLM_FALLBACK=true

# Website Extraction Security & Networking Limits
HTTP_TIMEOUT_SECONDS=15.0
MAX_RESPONSE_BYTES=2097152
MAX_REDIRECTS=5
```

> **Security Note**: Never commit `.env` or hardcode API keys in source files. `.gitignore` is pre-configured to exclude `.env` files.

---

## 7. How to Run the Server

### Run with Uvicorn (Development)
```bash
cd ai-link-analysis
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or using the included launcher script:
```bash
python ai-link-analysis/run_server.py
```

### Interactive API Documentation
Once the server is running, open your browser at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **Health Check**: `http://127.0.0.1:8000/health`

### Run the Automated Test Suite
```bash
cd ai-link-analysis
pytest -v
```

---

## 8. API Endpoint Documentation

### `POST /link-analysis`

Analyzes a public website URL and returns ground-truth extracted HTML facts alongside all five required AI marketing and SEO analysis sections.

- **URL**: `/link-analysis`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body
```json
{
  "url": "https://example.com"
}
```

#### HTTP Status Codes
| Status Code | Error Code | Description |
| :--- | :--- | :--- |
| `200 OK` | — | Successfully extracted website content and generated all 5 analysis sections. |
| `400 Bad Request` | `invalid_url` / `ssrf_protection_blocked` | Malformed URL, unsupported scheme (`ftp://`, `javascript:`), or SSRF block (`localhost`, private IPs). |
| `413 Payload Too Large` | `website_extraction_failed` | Target webpage exceeded `MAX_RESPONSE_BYTES` (2 MB). |
| `422 Unprocessable Entity` | `website_extraction_failed` | Target URL returned non-HTML content, HTTP 4xx status, or exceeded redirect limits. |
| `502 Bad Gateway` | `website_extraction_failed` / `llm_generation_failed` | Target website unreachable or upstream LLM provider failed. |
| `503 Service Unavailable` | `missing_api_key` | Neither `GEMINI_API_KEY` nor `OPENAI_API_KEY` is configured. |
| `504 Gateway Timeout` | `website_extraction_failed` | Fetching the target website timed out (`HTTP_TIMEOUT_SECONDS`). |

---

## 9. Sample Request and Response

### Sample cURL Request
```bash
curl -X POST "http://127.0.0.1:8000/link-analysis" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

### Sample Response (`200 OK`)
```json
{
  "url": "https://example.com/",
  "metadata": {
    "llm_provider": "gemini",
    "llm_model": "gemini-2.5-flash",
    "analysis_timestamp_utc": "2026-11-18T08:13:32.151819+00:00",
    "execution_time_ms": 402.58,
    "fact_vs_inference_notice": "Factual data scraped directly from the HTML is stored in 'website_derived_facts' and explicitly tagged fields (e.g., 'website_stated_products_and_services', 'observed_current_seo_facts', and 'provenance=website_derived_fact'). Strategic recommendations, competitor comparisons, and keyword suggestions are AI-generated inferences based on the extracted content."
  },
  "website_derived_facts": {
    "source_type": "website_derived_fact",
    "requested_url": "https://example.com/",
    "final_url": "https://example.com/",
    "domain": "example.com",
    "http_status_code": 200,
    "page_title": "Example Domain",
    "meta_description": "",
    "meta_keywords": [],
    "canonical_url": "",
    "headings": {
      "h1": ["Example Domain"],
      "h2": [],
      "h3": []
    },
    "paragraphs": [
      "This domain is for use in documentation examples without needing permission. Avoid asking for permission before using it in examples."
    ],
    "links": [
      {
        "text": "More information...",
        "href": "https://iana.org/domains/example",
        "is_internal": false
      }
    ],
    "business_signals": {
      "emails": [],
      "phone_numbers": [],
      "social_links": [],
      "schema_org_types": [],
      "detected_cta_phrases": ["More information..."]
    },
    "word_count": 25
  },
  "competitor_analysis": {
    "brand_name": "Example Domain",
    "brand_overview": "Example Domain operates on example.com as an IANA-reserved reference domain for technical documentation and testing examples.",
    "brand_category": "Digital Web Services & Online Information Portal",
    "website_stated_products_and_services": [
      "Primary web presence and informational portal at example.com"
    ],
    "inferred_products_and_services": [
      "Example Domain Digital Customer Onboarding & Documentation",
      "Example Domain Enterprise API & Web Integration Services"
    ],
    "competitors": [
      {
        "name": "Cloudflare Web Services",
        "website_or_domain": "cloudflare.com",
        "category_fit": "Global web infrastructure, domain documentation, and edge web platform benchmark.",
        "strengths": [
          "Global edge network and comprehensive developer documentation",
          "Strong brand recognition across technical and enterprise audiences"
        ],
        "weaknesses": [
          "Complex multi-product catalog for simple single-purpose web properties",
          "Enterprise tiers require custom sales engagement"
        ],
        "provenance": "ai_market_inference"
      },
      {
        "name": "Vercel Digital Platform",
        "website_or_domain": "vercel.com",
        "category_fit": "Modern web publishing, documentation hosting, and digital experience competitor.",
        "strengths": [
          "Fast developer workflow and instant preview deployments",
          "High SEO and Core Web Vitals optimization out of the box"
        ],
        "weaknesses": [
          "Usage-based bandwidth pricing can scale steeply at high traffic",
          "Primarily tailored to frontend engineering teams"
        ],
        "provenance": "ai_market_inference"
      },
      {
        "name": "Netlify Web Platform",
        "website_or_domain": "netlify.com",
        "category_fit": "Comparable web hosting, standard web portal, and composable digital platform.",
        "strengths": [
          "Simple onboarding for static and hybrid web properties",
          "Built-in forms, identity, and edge routing features"
        ],
        "weaknesses": [
          "Less specialized for heavy backend compute workloads",
          "Competitive pressure from hyperscaler cloud providers"
        ],
        "provenance": "ai_market_inference"
      }
    ],
    "brand_advantages": [
      "Clean, lightweight HTML structure on example.com with fast initial load profile",
      "Uncluttered user experience with direct access to core content"
    ],
    "market_opportunities": [
      "Expand on-page structured content, FAQs, and schema.org metadata on example.com",
      "Develop dedicated solution landing pages and technical blog resources to capture organic search intent"
    ]
  },
  "target_search_queries": {
    "data_provenance": "ai_generated_recommendation",
    "volume_integrity_policy": "Search volumes are intentionally omitted and never fabricated. Qualitative intent and audience alignment are provided instead.",
    "queries": [
      {
        "query_topic": "Example Domain official website and overview",
        "search_intent": "Navigational",
        "target_audience": "Prospective users and researchers looking for Example Domain (example.com)",
        "platform_queries": {
          "Google": "Example Domain example.com official site overview",
          "Facebook": "Example Domain official page and community updates",
          "Instagram": "#ExampleDomain #WebServices #DigitalPlatform",
          "LinkedIn": "Example Domain company profile and enterprise services",
          "X": "Example Domain (example.com) announcements and user feedback"
        },
        "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)"
      }
    ]
  },
  "seo_improvements": {
    "observed_current_seo_facts": {
      "current_page_title": "Example Domain",
      "current_title_length": "14",
      "current_meta_description": "(Missing meta description)",
      "current_meta_description_length": "0",
      "h1_count": "1",
      "h2_count": "0",
      "canonical_url": "(Not specified)"
    },
    "primary_keywords": [
      "Example Domain",
      "example.com platform",
      "Example Domain digital services",
      "web documentation and domain standards"
    ],
    "secondary_keywords": [
      "Example Domain features",
      "Example Domain documentation",
      "reliable web portal architecture",
      "IANA and standard web examples"
    ],
    "long_tail_keywords": [
      "how to use Example Domain (example.com) for documentation and testing",
      "complete overview of Example Domain capabilities and services",
      "Example Domain best practices for technical teams"
    ],
    "recommended_seo_title": "Example Domain | Official Platform, Documentation & Services (example.com)",
    "recommended_meta_description": "Explore Example Domain at example.com. Access official documentation, core digital services, technical specifications, and getting-started resources.",
    "recommended_landing_pages": [
      {
        "title": "Example Domain Solutions & Capabilities Overview",
        "suggested_url_slug": "/solutions",
        "purpose_and_target_keyword": "Target 'Example Domain digital services' and convert visitors seeking a full feature breakdown."
      },
      {
        "title": "Example Domain Developer Documentation & Quickstart",
        "suggested_url_slug": "/docs/quickstart",
        "purpose_and_target_keyword": "Target 'Example Domain documentation' with actionable onboarding steps."
      }
    ],
    "recommended_faqs": [
      {
        "question": "What is Example Domain (example.com) and who is it designed for?",
        "recommended_answer_summary": "Example Domain provides structured web resources and services designed for technical teams, educators, and organizations."
      },
      {
        "question": "How can my organization get started with Example Domain?",
        "recommended_answer_summary": "Visit the primary portal at https://example.com/ and follow the linked documentation resources."
      },
      {
        "question": "Does Example Domain follow standard web security and accessibility practices?",
        "recommended_answer_summary": "Yes, example.com serves lightweight, standards-compliant HTML over HTTPS."
      }
    ],
    "recommended_blog_topics": [
      {
        "title": "Getting the Most Out of Example Domain: A Complete 2026 Guide",
        "target_keywords": ["Example Domain guide", "example.com tutorial"],
        "search_intent_and_angle": "Comprehensive walkthrough for first-time visitors and technical evaluators."
      },
      {
        "title": "Modern Web Architecture: Why Clean, Standards-Compliant HTML Matters for SEO",
        "target_keywords": ["clean html seo", "web standards performance"],
        "search_intent_and_angle": "Educational thought-leadership article attracting software engineers and technical SEOs."
      },
      {
        "title": "Top 5 Use Cases for Example Domain in Technical Documentation and Workflows",
        "target_keywords": ["Example Domain use cases", "technical documentation examples"],
        "search_intent_and_angle": "Practical use-case showcase highlighting real-world applications."
      }
    ]
  },
  "top_five_services": {
    "services": [
      {
        "service_name": "Primary web presence and informational portal at example.com",
        "description": "Core web resource and primary informational offering explicitly presented on example.com.",
        "target_industry": "Technology, Education, and Digital Publishing",
        "target_customer": "Web Developers, Technical Writers, and Digital Visitors",
        "main_benefit": "Provides immediate, standards-compliant access to the site's primary content.",
        "provenance": "website_derived_fact"
      }
    ]
  },
  "target_audience": {
    "website_explicit_audience_clues": [
      "This domain is for use in documentation examples without needing permission."
    ],
    "primary_audiences": [
      "Software Engineers, Web Developers, and Technical Documentation Authors",
      "System Administrators, QA Engineers, and API Integration Specialists"
    ],
    "secondary_audiences": [
      "Computer Science Educators, Students, and Technical Trainers",
      "Digital Product Managers and SEO/Content Strategists"
    ],
    "industry_segments": [
      "Software Development & SaaS",
      "Internet Infrastructure & Telecommunications",
      "Technical Education & E-Learning"
    ],
    "business_types": [
      "B2B Technology Organizations",
      "Developer Communities & Educational Institutions",
      "Individual Practitioners & Open-Source Contributors"
    ],
    "customer_needs_and_challenges": [
      "Need for reliable, standards-compliant web endpoints and clear documentation",
      "Challenge of expanding minimal web pages into rich, search-optimized conversion funnels",
      "Requirement for clear navigation, structured metadata, and fast page load performance"
    ],
    "geographical_focus": "Global reach (public internet accessibility via example.com with English-language primary content).",
    "recommended_marketing_segments": [
      "Developer Relations (DevRel) & Technical Content Communities",
      "Technical SEO & Web Performance Engineering Teams",
      "Cloud & Web Infrastructure Decision-Makers"
    ]
  }
}
```
*(Note: In the live API response, `target_search_queries.queries` and `top_five_services.services` always contain all 5 items.)*

---

## 10. LLM Research & Provider Comparison

We researched and evaluated six leading commercial models across **Google Gemini**, **OpenAI**, and **Anthropic Claude** for structured website link analysis.

### Model Comparison Table (Published API Pricing & Capabilities)

| Provider & Model | Input Pricing (per 1M tokens) | Output Pricing (per 1M tokens) | Context Window | Typical Response Speed (Estimated for ~2K Output) | Structured JSON Output Capabilities | Analytical Accuracy & Marketing/SEO Depth |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini 2.5 Flash** *(Recommended Primary)* | **$0.30** | **$2.50** | **1,000,000** tokens | **Fast (~2.5 – 4.5s)** | Native `response_mime_type="application/json"` + direct Pydantic `response_schema` enforcement | High accuracy for extracting entity relationships, SEO keywords, and structured B2B/B2C taxonomies |
| **OpenAI GPT-4o-mini** *(Recommended Fallback)* | **$0.15** | **$0.60** | **128,000** tokens | **Fast (~3.0 – 5.5s)** | Native `response_format={"type": "json_object"}` & Structured Outputs JSON Schema | Very strong schema adherence and concise copywriting at ultra-low token cost |
| **Anthropic Claude 3.5 Haiku** | **$0.25** (up to $0.80 depending on tier) | **$1.25** (up to $4.00 depending on tier) | **200,000** tokens | **Fast (~3.0 – 5.0s)** | Tool-use JSON schema / prompt-guided JSON mode | Strong linguistic nuance and marketing tone; slightly less native schema strictness without tool wrappers |
| **Google Gemini 2.5 Pro** | **$1.25** | **$5.00 – $10.00** | **2,000,000** tokens | Moderate (~6.0 – 12.0s) | Native `response_schema` enforcement | Frontier-grade deep reasoning; overkill for single-page HTML marketing extraction |
| **OpenAI GPT-4o** | **$2.50** | **$10.00** | **128,000** tokens | Moderate (~5.0 – 9.0s) | Strict Structured Outputs (`json_schema`) | Excellent competitive intelligence & nuanced SEO copywriting, but ~4x–15x more expensive than Flash/mini |
| **Anthropic Claude 3.5 Sonnet** | **$3.00** | **$15.00** | **200,000** tokens | Moderate (~5.5 – 10.0s) | Tool-use JSON schema | Top-tier strategic writing quality, but highest cost per request ($0.036+ per analysis) |

---

### Estimated Token Usage & Cost Per Single Link Analysis

> **Transparency Note**: The token counts, per-request costs, and latency ranges below are **engineering estimates** based on our actual prompt template size, cleaned HTML payload limits (capped at 40 paragraphs, 25 headings, 40 links), and a full 5-section JSON response (~1,800–2,200 words). No benchmark scores have been fabricated.

- **Estimated Input Tokens per Analysis**: **~2,500 tokens**
  - System Prompt & Instructions: ~450 tokens
  - JSON Schema Definition: ~850 tokens
  - Cleaned Website Extracted Facts JSON: ~1,200 tokens (typical landing page)
- **Estimated Output Tokens per Analysis**: **~2,000 tokens**
  - Complete 5-section JSON response (`competitor_analysis`, `target_search_queries`, `seo_improvements`, `top_five_services`, `target_audience`)

#### Per-Analysis Cost Breakdown (Estimated for 2,500 Input + 2,000 Output Tokens)

| Model | Input Cost (2.5K tokens) | Output Cost (2.0K tokens) | **Total Estimated Cost / Analysis** | **Analyses per $1.00 USD** | **Expected End-to-End Response Time (Est.)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini 2.5 Flash** *(Primary)* | $0.00075 | $0.00500 | **~$0.00575** (~0.58 cents) | **~173 analyses** | **3.5 – 6.0 seconds** (including HTTP scrape) |
| **OpenAI GPT-4o-mini** *(Fallback)* | $0.000375 | $0.00120 | **~$0.00158** (~0.16 cents) | **~630 analyses** | **4.0 – 6.5 seconds** (including HTTP scrape) |
| **Claude 3.5 Haiku** | $0.000625 | $0.00250 | **~$0.00313** (~0.31 cents) | **~319 analyses** | **4.0 – 6.5 seconds** |
| **Google Gemini 2.5 Pro** | $0.003125 | $0.01000 | **~$0.01313** (~1.31 cents) | **~76 analyses** | **7.0 – 13.0 seconds** |
| **OpenAI GPT-4o** | $0.00625 | $0.02000 | **~$0.02625** (~2.63 cents) | **~38 analyses** | **6.0 – 10.0 seconds** |
| **Claude 3.5 Sonnet** | $0.00750 | $0.03000 | **~$0.03750** (~3.75 cents) | **~26 analyses** | **6.5 – 11.0 seconds** |

---

### Recommendation & Justification

1. **Recommended Primary Model: `gemini-2.5-flash` (Google Gemini)**
   - **Why**: `gemini-2.5-flash` offers the best balance of **low latency**, **native Pydantic schema enforcement** (`response_schema=LLMAnalysisPayload`), **1M token context window**, and **strong marketing/SEO reasoning** at roughly **$0.0058 per analysis** (plus a generous free tier on Google AI Studio for development and testing).
2. **Recommended Fallback Model: `gpt-4o-mini` (OpenAI)**
   - **Why**: Configured automatically via `ENABLE_LLM_FALLBACK=true`. If Gemini experiences transient rate-limiting or downtime, the service seamlessly falls back to `gpt-4o-mini`, which costs only **~$0.0016 per analysis** and supports native JSON object mode.

---

## 11. Cost Optimization Strategies

1. **Aggressive HTML Pre-Cleaning before Prompting**: Raw HTML pages often exceed 50,000–150,000 tokens due to inline SVGs, CSS bundles, tracking scripts, and DOM boilerplate. `WebsiteExtractorService` strips all scripts/styles/nav/footers and deduplicates paragraphs and headings, reducing input tokens by **90%–97%** (down to ~1,200 tokens).
2. **Temperature & Output Bounding**: Using `temperature=0.2` reduces verbose hallucinations and keeps JSON output focused and deterministic.
3. **Prompt Caching**: Both Gemini and OpenAI automatically discount repeated static prefixes (`SYSTEM_PROMPT` + JSON schema definition) by 50%–75% at scale.
4. **Domain/URL Response Caching (Production Extension)**: Caching completed `LinkAnalysisResponse` payloads in Redis keyed by `(normalized_url, date)` with a 24-hour TTL eliminates redundant LLM calls for popular domains.

---

## 12. Deployment Instructions

This repository includes ready-to-use deployment configurations for **Docker**, **Render**, and **Railway**.

### Option A: Deploy with Docker
```bash
cd ai-link-analysis
docker build -t ai-link-analysis-api .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY="your_gemini_api_key" \
  -e LLM_PROVIDER="gemini" \
  ai-link-analysis-api
```

### Option B: Deploy to Render (`render.yaml`)
1. Push this repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com/), click **New +** -> **Blueprint** and connect your GitHub repository.
3. Render will automatically detect `ai-link-analysis/render.yaml`.
4. Enter your `GEMINI_API_KEY` (and optional `OPENAI_API_KEY`) in the Render secret environment variable prompt.
5. Render will build the service and verify readiness via `GET /health`.

### Option C: Deploy to Railway (`railway.toml` / `Dockerfile`)
1. Push this repository to GitHub.
2. In [Railway](https://railway.app/), create a **New Project** -> **Deploy from GitHub repo**.
3. Set the root directory to `ai-link-analysis` and configure `GEMINI_API_KEY` in the **Variables** tab.
4. Railway will build the `Dockerfile` and expose a public HTTPS domain monitored by `/health`.
