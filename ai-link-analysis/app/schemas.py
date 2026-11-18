"""Pydantic schemas for request validation, extracted website facts, and AI analysis output."""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class LinkAnalysisRequest(BaseModel):
    """Request payload for POST /link-analysis."""

    url: str = Field(
        ...,
        min_length=4,
        max_length=2048,
        description="The public HTTP or HTTPS website URL to analyze.",
        examples=["https://example.com"],
    )

    @field_validator("url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        """Trim surrounding whitespace from the submitted URL."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("URL must be a non-empty string.")
        return value.strip()


# =============================================================================
# Website Extraction Models (Facts directly extracted from the HTML document)
# =============================================================================


class ExtractedLink(BaseModel):
    """Represents a hyperlink extracted from the target webpage."""

    text: str = Field(..., description="Anchor text of the link.")
    href: str = Field(..., description="Resolved absolute URL of the link.")
    is_internal: bool = Field(..., description="True if link points to the same domain.")


class ExtractedBusinessSignals(BaseModel):
    """Factual business signals detected directly in the webpage HTML."""

    emails: list[str] = Field(default_factory=list, description="Email addresses found on the page.")
    phone_numbers: list[str] = Field(
        default_factory=list, description="Phone numbers detected on the page."
    )
    social_links: list[str] = Field(
        default_factory=list, description="Social media profile links found on the page."
    )
    schema_org_types: list[str] = Field(
        default_factory=list, description="JSON-LD Schema.org types declared on the page."
    )
    detected_cta_phrases: list[str] = Field(
        default_factory=list, description="Call-to-action button or link phrases detected."
    )


class WebsiteExtractedData(BaseModel):
    """Structured factual data extracted directly from the target website (Website-Derived Facts)."""

    source_type: Literal["website_derived_fact"] = Field(
        default="website_derived_fact",
        description="Indicates all fields in this object are directly extracted from the website HTML.",
    )
    requested_url: str = Field(..., description="Original URL submitted in the request.")
    final_url: str = Field(..., description="Final resolved URL after any safe redirects.")
    domain: str = Field(..., description="Hostname/domain of the analyzed website.")
    http_status_code: int = Field(..., description="HTTP status code returned by the website.")
    page_title: str = Field(default="", description="Extracted <title> or og:title tag content.")
    meta_description: str = Field(
        default="", description="Extracted meta description or og:description content."
    )
    meta_keywords: list[str] = Field(
        default_factory=list, description="Extracted meta keywords if present."
    )
    canonical_url: str = Field(default="", description="Canonical URL tag value if present.")
    headings: dict[str, list[str]] = Field(
        default_factory=lambda: {"h1": [], "h2": [], "h3": []},
        description="Deduplicated H1, H2, and H3 headings from the webpage.",
    )
    paragraphs: list[str] = Field(
        default_factory=list,
        description="Cleaned, deduplicated main body paragraphs from the webpage.",
    )
    links: list[ExtractedLink] = Field(
        default_factory=list,
        description="Relevant internal and external hyperlinks extracted from the page.",
    )
    business_signals: ExtractedBusinessSignals = Field(
        default_factory=ExtractedBusinessSignals,
        description="Explicit business contact, social, and structured data signals.",
    )
    word_count: int = Field(default=0, description="Approximate word count of cleaned body text.")


# =============================================================================
# Section 1: Competitor Analysis
# =============================================================================


class CompetitorProfile(BaseModel):
    """Detailed profile of a relevant competitor."""

    name: str = Field(..., min_length=1, description="Competitor brand or company name.")
    website_or_domain: str = Field(
        default="", description="Known domain or website URL of the competitor (if applicable)."
    )
    category_fit: str = Field(
        ..., description="Why this competitor is relevant to the analyzed brand."
    )
    strengths: list[str] = Field(
        ..., min_length=1, description="Key strengths of this competitor."
    )
    weaknesses: list[str] = Field(
        ..., min_length=1, description="Key weaknesses or gaps of this competitor."
    )
    provenance: Literal["website_mentioned", "ai_market_inference"] = Field(
        default="ai_market_inference",
        description="Whether this competitor was explicitly mentioned on the site or inferred by AI market knowledge.",
    )


class CompetitorAnalysisSection(BaseModel):
    """Section 1: Competitor Analysis."""

    brand_name: str = Field(..., min_length=1, description="Identified brand or organization name.")
    brand_overview: str = Field(
        ..., min_length=10, description="Comprehensive overview of the brand and its value proposition."
    )
    brand_category: str = Field(
        ..., min_length=2, description="Primary industry/market category of the brand."
    )
    website_stated_products_and_services: list[str] = Field(
        default_factory=list,
        description="Products and services explicitly stated on the website (Website-Derived Facts).",
    )
    inferred_products_and_services: list[str] = Field(
        default_factory=list,
        description="Additional or implied products/services inferred by AI from site context (AI Inference).",
    )
    competitors: list[CompetitorProfile] = Field(
        ...,
        min_length=3,
        description="At least three relevant competitors with strengths and weaknesses.",
    )
    brand_advantages: list[str] = Field(
        ..., min_length=1, description="Competitive advantages of the analyzed brand."
    )
    market_opportunities: list[str] = Field(
        ..., min_length=1, description="Strategic market opportunities and growth areas."
    )


# =============================================================================
# Section 2: Target Search Queries
# =============================================================================


class PlatformSearchQueries(BaseModel):
    """Platform-tailored search phrases across the 5 required channels."""

    Google: str = Field(..., min_length=2, description="Search query tailored for Google Search.")
    Facebook: str = Field(..., min_length=2, description="Search query tailored for Facebook.")
    Instagram: str = Field(
        ..., min_length=2, description="Search query or hashtag search tailored for Instagram."
    )
    LinkedIn: str = Field(..., min_length=2, description="Search query tailored for LinkedIn.")
    X: str = Field(..., min_length=2, description="Search query tailored for X (formerly Twitter).")


class CustomerSearchQueryItem(BaseModel):
    """Individual customer search query cluster with platform variations, intent, and audience."""

    query_topic: str = Field(
        ..., min_length=2, description="Core customer search query or topic."
    )
    search_intent: Literal[
        "Informational", "Navigational", "Commercial Investigation", "Transactional"
    ] = Field(..., description="Primary search intent classification.")
    target_audience: str = Field(
        ..., min_length=2, description="Specific audience persona executing this search."
    )
    platform_queries: PlatformSearchQueries = Field(
        ...,
        description="How customers search for this query across Google, Facebook, Instagram, LinkedIn, and X.",
    )
    search_volume_note: str = Field(
        default="Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
        description="Explicit policy note confirming search volumes are never fabricated.",
    )


class TargetSearchQueriesSection(BaseModel):
    """Section 2: Target Search Queries (5 customer queries across Google, Facebook, Instagram, LinkedIn, and X)."""

    data_provenance: Literal["ai_generated_recommendation"] = Field(
        default="ai_generated_recommendation",
        description="Clarifies that target search queries are AI-generated strategic suggestions.",
    )
    volume_integrity_policy: str = Field(
        default="Search volumes are intentionally omitted and never fabricated. Qualitative intent and audience alignment are provided instead.",
        description="Guarantee that no fake search volume numbers are invented.",
    )
    queries: list[CustomerSearchQueryItem] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Five relevant customer search queries across Google, Facebook, Instagram, LinkedIn, and X.",
    )


