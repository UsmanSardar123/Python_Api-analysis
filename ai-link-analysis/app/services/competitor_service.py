"""Competitor intelligence preprocessing and enrichment service."""

import re
from urllib.parse import urlparse

from app.schemas import CompetitorAnalysisSection, WebsiteExtractedData


class CompetitorService:
    """Extracts competitive signals from website data and validates competitor analysis output."""

    def extract_competitor_hints(self, extracted: WebsiteExtractedData) -> dict[str, object]:
        """Scan extracted website content for explicit brand clues, comparison links, and category hints."""
        brand_guess = self._infer_brand_name(extracted)
        comparison_mentions: list[str] = []

        # Look for "vs", "alternative to", "compare" in headings, links, and paragraphs
        comparison_pattern = re.compile(
            r"\b(?:vs\.?|versus|alternative\s+to|compare\s+with|compared\s+to)\s+([A-Z][A-Za-z0-9._-]{1,30})",
            re.IGNORECASE,
        )

        text_pool = (
            extracted.headings.get("h1", [])
            + extracted.headings.get("h2", [])
            + extracted.headings.get("h3", [])
            + [link.text for link in extracted.links]
            + extracted.paragraphs[:15]
        )

        seen_mentions: set[str] = set()
        for snippet in text_pool:
            for match in comparison_pattern.finditer(snippet):
                candidate = match.group(1).strip(" .,;:!?()[]{}")
                if candidate and candidate.lower() not in seen_mentions:
                    seen_mentions.add(candidate.lower())
                    comparison_mentions.append(candidate)

        external_domains: list[str] = []
        seen_domains: set[str] = set()
        for link in extracted.links:
            if not link.is_internal:
                parsed = urlparse(link.href)
                host = (parsed.hostname or "").lower()
                if host and host not in seen_domains:
                    seen_domains.add(host)
                    external_domains.append(host)

        return {
            "inferred_brand_name": brand_guess,
            "explicit_comparison_mentions": comparison_mentions[:10],
            "referenced_external_domains": external_domains[:15],
            "schema_org_types": extracted.business_signals.schema_org_types,
        }

    @staticmethod
    def _infer_brand_name(extracted: WebsiteExtractedData) -> str:
        """Infer a baseline brand name from page title or domain name."""
        if extracted.page_title:
            # Split common title separators: "Brand | Tagline" or "Tagline - Brand"
            parts = re.split(r"\s+[\|\-–—:]\s+", extracted.page_title)
            if parts:
                shortest_meaningful = min(
                    (p.strip() for p in parts if len(p.strip()) >= 2),
                    key=len,
                    default=parts[0].strip(),
                )
                if 2 <= len(shortest_meaningful) <= 50:
                    return shortest_meaningful

        domain = extracted.domain
        if domain.startswith("www."):
            domain = domain[4:]
        base_label = domain.split(".")[0] if domain else "Unknown Brand"
        return base_label.replace("-", " ").title()

    def enrich_and_validate_competitor_section(
        self,
        section: CompetitorAnalysisSection,
        extracted: WebsiteExtractedData,
    ) -> CompetitorAnalysisSection:
        """Ensure brand name fallback and verify provenance tags on competitors."""
        if not section.brand_name or not section.brand_name.strip():
            section.brand_name = self._infer_brand_name(extracted)

        # Check whether any competitor name actually appears verbatim in the extracted website text
        full_site_text_lower = " ".join(
            [
                extracted.page_title,
                extracted.meta_description,
                *extracted.headings.get("h1", []),
                *extracted.headings.get("h2", []),
                *extracted.paragraphs,
            ]
        ).lower()

        for comp in section.competitors:
            comp_name_lower = comp.name.lower().strip()
            if comp_name_lower and len(comp_name_lower) >= 3 and comp_name_lower in full_site_text_lower:
                comp.provenance = "website_mentioned"
            else:
                comp.provenance = "ai_market_inference"

        return section

