"""Main orchestration service combining website extraction, competitor intelligence, and LLM analysis."""

from datetime import datetime, timezone
import time

from app.config import Settings, get_settings
from app.schemas import AnalysisMetadata, LinkAnalysisResponse
from app.services.competitor_service import CompetitorService
from app.services.llm_service import LLMService
from app.services.website_extractor import WebsiteExtractorService


class AnalysisService:
    """Orchestrates end-to-end website extraction and AI-powered link analysis."""

    def __init__(
        self,
        settings: Settings | None = None,
        extractor_service: WebsiteExtractorService | None = None,
        competitor_service: CompetitorService | None = None,
        llm_service: LLMService | None = None,
    ):
        self.settings = settings or get_settings()
        self.extractor_service = extractor_service or WebsiteExtractorService(self.settings)
        self.competitor_service = competitor_service or CompetitorService()
        self.llm_service = llm_service or LLMService(self.settings)

    async def analyze_url(self, raw_url: str) -> LinkAnalysisResponse:
        """Execute full website extraction and 5-section AI analysis for the submitted URL."""
        start_time = time.perf_counter()

        # 1. Extract website facts with SSRF and HTTP safety protections
        extracted_facts = await self.extractor_service.extract_from_url(raw_url)

        # 2. Extract competitor hints and brand signals from factual HTML content
        competitor_hints = self.competitor_service.extract_competitor_hints(extracted_facts)

        # 3. Generate structured 5-section analysis using configured LLM provider
        llm_payload, provider_used, model_used = (
            await self.llm_service.generate_structured_analysis(
                extracted=extracted_facts,
                competitor_hints=competitor_hints,
            )
        )

        # 4. Post-process & enrich sections to guarantee strict fact-vs-inference attribution
        enriched_competitors = self.competitor_service.enrich_and_validate_competitor_section(
            section=llm_payload.competitor_analysis,
            extracted=extracted_facts,
        )

        # Populate ground-truth observed SEO facts in the SEO Improvements section
        observed_seo = {
            "current_page_title": extracted_facts.page_title or "(Missing <title> tag)",
            "current_title_length": str(len(extracted_facts.page_title)),
            "current_meta_description": extracted_facts.meta_description
            or "(Missing meta description)",
            "current_meta_description_length": str(len(extracted_facts.meta_description)),
            "h1_count": str(len(extracted_facts.headings.get("h1", []))),
            "h2_count": str(len(extracted_facts.headings.get("h2", []))),
            "canonical_url": extracted_facts.canonical_url or "(Not specified)",
        }
        llm_payload.seo_improvements.observed_current_seo_facts = observed_seo

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        timestamp_utc = datetime.now(timezone.utc).isoformat()

        return LinkAnalysisResponse(
            url=extracted_facts.final_url,
            metadata=AnalysisMetadata(
                llm_provider=provider_used,
                llm_model=model_used,
                analysis_timestamp_utc=timestamp_utc,
                execution_time_ms=elapsed_ms,
            ),
            website_derived_facts=extracted_facts,
            competitor_analysis=enriched_competitors,
            target_search_queries=llm_payload.target_search_queries,
            seo_improvements=llm_payload.seo_improvements,
            top_five_services=llm_payload.top_five_services,
            target_audience=llm_payload.target_audience,
        )