# =============================================================================
# Section 3: SEO Improvements
# =============================================================================


class RecommendedLandingPage(BaseModel):
    """Recommended landing page structure for SEO growth."""

    title: str = Field(..., min_length=2, description="Suggested landing page title.")
    suggested_url_slug: str = Field(..., min_length=2, description="Suggested URL path/slug.")
    purpose_and_target_keyword: str = Field(
        ..., min_length=5, description="Target keyword and conversion goal of the page."
    )


class RecommendedFAQ(BaseModel):
    """Recommended FAQ entry for on-page SEO and featured snippets."""

    question: str = Field(..., min_length=5, description="Frequently asked customer question.")
    recommended_answer_summary: str = Field(
        ..., min_length=5, description="Concise, authoritative answer outline."
    )


class RecommendedBlogTopic(BaseModel):
    """Recommended blog article topic for content marketing."""

    title: str = Field(..., min_length=5, description="Suggested blog post headline.")
    target_keywords: list[str] = Field(
        ..., min_length=1, description="Keywords targeted by this blog post."
    )
    search_intent_and_angle: str = Field(
        ..., min_length=5, description="Content angle and reader value proposition."
    )


class SEOImprovementsSection(BaseModel):
    """Section 3: SEO Improvements."""

    observed_current_seo_facts: dict[str, str] = Field(
        default_factory=dict,
        description="Website-derived facts regarding current title, meta description, and H1 status.",
    )
    primary_keywords: list[str] = Field(
        ..., min_length=3, description="High-priority primary SEO keywords."
    )
    secondary_keywords: list[str] = Field(
        ..., min_length=3, description="Supporting secondary SEO keywords."
    )
    long_tail_keywords: list[str] = Field(
        ..., min_length=3, description="Specific, high-intent long-tail keyword phrases."
    )
    recommended_seo_title: str = Field(
        ...,
        min_length=10,
        max_length=120,
        description="Optimized SEO <title> recommendation (ideally 50-60 characters).",
    )
    recommended_meta_description: str = Field(
        ...,
        min_length=30,
        max_length=300,
        description="Optimized meta description recommendation (ideally 140-160 characters).",
    )
    recommended_landing_pages: list[RecommendedLandingPage] = Field(
        ..., min_length=2, description="Recommended new or improved landing pages."
    )
    recommended_faqs: list[RecommendedFAQ] = Field(
        ..., min_length=3, description="Recommended FAQ items for schema markup and user clarity."
    )
    recommended_blog_topics: list[RecommendedBlogTopic] = Field(
        ..., min_length=3, description="Recommended blog topics to capture organic traffic."
    )


