"""Comprehensive test suite for the AI-Powered Website Link Analysis API."""

import json
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import app, get_analysis_service, get_settings
from app.schemas import (
    LLMAnalysisPayload,
    LinkAnalysisResponse,
    WebsiteExtractedData,
)
from app.services.analysis_service import AnalysisService
from app.services.competitor_service import CompetitorService
from app.services.llm_service import (
    LLMConfigurationError,
    LLMService,
    LLMServiceError,
)
from app.services.website_extractor import (
    WebsiteExtractionError,
    WebsiteExtractorService,
)
from app.utils.validators import (
    SSRFProtectionError,
    URLValidationError,
    is_ip_blocked,
    validate_and_normalize_url,
)


# =============================================================================
# Reusable Fixtures & Sample Data
# =============================================================================

SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CloudPulse Analytics | AI Cloud Cost & FinOps Platform</title>
    <meta name="description" content="CloudPulse helps engineering and finance teams reduce AWS, GCP, and Azure spend by up to 40% with automated FinOps intelligence.">
    <meta name="keywords" content="Cloud FinOps, AWS Cost Optimization, Kubernetes Cost Monitoring, Cloud Billing AI">
    <link rel="canonical" href="https://cloudpulse.example.com/" />
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "CloudPulse Analytics"
    }
    </script>
    <style>
        body { font-family: sans-serif; color: #222; }
        .hidden { display: none; }
    </style>
    <script>
        console.log("Tracking script that should be stripped");
    </script>
</head>
<body>
    <nav role="navigation">
        <a href="/features">Features</a>
        <a href="/pricing">Pricing</a>
    </nav>
    <main>
        <h1>Real-Time Cloud Cost Optimization for Modern Engineering Teams</h1>
        <p>CloudPulse Analytics provides automated cloud cost visibility, Kubernetes rightsizing, and commitment management across AWS, Google Cloud, and Microsoft Azure.</p>
        <p>CloudPulse Analytics provides automated cloud cost visibility, Kubernetes rightsizing, and commitment management across AWS, Google Cloud, and Microsoft Azure.</p>
        <h2>Why Switch to CloudPulse vs Vantage or CloudZero?</h2>
        <p>Unlike legacy billing dashboards, our autonomous AI agents detect idle resources, orphaned EBS volumes, and anomalous spend spikes within 60 seconds.</p>
        <h3>Core Platform Capabilities</h3>
        <ul>
            <li>Automated Kubernetes Pod & Node Rightsizing with zero downtime</li>
            <li>Autonomous Reserved Instance & Savings Plan Autopilot</li>
            <li>Unit Economics & Per-Customer Cost Allocation Telemetry</li>
        </ul>
        <a href="https://cloudpulse.example.com/demo">Book a Demo</a>
        <a href="https://linkedin.com/company/cloudpulse">LinkedIn</a>
        <a href="https://x.com/cloudpulse">X Profile</a>
        <p>Contact our enterprise FinOps team at sales@cloudpulse.example.com or call +1 (415) 555-0199 for a custom architecture review.</p>
    </main>
    <footer>
        <p>Copyright 2026 CloudPulse Inc. All rights reserved.</p>
    </footer>
</body>
</html>
"""


def get_valid_mock_llm_dict() -> dict[str, Any]:
    """Return a complete, valid dictionary matching LLMAnalysisPayload."""
    return {
        "competitor_analysis": {
            "brand_name": "CloudPulse Analytics",
            "brand_overview": (
                "CloudPulse Analytics is a B2B SaaS FinOps and cloud cost intelligence platform "
                "that helps engineering and finance teams monitor, allocate, and reduce multi-cloud "
                "infrastructure spend across AWS, GCP, and Azure."
            ),
            "brand_category": "Cloud FinOps & Cost Optimization Software",
            "website_stated_products_and_services": [
                "Automated cloud cost visibility across AWS, GCP, and Azure",
                "Automated Kubernetes Pod & Node Rightsizing",
                "Autonomous Reserved Instance & Savings Plan Autopilot",
                "Unit Economics & Per-Customer Cost Allocation Telemetry",
                "Real-time anomaly detection for idle resources and orphaned EBS volumes",
            ],
            "inferred_products_and_services": [
                "FinOps executive reporting & forecasting dashboards",
                "CI/CD pull-request cloud cost estimation integrations",
            ],
            "competitors": [
                {
                    "name": "Vantage",
                    "website_or_domain": "vantage.sh",
                    "category_fit": "Direct multi-cloud cost transparency and FinOps automation platform.",
                    "strengths": [
                        "Developer-friendly UI and fast onboarding",
                        "Strong multi-cloud billing integrations (AWS, GCP, Azure, Datadog, Snowflake)",
                    ],
                    "weaknesses": [
                        "Higher tier pricing for autopilot commitment management",
                        "Less emphasis on autonomous sub-minute anomaly remediation",
                    ],
                    "provenance": "website_mentioned",
                },
                {
                    "name": "CloudZero",
                    "website_or_domain": "cloudzero.com",
                    "category_fit": "Enterprise cloud cost intelligence focused on unit economics and engineering allocation.",
                    "strengths": [
                        "Deep unit cost telemetry per customer, feature, and team",
                        "Strong enterprise FinOps consulting support",
                    ],
                    "weaknesses": [
                        "Longer implementation cycle for complex custom tagging",
                        "Primarily focused on visibility rather than automated Kubernetes node mutation",
                    ],
                    "provenance": "website_mentioned",
                },
                {
                    "name": "Cast AI",
                    "website_or_domain": "cast.ai",
                    "category_fit": "Direct competitor in automated Kubernetes cost optimization and rightsizing.",
                    "strengths": [
                        "Real-time autonomous Kubernetes cluster autoscaling and spot instance automation",
                        "Measurable immediate compute savings on EKS, GKE, and AKS",
                    ],
                    "weaknesses": [
                        "Narrower focus on container workloads compared to full-stack non-K8s FinOps",
                        "Requires cluster-level controller permissions",
                    ],
                    "provenance": "ai_market_inference",
                },
            ],
            "brand_advantages": [
                "Sub-minute (60-second) anomaly and orphaned resource detection",
                "Unified coverage combining Kubernetes pod rightsizing, RI/Savings Plan autopilot, and unit economics",
                "Multi-cloud native support across AWS, Google Cloud, and Microsoft Azure",
            ],
            "market_opportunities": [
                "Expand into AI/GPU workload cost optimization (LLM inference & training FinOps)",
                "Offer self-serve freemium tier for Series A/B cloud-native startups",
                "Partner with cloud MSPs and DevOps consultancies for channel distribution",
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
                    "query_topic": "Automated AWS and Kubernetes cost optimization platform",
                    "search_intent": "Commercial Investigation",
                    "target_audience": "VP of Engineering, DevOps Leads, and Platform Engineers",
                    "platform_queries": {
                        "Google": "best automated aws kubernetes cost optimization tool finops",
                        "Facebook": "Cloud FinOps & AWS Cost Optimization groups",
                        "Instagram": "#CloudFinOps #KubernetesOptimization #DevOpsTools",
                        "LinkedIn": "automated cloud cost optimization FinOps platform for engineering teams",
                        "X": "what are teams using to cut AWS and K8s cloud bills automatically?",
                    },
                    "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                },
                {
                    "query_topic": "CloudZero vs Vantage alternatives for multi-cloud FinOps",
                    "search_intent": "Commercial Investigation",
                    "target_audience": "FinOps Practitioners and CTOs comparing vendors",
                    "platform_queries": {
                        "Google": "cloudzero vs vantage alternatives multi cloud cost management",
                        "Facebook": "SaaS CTO & Cloud Infrastructure Cost community discussions",
                        "Instagram": "#FinOps #CloudArchitecture #SaaSMetrics",
                        "LinkedIn": "comparing CloudZero vs Vantage vs autonomous FinOps platforms",
                        "X": "CloudZero vs Vantage vs alternatives for multi-cloud cost allocation",
                    },
                    "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                },
                {
                    "query_topic": "How to reduce orphaned EBS volumes and idle cloud spend",
                    "search_intent": "Informational",
                    "target_audience": "Site Reliability Engineers (SREs) and Cloud Architects",
                    "platform_queries": {
                        "Google": "how to detect orphaned ebs volumes and idle aws resources automatically",
                        "Facebook": "AWS Solutions Architect & SRE cost saving tips",
                        "Instagram": "#AWSArchitecture #SRE #CloudEngineering",
                        "LinkedIn": "reducing wasted cloud spend from idle resources and unattached EBS volumes",
                        "X": "automated scripts or tools for cleaning up orphaned EBS volumes and idle cloud instances",
                    },
                    "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                },
                {
                    "query_topic": "Automated Reserved Instances and AWS Savings Plan autopilot",
                    "search_intent": "Transactional",
                    "target_audience": "CFOs, VP of Finance, and Cloud Procurement Managers",
                    "platform_queries": {
                        "Google": "automated aws savings plan and reserved instance management software",
                        "Facebook": "B2B SaaS CFO & Finance Leaders network",
                        "Instagram": "#SaaSFinance #CloudEconomics #CFOInsights",
                        "LinkedIn": "autonomous Reserved Instance and Savings Plan portfolio optimization",
                        "X": "best autopilot tool for AWS Savings Plans without lock-in risk",
                    },
                    "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                },
                {
                    "query_topic": "Per-customer unit economics and COGS cloud cost allocation",
                    "search_intent": "Commercial Investigation",
                    "target_audience": "SaaS Product Leaders, FinOps Directors, and FP&A Teams",
                    "platform_queries": {
                        "Google": "cloud unit economics software track cost per customer saas cogs",
                        "Facebook": "B2B SaaS Founders & Gross Margin Optimization",
                        "Instagram": "#UnitEconomics #SaaSGrowth #CloudCOGS",
                        "LinkedIn": "measuring cloud cost per customer and improving SaaS gross margins",
                        "X": "how do you track AWS/GCP cost per tenant for B2B SaaS COGS?",
                    },
                    "search_volume_note": "Unverified / Not fabricated (Live keyword tool integration required for exact search volume metrics)",
                },
            ],
        },
        "seo_improvements": {
            "observed_current_seo_facts": {},
            "primary_keywords": [
                "Cloud Cost Optimization Platform",
                "AI FinOps Software",
                "Kubernetes Cost Monitoring",
                "Multi-Cloud Spend Management",
            ],
            "secondary_keywords": [
                "AWS Reserved Instance Autopilot",
                "Unit Economics Cost Allocation",
                "Cloud Spend Anomaly Detection",
                "GCP and Azure Cost Reduction",
            ],
            "long_tail_keywords": [
                "automated kubernetes pod and node rightsizing without downtime",
                "real-time cloud cost anomaly detection for aws gcp azure",
                "cloudzero and vantage alternative for autonomous finops",
                "how to allocate multi-cloud infrastructure cost per customer",
            ],
            "recommended_seo_title": "CloudPulse Analytics | AI Cloud Cost Optimization & FinOps Platform",
            "recommended_meta_description": (
                "Cut AWS, GCP, and Azure spend by up to 40% with CloudPulse Analytics. "
                "Automate Kubernetes rightsizing, RI/Savings Plans, and real-time FinOps telemetry."
            ),
            "recommended_landing_pages": [
                {
                    "title": "Automated Kubernetes Cost Optimization & Rightsizing",
                    "suggested_url_slug": "/solutions/kubernetes-cost-optimization",
                    "purpose_and_target_keyword": "Target 'Kubernetes Cost Monitoring' and convert DevOps/Platform teams looking for zero-downtime pod rightsizing.",
                },
                {
                    "title": "CloudPulse vs. Vantage & CloudZero: Autonomous FinOps Comparison",
                    "suggested_url_slug": "/compare/cloudpulse-vs-vantage-cloudzero",
                    "purpose_and_target_keyword": "Capture high-intent bottom-of-funnel competitor comparison searches.",
                },
                {
                    "title": "SaaS Unit Economics & Per-Customer Cloud Cost Allocation",
                    "suggested_url_slug": "/solutions/saas-unit-economics",
                    "purpose_and_target_keyword": "Target CFOs and FinOps leads searching for SaaS COGS and per-tenant margin tracking.",
                },
            ],
            "recommended_faqs": [
                {
                    "question": "How does CloudPulse reduce AWS, GCP, and Azure spend by up to 40%?",
                    "recommended_answer_summary": "CloudPulse combines 60-second anomaly detection, idle resource cleanup, zero-downtime Kubernetes rightsizing, and autonomous RI/Savings Plan management.",
                },
                {
                    "question": "Does automated Kubernetes pod rightsizing cause application downtime?",
                    "recommended_answer_summary": "No. CloudPulse orchestrates rolling rightsizing adjustments aligned with pod disruption budgets to ensure zero downtime.",
                },
                {
                    "question": "How quickly can engineering teams integrate CloudPulse Analytics?",
                    "recommended_answer_summary": "Read-only billing and telemetry integrations connect in under 15 minutes via IAM roles without requiring application code changes.",
                },
            ],
            "recommended_blog_topics": [
                {
                    "title": "The Complete 2026 Engineering Guide to Zero-Downtime Kubernetes Cost Rightsizing",
                    "target_keywords": [
                        "kubernetes cost rightsizing",
                        "eks cost optimization",
                    ],
                    "search_intent_and_angle": "Informational technical deep-dive showing SREs how to eliminate overprovisioned CPU/memory requests.",
                },
                {
                    "title": "How to Calculate Cloud Cost Per Customer (And Improve SaaS Gross Margins)",
                    "target_keywords": [
                        "cloud unit economics",
                        "cost per customer saas",
                    ],
                    "search_intent_and_angle": "Strategic guide for CTOs and CFOs on mapping shared multi-cloud resources to individual customer tenants.",
                },
                {
                    "title": "7 Hidden Sources of AWS Waste: From Orphaned EBS Volumes to Idle NAT Gateways",
                    "target_keywords": [
                        "orphaned ebs volumes aws",
                        "reduce aws cloud waste",
                    ],
                    "search_intent_and_angle": "Practical checklist with immediate FinOps remediation steps and automated alerting benchmarks.",
                },
            ],
        },
        "top_five_services": {
            "services": [
                {
                    "service_name": "Multi-Cloud Cost Visibility & Spend Intelligence",
                    "description": "Unified real-time cost tracking and executive reporting across AWS, Google Cloud, and Microsoft Azure.",
                    "target_industry": "SaaS, FinTech, E-Commerce, and Enterprise Technology",
                    "target_customer": "VP of Engineering, FinOps Leads, and CTOs",
                    "main_benefit": "Eliminates blind spots across multi-cloud bills and accelerates financial close.",
                    "provenance": "website_derived_fact",
                },
                {
                    "service_name": "Automated Kubernetes Pod & Node Rightsizing",
                    "description": "Continuous rightsizing of containerized workloads and cluster nodes with zero application downtime.",
                    "target_industry": "Cloud-Native SaaS, AI/ML Platforms, and Digital Natives",
                    "target_customer": "Platform Engineers, DevOps Leads, and SRE Teams",
                    "main_benefit": "Cuts container compute overprovisioning by up to 40% without performance degradation.",
                    "provenance": "website_derived_fact",
                },
                {
                    "service_name": "Autonomous Reserved Instance & Savings Plan Autopilot",
                    "description": "AI-driven purchasing, exchanging, and lifecycle management of cloud discount commitments.",
                    "target_industry": "Scale-up and Enterprise Cloud Consumers",
                    "target_customer": "CFOs, VP of Finance, and Cloud Procurement Teams",
                    "main_benefit": "Maximizes commitment discount coverage while minimizing long-term lock-in risk.",
                    "provenance": "website_derived_fact",
                },
                {
                    "service_name": "Unit Economics & Per-Customer Cost Allocation",
                    "description": "Granular telemetry mapping shared cloud infrastructure costs to specific customers, features, and engineering teams.",
                    "target_industry": "B2B Multi-Tenant SaaS and Data Platforms",
                    "target_customer": "Product Leaders, FinOps Directors, and FP&A Analysts",
                    "main_benefit": "Protects gross margins by revealing exact cloud COGS per customer tier.",
                    "provenance": "website_derived_fact",
                },
                {
                    "service_name": "Real-Time Spend Anomaly & Idle Resource Detection",
                    "description": "Autonomous AI agents that identify orphaned EBS volumes, idle instances, and abnormal spend spikes within 60 seconds.",
                    "target_industry": "All Cloud-Hosted Engineering Organizations",
                    "target_customer": "Cloud Infrastructure Managers and On-Call DevOps Engineers",
                    "main_benefit": "Prevents surprise billing shocks by catching runaway cloud costs within one minute.",
                    "provenance": "website_derived_fact",
                },
            ]
        },
        "target_audience": {
            "website_explicit_audience_clues": [
                "Modern Engineering Teams",
                "Finance teams reducing AWS, GCP, and Azure spend",
                "Enterprise FinOps team",
            ],
            "primary_audiences": [
                "VPs of Engineering, CTOs, and Platform Engineering Leaders managing multi-cloud infrastructure",
                "FinOps Practitioners, Cloud Financial Managers, and Directors of Cloud Operations",
            ],
            "secondary_audiences": [
                "Chief Financial Officers (CFOs) and Strategic FP&A teams tracking SaaS gross margins",
                "Site Reliability Engineers (SREs) and Kubernetes Administrators responsible for cluster efficiency",
            ],
            "industry_segments": [
                "B2B & B2C Software-as-a-Service (SaaS)",
                "FinTech & Financial Services",
                "Data Analytics, AI/ML & High-Scale Cloud Natives",
                "Enterprise Digital Transformation Teams",
            ],
            "business_types": [
                "B2B Mid-Market Tech Companies ($10M-$100M ARR)",
                "B2B Enterprise Organizations with >$50k/month cloud spend",
                "High-Growth Cloud-Native Startups",
            ],
            "customer_needs_and_challenges": [
                "Escalating and unpredictable monthly bills across AWS, GCP, and Azure",
                "Overprovisioned Kubernetes clusters where engineers pad CPU/memory requests for safety",
                "Inability to attribute shared infrastructure costs to individual customers or product lines",
                "Delayed detection of orphaned storage volumes and runaway compute jobs",
            ],
            "geographical_focus": (
                "US headquarters signal detected (+1 415 San Francisco area code), serving global English-speaking "
                "cloud-native markets across North America, Europe, and APAC."
            ),
            "recommended_marketing_segments": [
                "High-Growth SaaS Engineering Leaders (AWS/GCP/EKS users with >$25k/mo cloud spend)",
                "Enterprise FinOps Certified Practitioners & Cloud Center of Excellence (CCoE) Directors",
                "SaaS CFOs & Finance VPs focused on Gross Margin & COGS Optimization",
                "Competitor Conquesting Segment (Current users evaluating Vantage, CloudZero, or Kubecost)",
            ],
        },
    }


# =============================================================================
# 1. URL Validation & SSRF Protection Tests
# =============================================================================


class TestURLValidatorsAndSSRF:
    """Tests for URL syntax validation and SSRF protection against internal networks."""

    def test_valid_public_urls(self) -> None:
        """Valid HTTP and HTTPS public URLs should normalize cleanly when DNS resolves to a public IP."""
        with patch(
            "app.utils.validators.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))],
        ):
            normalized = validate_and_normalize_url("https://example.com/about#section")
            assert normalized == "https://example.com/about"

            normalized_root = validate_and_normalize_url("  http://example.com  ")
            assert normalized_root == "http://example.com/"

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "",
            "   ",
            "not-a-url",
            "ftp://example.com/file.txt",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "data:text/html,<h1>Hello</h1>",
            "https://",
            "https://example.com/path with spaces",
        ],
    )
    def test_invalid_urls_rejected(self, invalid_url: str) -> None:
        """Malformed URLs and non-HTTP/HTTPS schemes must raise URLValidationError."""
        with pytest.raises(URLValidationError):
            validate_and_normalize_url(invalid_url, resolve_dns=False)

    @pytest.mark.parametrize(
        "ssrf_url",
        [
            "http://localhost/admin",
            "http://localhost:8000/health",
            "http://127.0.0.1/secret",
            "http://127.0.0.53:80/",
            "http://0.0.0.0/",
            "http://[::1]/",
            "http://10.0.0.1/internal",
            "http://172.16.0.10/admin",
            "http://192.168.1.1/router",
            "http://169.254.169.254/latest/meta-data/",
            "http://100.64.0.1/cgnat",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://internal.corp/dashboard",
            "http://printer.local/",
            "http://intranet/wiki",
            "http://2130706433/",  # Decimal representation of 127.0.0.1
            "http://0x7f000001/",  # Hex representation of 127.0.0.1
            "https://user:password@example.com/",  # Embedded credentials
            "http://example.com:22/",  # Disallowed SSH port
            "http://example.com:6379/",  # Disallowed Redis port
        ],
    )
    def test_ssrf_urls_blocked(self, ssrf_url: str) -> None:
        """Private IPs, localhost, cloud metadata, internal suffixes, and non-web ports must be blocked."""
        with pytest.raises(SSRFProtectionError):
            validate_and_normalize_url(ssrf_url, resolve_dns=False)

    def test_dns_rebinding_to_private_ip_blocked(self) -> None:
        """If a public-looking domain resolves to a private/loopback IP in DNS, SSRF protection must block it."""
        with patch(
            "app.utils.validators.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.250", 80))],
        ):
            with pytest.raises(SSRFProtectionError, match="restricted internal/private IP"):
                validate_and_normalize_url("http://evil-rebind.example.com/", resolve_dns=True)

    def test_is_ip_blocked_helper(self) -> None:
        """Verify IP classification helper accurately distinguishes private vs public IPs."""
        assert is_ip_blocked("127.0.0.1") is True
        assert is_ip_blocked("10.24.0.5") is True
        assert is_ip_blocked("169.254.169.254") is True
        assert is_ip_blocked("::1") is True
        assert is_ip_blocked("::ffff:127.0.0.1") is True
        assert is_ip_blocked("93.184.215.14") is False
        assert is_ip_blocked("8.8.8.8") is False


# =============================================================================
# 2. Website Extraction & HTML Parsing Tests
# =============================================================================


class TestWebsiteExtraction:
    """Tests for HTML parsing, clutter removal, redirect validation, and inaccessible websites."""

    def test_parse_html_extracts_facts_and_strips_clutter(self) -> None:
        """Extractor should capture title, meta, headings, paragraphs, links, signals, and strip scripts/nav/duplicates."""
        extractor = WebsiteExtractorService()
        extracted = extractor.parse_html(
            html_content=SAMPLE_HTML,
            requested_url="https://cloudpulse.example.com/",
            final_url="https://cloudpulse.example.com/",
            http_status_code=200,
        )

        assert extracted.source_type == "website_derived_fact"
        assert extracted.domain == "cloudpulse.example.com"
        assert "CloudPulse Analytics" in extracted.page_title
        assert "reduce AWS, GCP, and Azure spend" in extracted.meta_description
        assert "Cloud FinOps" in extracted.meta_keywords
        assert extracted.canonical_url == "https://cloudpulse.example.com/"

        # Verify H1, H2, H3 extraction
        assert extracted.headings["h1"] == [
            "Real-Time Cloud Cost Optimization for Modern Engineering Teams"
        ]
        assert "Why Switch to CloudPulse vs Vantage or CloudZero?" in extracted.headings["h2"]
        assert "Core Platform Capabilities" in extracted.headings["h3"]

        # Verify duplicate paragraphs were deduplicated and script/style/footer text removed
        combined_paragraphs = " ".join(extracted.paragraphs)
        assert "Tracking script that should be stripped" not in combined_paragraphs
        assert "font-family: sans-serif" not in combined_paragraphs
        assert "Copyright 2026 CloudPulse Inc." not in combined_paragraphs
        assert len(extracted.paragraphs) >= 3

        # Verify business signals
        assert "sales@cloudpulse.example.com" in extracted.business_signals.emails
        assert any("415" in p for p in extracted.business_signals.phone_numbers)
        assert "SoftwareApplication" in extracted.business_signals.schema_org_types
        assert any("linkedin.com" in s for s in extracted.business_signals.social_links)
        assert "Book a Demo" in extracted.business_signals.detected_cta_phrases

    def test_redirect_to_internal_ip_is_blocked(self) -> None:
        """If a public website redirects (302) to http://127.0.0.1/admin, extractor must block it."""
        import asyncio

        extractor = WebsiteExtractorService()

        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"location": "http://169.254.169.254/latest/meta-data/"}

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.return_value = mock_response

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__.return_value = mock_client

        with (
            patch(
                "app.utils.validators.socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))],
            ),
            patch("httpx.AsyncClient", return_value=mock_client_ctx),
        ):
            with pytest.raises(SSRFProtectionError):
                asyncio.run(extractor.extract_from_url("https://example.com/redirect-me"))

    def test_inaccessible_website_timeout_handling(self) -> None:
        """Timeouts when fetching a website must raise WebsiteExtractionError with 504 status."""
        import asyncio

        extractor = WebsiteExtractorService()

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.side_effect = httpx.ReadTimeout("Read timed out")

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__.return_value = mock_client

        with (
            patch(
                "app.utils.validators.socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))],
            ),
            patch("httpx.AsyncClient", return_value=mock_client_ctx),
        ):
            with pytest.raises(WebsiteExtractionError) as exc_info:
                asyncio.run(extractor.extract_from_url("https://slow.example.com"))
            assert exc_info.value.status_code == 504


