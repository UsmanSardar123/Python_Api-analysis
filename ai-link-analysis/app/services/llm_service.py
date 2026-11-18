"""LLM integration service supporting Google Gemini and OpenAI with structured JSON validation."""

import json
import logging
import os
import re
from typing import Any

from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas import LLMAnalysisPayload, WebsiteExtractedData

logger = logging.getLogger(__name__)

# Patterns used to sanitize error messages so API keys or Bearer tokens are never leaked
_SECRET_REDACTION_PATTERNS = (
    re.compile(r"(AIza[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(sk-[0-9A-Za-z\-_]{15,})"),
    re.compile(r"(?i)(key=)([^&\s\"']+)"),
    re.compile(r"(?i)(bearer\s+)([0-9A-Za-z\-_\.]+)"),
)


def redact_secrets(message: str) -> str:
    """Redact any potential API keys, query keys, or bearer tokens from error strings or logs."""
    if not message:
        return ""
    sanitized = str(message)
    sanitized = _SECRET_REDACTION_PATTERNS[0].sub("[REDACTED_GEMINI_KEY]", sanitized)
    sanitized = _SECRET_REDACTION_PATTERNS[1].sub("[REDACTED_OPENAI_KEY]", sanitized)
    sanitized = _SECRET_REDACTION_PATTERNS[2].sub(r"\1[REDACTED]", sanitized)
    sanitized = _SECRET_REDACTION_PATTERNS[3].sub(r"\1[REDACTED]", sanitized)
    return sanitized


class LLMConfigurationError(Exception):
    """Raised when required LLM API keys are missing or invalidly configured."""


class LLMAuthenticationError(Exception):
    """Raised when the configured LLM API key is rejected by the provider (401/403/API_KEY_INVALID)."""


class LLMServiceError(Exception):
    """Raised when the LLM provider fails or returns an invalid/incomplete structured response."""


SYSTEM_PROMPT = """You are an elite B2B/B2C Digital Marketing Strategist, Technical SEO Architect, and Competitive Intelligence Analyst.
Your task is to analyze factual website content extracted from a target URL and produce a rigorous, complete, structured JSON analysis containing five required sections:
1. competitor_analysis
2. target_search_queries
3. seo_improvements
4. top_five_services
5. target_audience

CRITICAL RULES YOU MUST FOLLOW:
1. FACT VS. INFERENCE SEPARATION:
   - Clearly distinguish facts explicitly present on the website from AI-generated strategic inferences.
   - Populate `website_stated_products_and_services` ONLY with offerings directly supported by the provided website text.
   - Populate `inferred_products_and_services` with logical adjacent offerings inferred from the domain/industry context.
   - For each item in `top_five_services.services`, set `provenance` to `"website_derived_fact"` if explicitly mentioned on the page, or `"ai_inferred_offering"` if inferred to complete the top 5 services.
   - For each competitor in `competitor_analysis.competitors`, set `provenance` to `"website_mentioned"` ONLY if the competitor appears in the extracted website text, otherwise `"ai_market_inference"`.

2. NEVER FABRICATE SEARCH VOLUMES:
   - In `target_search_queries`, NEVER invent or fabricate monthly search volume numbers (e.g., do not output fake numbers like "12,400/mo").
   - Keep `search_volume_note` as a transparent note stating that exact search volume metrics require live keyword planner data and are not fabricated.

3. COMPLETENESS REQUIREMENTS:
   - `competitor_analysis.competitors`: Must include AT LEAST 3 relevant, real-world competitors (or category alternatives if the site is a generic/placeholder domain like example.com) with concrete `strengths` and `weaknesses`.
   - `target_search_queries.queries`: Must contain EXACTLY 5 relevant customer search query items, each including platform-specific search queries for `Google`, `Facebook`, `Instagram`, `LinkedIn`, and `X`, plus `search_intent` ("Informational", "Navigational", "Commercial Investigation", or "Transactional") and `target_audience`.
   - `seo_improvements`: Must include `primary_keywords` (3+), `secondary_keywords` (3+), `long_tail_keywords` (3+), `recommended_seo_title` (10-120 chars), `recommended_meta_description` (30-300 chars), `recommended_landing_pages` (2+), `recommended_faqs` (3+), and `recommended_blog_topics` (3+).
   - `top_five_services.services`: Must contain EXACTLY 5 services with `service_name`, `description`, `target_industry`, `target_customer`, `main_benefit`, and `provenance`.
   - `target_audience`: Must include `website_explicit_audience_clues`, `primary_audiences` (2+), `secondary_audiences` (2+), `industry_segments` (2+), `business_types` (1+), `customer_needs_and_challenges` (3+), `geographical_focus`, and `recommended_marketing_segments` (3+).

4. OUTPUT FORMAT:
   - Return ONLY valid JSON matching the exact schema requested. Do not wrap in markdown code fences or add commentary outside the JSON object.
"""