# =============================================================================
# Section 4: Top Five Services
# =============================================================================


class ServiceItem(BaseModel):
    """Individual service offering analysis."""

    service_name: str = Field(..., min_length=2, description="Name of the service or core offering.")
    description: str = Field(
        ..., min_length=10, description="Clear description of what the service delivers."
    )
    target_industry: str = Field(
        ..., min_length=2, description="Primary industry vertical(s) suited for this service."
    )
    target_customer: str = Field(
        ..., min_length=2, description="Ideal customer profile or buyer role."
    )
    main_benefit: str = Field(
        ..., min_length=5, description="Primary measurable or strategic benefit to the customer."
    )
    provenance: Literal["website_derived_fact", "ai_inferred_offering"] = Field(
        default="website_derived_fact",
        description="Distinguishes whether this service was directly stated on the website or inferred by AI.",
    )


class TopFiveServicesSection(BaseModel):
    """Section 4: Top Five Services."""

    services: list[ServiceItem] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Top five services offered by (or strategically aligned with) the website.",
    )


# =============================================================================
# Section 5: Target Audience
# =============================================================================


class TargetAudienceSection(BaseModel):
    """Section 5: Target Audience."""

    website_explicit_audience_clues: list[str] = Field(
        default_factory=list,
        description="Direct textual clues from the website about who it serves (Website-Derived Facts).",
    )
    primary_audiences: list[str] = Field(
        ..., min_length=2, description="Primary target customer personas and decision-makers."
    )
    secondary_audiences: list[str] = Field(
        ..., min_length=2, description="Secondary or adjacent target audiences and influencers."
    )
    industry_segments: list[str] = Field(
        ..., min_length=2, description="Key industry verticals and market segments."
    )
    business_types: list[str] = Field(
        ...,
        min_length=1,
        description="Business models served (e.g., B2B Enterprise, SMBs, SaaS Startups, B2C Consumers).",
    )
    customer_needs_and_challenges: list[str] = Field(
        ...,
        min_length=3,
        description="Core pain points, operational challenges, and needs of the target audience.",
    )
    geographical_focus: str = Field(
        ...,
        min_length=2,
        description="Geographical market focus (distinguishing website-stated location vs inferred global/regional reach).",
    )
    recommended_marketing_segments: list[str] = Field(
        ...,
        min_length=3,
        description="Actionable marketing segments for paid, organic, and outbound campaigns.",
    )


# =============================================================================
# Complete LLM Structured Output & Full API Response
# =============================================================================


class LLMAnalysisPayload(BaseModel):
    """Schema enforced directly on the LLM JSON response containing all 5 required sections."""

    competitor_analysis: CompetitorAnalysisSection
    target_search_queries: TargetSearchQueriesSection
    seo_improvements: SEOImprovementsSection
    top_five_services: TopFiveServicesSection
    target_audience: TargetAudienceSection


class AnalysisMetadata(BaseModel):
    """Metadata describing the LLM execution, timing, and fact-vs-inference policy."""

    llm_provider: str = Field(..., description="LLM provider used for the analysis (e.g., gemini, openai).")
    llm_model: str = Field(..., description="Specific model identifier used.")
    analysis_timestamp_utc: str = Field(..., description="ISO-8601 UTC timestamp of the analysis.")
    execution_time_ms: float = Field(..., description="Total end-to-end processing time in milliseconds.")
    fact_vs_inference_notice: str = Field(
        default=(
            "Factual data scraped directly from the HTML is stored in 'website_derived_facts' and "
            "explicitly tagged fields (e.g., 'website_stated_products_and_services', 'observed_current_seo_facts', "
            "and 'provenance=website_derived_fact'). Strategic recommendations, competitor comparisons, and "
            "keyword suggestions are AI-generated inferences based on the extracted content."
        ),
        description="Explanation of how website-derived facts are separated from AI-generated insights.",
    )


class LinkAnalysisResponse(BaseModel):
    """Top-level response returned by POST /link-analysis."""

    url: str = Field(..., description="Final analyzed website URL.")
    metadata: AnalysisMetadata = Field(..., description="Execution and model provenance metadata.")
    website_derived_facts: WebsiteExtractedData = Field(
        ...,
        description="Directly extracted factual content from the target website (no AI hallucination).",
    )
    competitor_analysis: CompetitorAnalysisSection = Field(
        ..., description="1. Competitor Analysis section."
    )
    target_search_queries: TargetSearchQueriesSection = Field(
        ..., description="2. Target Search Queries section."
    )
    seo_improvements: SEOImprovementsSection = Field(
        ..., description="3. SEO Improvements section."
    )
    top_five_services: TopFiveServicesSection = Field(
        ..., description="4. Top Five Services section."
    )
    target_audience: TargetAudienceSection = Field(
        ..., description="5. Target Audience section."
    )