# =============================================================================
# 3. LLM Integration, Missing API Keys & Structured Validation Tests
# =============================================================================


class TestLLMServiceAndValidation:
    """Tests for missing API keys, malformed LLM responses, fallback behavior, and Pydantic schemas."""

    def test_missing_api_keys_raises_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When neither GEMINI_API_KEY nor OPENAI_API_KEY is set, LLMConfigurationError must be raised."""
        import asyncio

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        test_settings = Settings(
            gemini_api_key="your_gemini_api_key_here",
            openai_api_key="",
        )
        llm_service = LLMService(settings=test_settings)
        extractor = WebsiteExtractorService(settings=test_settings)
        extracted = extractor.parse_html(SAMPLE_HTML, "https://example.com", "https://example.com")

        with pytest.raises(LLMConfigurationError, match="Missing LLM API credentials"):
            asyncio.run(llm_service.generate_structured_analysis(extracted, {}))

    def test_structured_response_validation_rejects_incomplete_sections(self) -> None:
        """LLM output missing required sections or having fewer than 3 competitors / 5 services must fail validation."""
        incomplete_payload = get_valid_mock_llm_dict()
        # Only 1 competitor instead of required >= 3
        incomplete_payload["competitor_analysis"]["competitors"] = incomplete_payload[
            "competitor_analysis"
        ]["competitors"][:1]

        with pytest.raises(LLMServiceError, match="failed Pydantic schema validation"):
            LLMService.parse_and_validate_llm_json(json.dumps(incomplete_payload))

    def test_structured_response_validation_handles_markdown_fences(self) -> None:
        """LLMService should cleanly parse valid JSON even if wrapped in ```json fences."""
        valid_dict = get_valid_mock_llm_dict()
        wrapped = f"```json\n{json.dumps(valid_dict)}\n```"
        validated = LLMService.parse_and_validate_llm_json(wrapped)
        assert isinstance(validated, LLMAnalysisPayload)
        assert len(validated.competitor_analysis.competitors) == 3
        assert len(validated.target_search_queries.queries) == 5
        assert len(validated.top_five_services.services) == 5

    def test_llm_fallback_from_gemini_to_openai(self) -> None:
        """If primary provider (Gemini) fails and fallback is enabled, LLMService should succeed via OpenAI."""
        import asyncio

        test_settings = Settings(
            llm_provider="gemini",
            gemini_api_key="test-gemini-key-12345",
            openai_api_key="test-openai-key-67890",
            enable_llm_fallback=True,
        )
        llm_service = LLMService(settings=test_settings)
        extractor = WebsiteExtractorService(settings=test_settings)
        extracted = extractor.parse_html(SAMPLE_HTML, "https://example.com", "https://example.com")

        with (
            patch.object(
                llm_service,
                "_call_gemini",
                side_effect=LLMServiceError("Simulated Gemini rate limit 429"),
            ),
            patch.object(
                llm_service,
                "_call_openai",
                return_value=json.dumps(get_valid_mock_llm_dict()),
            ),
        ):
            payload, provider, model = asyncio.run(
                llm_service.generate_structured_analysis(extracted, {})
            )
            assert provider == "openai"
            assert model == test_settings.openai_model
            assert payload.competitor_analysis.brand_name == "CloudPulse Analytics"


# =============================================================================
# 4. FastAPI Endpoint Integration Tests (POST /link-analysis)
# =============================================================================


class TestFastAPIEndpoints:
    """End-to-end API tests using FastAPI TestClient."""

    def setup_method(self) -> None:
        app.dependency_overrides.clear()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_health_and_docs_endpoints(self) -> None:
        """GET /health and GET /docs should be accessible and return HTTP 200."""
        client = TestClient(app)

        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        docs_resp = client.get("/docs")
        assert docs_resp.status_code == 200
        assert "swagger-ui" in docs_resp.text.lower()

    def test_post_link_analysis_valid_url_returns_all_five_sections(self) -> None:
        """POST /link-analysis with a valid URL returns HTTP 200 and all 5 required sections."""
        test_settings = Settings(
            llm_provider="gemini",
            gemini_api_key="valid-test-gemini-key",
        )
        extractor = WebsiteExtractorService(settings=test_settings)
        extracted_data = extractor.parse_html(
            SAMPLE_HTML,
            "https://cloudpulse.example.com/",
            "https://cloudpulse.example.com/",
            200,
        )

        mock_extractor = MagicMock(spec=WebsiteExtractorService)
        mock_extractor.extract_from_url = AsyncMock(return_value=extracted_data)

        mock_llm = MagicMock(spec=LLMService)
        mock_llm.generate_structured_analysis = AsyncMock(
            return_value=(
                LLMAnalysisPayload.model_validate(get_valid_mock_llm_dict()),
                "gemini",
                "gemini-2.5-flash",
            )
        )

        service = AnalysisService(
            settings=test_settings,
            extractor_service=mock_extractor,
            competitor_service=CompetitorService(),
            llm_service=mock_llm,
        )
        app.dependency_overrides[get_analysis_service] = lambda: service

        client = TestClient(app)
        response = client.post(
            "/link-analysis",
            json={"url": "https://cloudpulse.example.com"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify top-level keys and all 5 analysis sections
        assert data["url"] == "https://cloudpulse.example.com/"
        assert "metadata" in data
        assert "website_derived_facts" in data
        assert "competitor_analysis" in data
        assert "target_search_queries" in data
        assert "seo_improvements" in data
        assert "top_five_services" in data
        assert "target_audience" in data

        # Validate against LinkAnalysisResponse schema
        validated_resp = LinkAnalysisResponse.model_validate(data)
        assert len(validated_resp.competitor_analysis.competitors) >= 3
        assert len(validated_resp.target_search_queries.queries) == 5
        assert len(validated_resp.top_five_services.services) == 5
        assert (
            validated_resp.seo_improvements.observed_current_seo_facts["current_page_title"]
            == "CloudPulse Analytics | AI Cloud Cost & FinOps Platform"
        )

    def test_post_link_analysis_ssrf_url_returns_400(self) -> None:
        """POST /link-analysis targeting localhost or private IPs must return HTTP 400."""
        client = TestClient(app)
        response = client.post(
            "/link-analysis",
            json={"url": "http://127.0.0.1:8000/admin"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "ssrf_protection_blocked"

    def test_post_link_analysis_invalid_url_returns_400(self) -> None:
        """POST /link-analysis with an invalid URL scheme or syntax returns HTTP 400."""
        client = TestClient(app)
        response = client.post(
            "/link-analysis",
            json={"url": "ftp://invalid-scheme.example.com"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_url"

    def test_post_link_analysis_inaccessible_site_returns_502(self) -> None:
        """POST /link-analysis when target site is down returns HTTP 502."""
        mock_extractor = MagicMock(spec=WebsiteExtractorService)
        mock_extractor.extract_from_url = AsyncMock(
            side_effect=WebsiteExtractionError("Connection refused by remote host", status_code=502)
        )

        service = AnalysisService(extractor_service=mock_extractor)
        app.dependency_overrides[get_analysis_service] = lambda: service

        client = TestClient(app)
        response = client.post(
            "/link-analysis",
            json={"url": "https://unreachable.example.com"},
        )
        assert response.status_code == 502
        assert response.json()["detail"]["error"] == "website_extraction_failed"

    def test_post_link_analysis_missing_api_key_returns_503(self) -> None:
        """POST /link-analysis when API keys are missing returns HTTP 503."""
        extractor = WebsiteExtractorService()
        extracted_data = extractor.parse_html(
            SAMPLE_HTML, "https://example.com", "https://example.com"
        )

        mock_extractor = MagicMock(spec=WebsiteExtractorService)
        mock_extractor.extract_from_url = AsyncMock(return_value=extracted_data)

        mock_llm = MagicMock(spec=LLMService)
        mock_llm.generate_structured_analysis = AsyncMock(
            side_effect=LLMConfigurationError("Missing GEMINI_API_KEY and OPENAI_API_KEY")
        )

        service = AnalysisService(
            extractor_service=mock_extractor,
            llm_service=mock_llm,
        )
        app.dependency_overrides[get_analysis_service] = lambda: service

        client = TestClient(app)
        response = client.post("/link-analysis", json={"url": "https://example.com"})
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "missing_api_key"

    def test_post_link_analysis_llm_failure_returns_502(self) -> None:
        """POST /link-analysis when LLM returns invalid JSON or fails returns HTTP 502."""
        extractor = WebsiteExtractorService()
        extracted_data = extractor.parse_html(
            SAMPLE_HTML, "https://example.com", "https://example.com"
        )

        mock_extractor = MagicMock(spec=WebsiteExtractorService)
        mock_extractor.extract_from_url = AsyncMock(return_value=extracted_data)

        mock_llm = MagicMock(spec=LLMService)
        mock_llm.generate_structured_analysis = AsyncMock(
            side_effect=LLMServiceError("LLM output was not valid JSON")
        )

        service = AnalysisService(
            extractor_service=mock_extractor,
            llm_service=mock_llm,
        )
        app.dependency_overrides[get_analysis_service] = lambda: service

        client = TestClient(app)
        response = client.post("/link-analysis", json={"url": "https://example.com"})
        assert response.status_code == 502
        assert response.json()["detail"]["error"] == "llm_generation_failed"