def build_user_prompt(
    extracted: WebsiteExtractedData,
    competitor_hints: dict[str, Any],
) -> str:
    """Build a structured, reusable user prompt containing the extracted website facts and JSON schema."""
    factual_payload = {
        "requested_url": extracted.requested_url,
        "final_url": extracted.final_url,
        "domain": extracted.domain,
        "page_title": extracted.page_title,
        "meta_description": extracted.meta_description,
        "meta_keywords": extracted.meta_keywords,
        "canonical_url": extracted.canonical_url,
        "headings": extracted.headings,
        "paragraphs": extracted.paragraphs[:25],
        "sample_links": [
            {"text": link.text, "href": link.href, "is_internal": link.is_internal}
            for link in extracted.links[:25]
        ],
        "business_signals": extracted.business_signals.model_dump(),
        "word_count": extracted.word_count,
        "competitor_preprocessing_hints": competitor_hints,
    }

    schema_json = json.dumps(LLMAnalysisPayload.model_json_schema(), indent=2)

    return (
        "Analyze the following extracted website data and return a JSON object conforming strictly "
        "to the required JSON schema.\n\n"
        "=== EXTRACTED WEBSITE FACTS (GROUND TRUTH) ===\n"
        f"{json.dumps(factual_payload, indent=2, ensure_ascii=False)}\n\n"
        "=== REQUIRED JSON SCHEMA ===\n"
        f"{schema_json}\n"
    )


class LLMService:
    """Service managing LLM API invocations, structured output parsing, and provider fallback."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _resolve_provider_order(self) -> list[tuple[str, str, str]]:
        """Determine ordered list of (provider, model, api_key) based on settings and available keys."""
        gemini_key = (
            self.settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        ).strip()
        openai_key = (
            self.settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        ).strip()

        valid_gemini = self.settings.has_valid_gemini_key()
        valid_openai = self.settings.has_valid_openai_key()

        candidates: list[tuple[str, str, str]] = []
        primary = self.settings.llm_provider.lower()

        if primary == "gemini":
            if valid_gemini:
                candidates.append(("gemini", self.settings.gemini_model, gemini_key))
            if self.settings.enable_llm_fallback and valid_openai:
                candidates.append(("openai", self.settings.openai_model, openai_key))
        else:
            if valid_openai:
                candidates.append(("openai", self.settings.openai_model, openai_key))
            if self.settings.enable_llm_fallback and valid_gemini:
                candidates.append(("gemini", self.settings.gemini_model, gemini_key))

        if not candidates:
            if self.settings.enable_demo_mode_without_api_key:
                return [("demo_heuristic", "deterministic-website-analyzer-v1", "demo")]
            raise LLMConfigurationError(
                "Missing LLM API credentials. Please set a valid GEMINI_API_KEY or OPENAI_API_KEY in your environment or .env file."
            )

        return candidates

    async def generate_structured_analysis(
        self,
        extracted: WebsiteExtractedData,
        competitor_hints: dict[str, Any],
    ) -> tuple[LLMAnalysisPayload, str, str]:
        """Generate and validate the 5-section website analysis via configured LLM provider(s).

        Returns:
            Tuple of (validated LLMAnalysisPayload, provider_name, model_name).

        Raises:
            LLMConfigurationError: If no API keys are configured.
            LLMServiceError: If all configured LLM providers fail or return invalid JSON.
        """
        candidates = self._resolve_provider_order()
        user_prompt = build_user_prompt(extracted, competitor_hints)
        errors: list[str] = []
        auth_errors: list[str] = []

        for provider, model, api_key in candidates:
            try:
                if provider == "demo_heuristic":
                    payload = self._build_deterministic_demo_analysis(extracted, competitor_hints)
                    return payload, provider, model
                if provider == "gemini":
                    raw_json = await self._call_gemini(
                        api_key=api_key,
                        model=model,
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                    )
                elif provider == "openai":
                    raw_json = await self._call_openai(
                        api_key=api_key,
                        model=model,
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                    )
                else:
                    raise LLMServiceError(f"Unsupported LLM provider: {provider}")

                payload = self.parse_and_validate_llm_json(raw_json)
                return payload, provider, model

            except LLMConfigurationError:
                raise
            except LLMAuthenticationError as exc:
                safe_msg = redact_secrets(str(exc))
                logger.warning("LLM provider '%s' (%s) authentication failed: %s", provider, model, safe_msg)
                auth_errors.append(f"{provider}/{model}: {safe_msg}")
                errors.append(f"{provider}/{model}: {safe_msg}")
            except Exception as exc:
                safe_msg = redact_secrets(str(exc))
                logger.warning("LLM provider '%s' (%s) failed: %s", provider, model, safe_msg)
                errors.append(f"{provider}/{model}: {safe_msg}")

        if auth_errors and len(auth_errors) == len(candidates):
            raise LLMAuthenticationError(
                "Invalid or unauthorized LLM API key(s). Details: " + " | ".join(auth_errors)
            )

        raise LLMServiceError(
            "Failed to generate valid structured analysis from LLM provider(s). Details: "
            + " | ".join(errors)
        )

    @staticmethod
    def parse_and_validate_llm_json(raw_text: str) -> LLMAnalysisPayload:
        """Clean any markdown wrappers, parse JSON, and validate against LLMAnalysisPayload."""
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            raise LLMServiceError("LLM returned an empty response.")

        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            # Strip markdown code fences if present
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed_dict = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMServiceError(f"LLM output was not valid JSON: {exc}") from exc

        try:
            return LLMAnalysisPayload.model_validate(parsed_dict)
        except ValidationError as exc:
            raise LLMServiceError(
                f"LLM JSON output failed Pydantic schema validation: {exc}"
            ) from exc

    async def _call_gemini(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Invoke Google Gemini API using google-genai SDK with structured JSON output."""
        try:
            import asyncio
            import httpx
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LLMServiceError(
                f"google-genai package is not installed: {exc}"
            ) from exc

        max_attempts = max(1, self.settings.llm_max_retries + 1)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                http_options = types.HttpOptions(
                    async_client_args={
                        "trust_env": False,
                        "timeout": self.settings.llm_timeout_seconds,
                    },
                    client_args={
                        "trust_env": False,
                        "timeout": self.settings.llm_timeout_seconds,
                    },
                )
                client = genai.Client(api_key=api_key, http_options=http_options)
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            response_schema=LLMAnalysisPayload,
                            temperature=0.2,
                        ),
                    ),
                    timeout=self.settings.llm_timeout_seconds,
                )
                text = getattr(response, "text", None)
                if not text:
                    raise LLMServiceError("Gemini returned an empty response body.")
                return text
            except (LLMServiceError, LLMAuthenticationError):
                raise
            except Exception as exc:
                last_error = exc
                safe_err = redact_secrets(str(exc))
                lower_err = safe_err.lower()
                if any(
                    token in lower_err
                    for token in (
                        "api_key_invalid",
                        "api key not valid",
                        "invalid api key",
                        "permission_denied",
                        "unauthenticated",
                        "401",
                        "403",
                    )
                ):
                    raise LLMAuthenticationError(
                        f"Google Gemini API authentication failed (invalid or unauthorized API key): {safe_err}"
                    ) from exc

                is_transient = any(
                    token in lower_err
                    for token in ("429", "resource_exhausted", "rate limit", "503", "unavailable", "timeout", "timed out")
                )
                if is_transient and attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue

                raise LLMServiceError(f"Google Gemini API call failed: {safe_err}") from exc

        raise LLMServiceError(
            f"Google Gemini API call failed after {max_attempts} attempts: {redact_secrets(str(last_error))}"
        )

    async def _call_openai(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Invoke OpenAI Chat Completions API with JSON mode."""
        try:
            import httpx
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise LLMServiceError(f"openai package is not installed: {exc}") from exc

        try:
            async with httpx.AsyncClient(trust_env=False, timeout=60.0) as http_client:
                client = AsyncOpenAI(api_key=api_key, http_client=http_client)
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                if not response.choices or not response.choices[0].message.content:
                    raise LLMServiceError("OpenAI returned an empty completion choice.")
                return response.choices[0].message.content
        except (LLMServiceError, LLMAuthenticationError):
            raise
        except Exception as exc:
            safe_err = redact_secrets(str(exc))
            lower_err = safe_err.lower()
            if any(
                token in lower_err
                for token in (
                    "invalid_api_key",
                    "incorrect api key",
                    "authenticationerror",
                    "401",
                    "403",
                )
            ):
                raise LLMAuthenticationError(
                    f"OpenAI API authentication failed (invalid or unauthorized API key): {safe_err}"
                ) from exc
            raise LLMServiceError(f"OpenAI API call failed: {safe_err}") from exc

    def _build_deterministic_demo_analysis(
        self,
        extracted: WebsiteExtractedData,
        competitor_hints: dict[str, Any],
    ) -> LLMAnalysisPayload:
        """Build a schema-validated 5-section analysis from extracted website facts when running in local demo mode."""
        brand_name = str(
            competitor_hints.get("inferred_brand_name")
            or extracted.page_title
            or extracted.domain
            or "Analyzed Website"
        )
        domain = extracted.domain or "example.com"
        h1_list = extracted.headings.get("h1", [])
        h2_list = extracted.headings.get("h2", [])
        first_paragraph = (
            extracted.paragraphs[0]
            if extracted.paragraphs
            else f"{brand_name} ({domain}) provides digital information and web services."
        )

        stated_offerings = (h1_list + h2_list)[:5] or [
            f"Primary web presence and informational portal at {domain}"
        ]

        demo_dict = {
            "competitor_analysis": {
                "brand_name": brand_name,
                "brand_overview": (
                    f"{brand_name} operates on {domain}. Based on extracted website facts, "
                    f"its core message is: {first_paragraph[:240]}"
                ),
                "brand_category": "Digital Web Services & Online Information Portal",
                "website_stated_products_and_services": stated_offerings,
                "inferred_products_and_services": [
                    f"{brand_name} Digital Customer Onboarding & Documentation",
                    f"{brand_name} Enterprise API & Web Integration Services",
                ],
                "competitors": [
                    {
                        "name": "Cloudflare Web Services",
                        "website_or_domain": "cloudflare.com",
                        "category_fit": "Global web infrastructure, domain documentation, and edge web platform benchmark.",
                        "strengths": [
                            "Global edge network and comprehensive developer documentation",
                            "Strong brand recognition across technical and enterprise audiences",
                        ],
                        "weaknesses": [
                            "Complex multi-product catalog for simple single-purpose web properties",
                            "Enterprise tiers require custom sales engagement",
                        ],
                        "provenance": "ai_market_inference",
                    },
                    {
                        "name": "Vercel Digital Platform",
                        "website_or_domain": "vercel.com",
                        "category_fit": "Modern web publishing, documentation hosting, and digital experience competitor.",
                        "strengths": [
                            "Fast developer workflow and instant preview deployments",
                            "High SEO and Core Web Vitals optimization out of the box",
                        ],
                        "weaknesses": [
                            "Usage-based bandwidth pricing can scale steeply at high traffic",
                            "Primarily tailored to frontend engineering teams",
                        ],
                        "provenance": "ai_market_inference",
                    },
                    {
                        "name": "Netlify Web Platform",
                        "website_or_domain": "netlify.com",
                        "category_fit": "Comparable web hosting, standard web portal, and composable digital platform.",
                        "strengths": [
                            "Simple onboarding for static and hybrid web properties",
                            "Built-in forms, identity, and edge routing features",
                        ],
                        "weaknesses": [
                            "Less specialized for heavy backend compute workloads",
                            "Competitive pressure from hyperscaler cloud providers",
                        ],
                        "provenance": "ai_market_inference",
                    },
                ],
                "brand_advantages": [
                    f"Clean, lightweight HTML structure on {domain} with fast initial load profile",
                    "Uncluttered user experience with direct access to core content",
                ],
                "market_opportunities": [
                    f"Expand on-page structured content, FAQs, and schema.org metadata on {domain}",
                    "Develop dedicated solution landing pages and technical blog resources to capture organic search intent",
                ],
            },
            "target_search_queries": {
                "data_provenance": "ai_generated_recommendation",
                "volume_integrity_policy": (
                    "Search volumes are intentionally omitted and never fabricated. "
                    "Qualitative intent and audience alignment are provided instead."
                ),
                "queries": [
                    {
                        "query_topic": f"{brand_name} official website and overview",
                        "search_intent": "Navigational",
                        "target_audience": f"Prospective users and researchers looking for {brand_name} ({domain})",
                        "platform_queries": {
                            "Google": f"{brand_name} {domain} official site overview",
                            "Facebook": f"{brand_name} official page and community updates",
                            "Instagram": f"#{brand_name.replace(' ', '')} #WebServices #DigitalPlatform",
                            "LinkedIn": f"{brand_name} company profile and enterprise services",
                            "X": f"{brand_name} ({domain}) announcements and user feedback",
                        },
                        "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                    },
                    {
                        "query_topic": f"How {brand_name} works and core capabilities",
                        "search_intent": "Informational",
                        "target_audience": "Technical evaluators, developers, and product managers",
                        "platform_queries": {
                            "Google": f"how does {brand_name} work features and documentation",
                            "Facebook": f"{brand_name} tutorials and user group discussions",
                            "Instagram": f"#{brand_name.replace(' ', '')}Guide #TechExplained",
                            "LinkedIn": f"implementing {brand_name} for modern digital workflows",
                            "X": f"anyone using {brand_name} ({domain}) in production? thoughts?",
                        },
                        "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                    },
                    {
                        "query_topic": f"{brand_name} alternatives and competitor comparison",
                        "search_intent": "Commercial Investigation",
                        "target_audience": "Decision-makers comparing solutions in the category",
                        "platform_queries": {
                            "Google": f"best {brand_name} alternatives and comparison",
                            "Facebook": "Digital platform comparisons and software recommendations",
                            "Instagram": "#SoftwareComparison #TechStack #DigitalTools",
                            "LinkedIn": f"evaluating {brand_name} vs industry alternatives for B2B teams",
                            "X": f"what is the best alternative to {brand_name} right now?",
                        },
                        "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                    },
                    {
                        "query_topic": f"{brand_name} integration and getting started guide",
                        "search_intent": "Transactional",
                        "target_audience": "New users and implementation engineers ready to onboard",
                        "platform_queries": {
                            "Google": f"get started with {brand_name} {domain} setup guide",
                            "Facebook": f"{brand_name} onboarding tips and setup community",
                            "Instagram": "#CodingLife #WebDevSetup #TechOnboarding",
                            "LinkedIn": f"best practices for deploying {brand_name} across organizations",
                            "X": f"quickest way to set up and configure {brand_name}",
                        },
                        "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                    },
                    {
                        "query_topic": f"{brand_name} security, reliability, and compliance standards",
                        "search_intent": "Commercial Investigation",
                        "target_audience": "IT administrators, security architects, and procurement leads",
                        "platform_queries": {
                            "Google": f"{brand_name} {domain} security compliance and reliability",
                            "Facebook": "Cybersecurity and reliable web infrastructure professionals",
                            "Instagram": "#InfoSec #CloudSecurity #WebReliability",
                            "LinkedIn": f"{brand_name} enterprise security architecture and governance",
                            "X": f"security and uptime review for {brand_name} ({domain})",
                        },
                        "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                    },
                ],
            },
            "seo_improvements": {
                "observed_current_seo_facts": {},
                "primary_keywords": [
                    f"{brand_name}",
                    f"{domain} platform",
                    f"{brand_name} digital services",
                    "web documentation and domain standards",
                ],
                "secondary_keywords": [
                    f"{brand_name} features",
                    f"{brand_name} documentation",
                    "reliable web portal architecture",
                    "IANA and standard web examples",
                ],
                "long_tail_keywords": [
                    f"how to use {brand_name} ({domain}) for documentation and testing",
                    f"complete overview of {brand_name} capabilities and services",
                    f"{brand_name} best practices for technical teams",
                ],
                "recommended_seo_title": f"{brand_name} | Official Platform, Documentation & Services ({domain})"[:115],
                "recommended_meta_description": (
                    f"Explore {brand_name} at {domain}. Access official documentation, core digital services, "
                    "technical specifications, and getting-started resources."
                )[:280],
                "recommended_landing_pages": [
                    {
                        "title": f"{brand_name} Solutions & Capabilities Overview",
                        "suggested_url_slug": "/solutions",
                        "purpose_and_target_keyword": f"Target '{brand_name} digital services' and convert visitors seeking a full feature breakdown.",
                    },
                    {
                        "title": f"{brand_name} Developer Documentation & Quickstart",
                        "suggested_url_slug": "/docs/quickstart",
                        "purpose_and_target_keyword": f"Target '{brand_name} documentation' with actionable onboarding steps.",
                    },
                ],
                "recommended_faqs": [
                    {
                        "question": f"What is {brand_name} ({domain}) and who is it designed for?",
                        "recommended_answer_summary": f"{brand_name} provides structured web resources and services designed for technical teams, educators, and organizations.",
                    },
                    {
                        "question": f"How can my organization get started with {brand_name}?",
                        "recommended_answer_summary": f"Visit the primary portal at {extracted.final_url} and follow the linked documentation resources.",
                    },
                    {
                        "question": f"Does {brand_name} follow standard web security and accessibility practices?",
                        "recommended_answer_summary": f"Yes, {domain} serves lightweight, standards-compliant HTML over HTTPS.",
                    },
                ],
                "recommended_blog_topics": [
                    {
                        "title": f"Getting the Most Out of {brand_name}: A Complete 2026 Guide",
                        "target_keywords": [f"{brand_name} guide", f"{domain} tutorial"],
                        "search_intent_and_angle": "Comprehensive walkthrough for first-time visitors and technical evaluators.",
                    },
                    {
                        "title": "Modern Web Architecture: Why Clean, Standards-Compliant HTML Matters for SEO",
                        "target_keywords": ["clean html seo", "web standards performance"],
                        "search_intent_and_angle": "Educational thought-leadership article attracting software engineers and technical SEOs.",
                    },
                    {
                        "title": f"Top 5 Use Cases for {brand_name} in Technical Documentation and Workflows",
                        "target_keywords": [f"{brand_name} use cases", "technical documentation examples"],
                        "search_intent_and_angle": "Practical use-case showcase highlighting real-world applications.",
                    },
                ],
            },
            "top_five_services": {
                "services": [
                    {
                        "service_name": stated_offerings[0][:90],
                        "description": f"Core web resource and primary informational offering explicitly presented on {domain}.",
                        "target_industry": "Technology, Education, and Digital Publishing",
                        "target_customer": "Web Developers, Technical Writers, and Digital Visitors",
                        "main_benefit": "Provides immediate, standards-compliant access to the site's primary content.",
                        "provenance": "website_derived_fact",
                    },
                    {
                        "service_name": "Technical Documentation & Reference Examples",
                        "description": f"Standardized reference content and domain examples hosted via {domain}.",
                        "target_industry": "Software Engineering & Technical Education",
                        "target_customer": "Software Engineers, QA Testers, and Educators",
                        "main_benefit": "Enables safe, reliable reference linking in documentation and automated tests.",
                        "provenance": "ai_inferred_offering",
                    },
                    {
                        "service_name": "Standards-Compliant Web Portal Delivery",
                        "description": "High-availability HTTP/HTTPS web page delivery with minimal payload overhead.",
                        "target_industry": "Internet Infrastructure & Web Services",
                        "target_customer": "DevOps Engineers and Network Administrators",
                        "main_benefit": "Guarantees fast response times and predictable uptime for web clients.",
                        "provenance": "ai_inferred_offering",
                    },
                    {
                        "service_name": "Domain & IANA Registry Navigation",
                        "description": "Direct outbound navigation to authoritative domain management and coordination bodies.",
                        "target_industry": "Domain Governance & Network Operations",
                        "target_customer": "IT Administrators and Domain Registrants",
                        "main_benefit": "Connects users directly to verified authoritative internet governance resources.",
                        "provenance": "ai_inferred_offering",
                    },
                    {
                        "service_name": "Cross-Platform Web Compatibility Baseline",
                        "description": "Clean semantic markup accessible across browsers, CLI tools, and automated crawlers.",
                        "target_industry": "Cross-Industry Digital Teams",
                        "target_customer": "QA Automation Engineers and Accessibility Auditors",
                        "main_benefit": "Ensures zero rendering blockers across desktop, mobile, and headless user agents.",
                        "provenance": "ai_inferred_offering",
                    },
                ]
            },
            "target_audience": {
                "website_explicit_audience_clues": (
                    extracted.paragraphs[:2]
                    if extracted.paragraphs
                    else [f"Visitors navigating to {domain}"]
                ),
                "primary_audiences": [
                    "Software Engineers, Web Developers, and Technical Documentation Authors",
                    "System Administrators, QA Engineers, and API Integration Specialists",
                ],
                "secondary_audiences": [
                    "Computer Science Educators, Students, and Technical Trainers",
                    "Digital Product Managers and SEO/Content Strategists",
                ],
                "industry_segments": [
                    "Software Development & SaaS",
                    "Internet Infrastructure & Telecommunications",
                    "Technical Education & E-Learning",
                ],
                "business_types": [
                    "B2B Technology Organizations",
                    "Developer Communities & Educational Institutions",
                    "Individual Practitioners & Open-Source Contributors",
                ],
                "customer_needs_and_challenges": [
                    "Need for reliable, standards-compliant web endpoints and clear documentation",
                    "Challenge of expanding minimal web pages into rich, search-optimized conversion funnels",
                    "Requirement for clear navigation, structured metadata, and fast page load performance",
                ],
                "geographical_focus": f"Global reach (public internet accessibility via {domain} with English-language primary content).",
                "recommended_marketing_segments": [
                    "Developer Relations (DevRel) & Technical Content Communities",
                    "Technical SEO & Web Performance Engineering Teams",
                    "Cloud & Web Infrastructure Decision-Makers",
                ],
            },
        }
        return LLMAnalysisPayload.model_validate(demo_dict)
