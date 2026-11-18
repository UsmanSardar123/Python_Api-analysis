"""FastAPI application entrypoint exposing POST /link-analysis and health endpoints."""

import logging
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.schemas import LinkAnalysisRequest, LinkAnalysisResponse
from app.services.analysis_service import AnalysisService
from app.services.llm_service import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMServiceError,
    redact_secrets,
)
from app.services.website_extractor import WebsiteExtractionError
from app.utils.rate_limiter import enforce_rate_limit
from app.utils.validators import SSRFProtectionError, URLValidationError

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=False,
    description=(
        "Production-minded AI-Powered Website Link Analysis API. "
        "Extracts factual website content with SSRF protection and generates a structured "
        "five-part strategic analysis: Competitor Analysis, Target Search Queries, "
        "SEO Improvements, Top Five Services, and Target Audience."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

allowed_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)


def get_analysis_service(
    current_settings: Settings = Depends(get_settings),
) -> AnalysisService:
    """Dependency provider for AnalysisService."""
    return AnalysisService(settings=current_settings)


@app.get("/", tags=["Health"])
async def root(current_settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Root welcome endpoint."""
    return {
        "service": current_settings.app_name,
        "version": current_settings.app_version,
        "docs": "/docs",
        "analysis_endpoint": "POST /link-analysis",
    }


@app.get("/health", tags=["Health"])
async def health_check(
    current_settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Service readiness and LLM configuration health endpoint."""
    return {
        "status": "healthy",
        "version": current_settings.app_version,
        "configured_primary_provider": current_settings.llm_provider,
        "configured_gemini_model": current_settings.gemini_model,
        "configured_openai_model": current_settings.openai_model,
        "gemini_key_configured": current_settings.has_valid_gemini_key(),
        "openai_key_configured": current_settings.has_valid_openai_key(),
        "demo_mode_enabled": current_settings.enable_demo_mode_without_api_key,
    }


@app.post(
    "/link-analysis",
    response_model=LinkAnalysisResponse,
    status_code=status.HTTP_200_OK,
    tags=["Link Analysis"],
    dependencies=[Depends(enforce_rate_limit)],
    summary="Analyze a website URL and generate 5 strategic AI marketing & SEO sections",
    responses={
        400: {"description": "Invalid URL format or SSRF policy violation"},
        401: {"description": "Invalid or unauthorized LLM API key"},
        413: {"description": "Target website response exceeds maximum size limit"},
        422: {"description": "Validation error or unprocessable website content"},
        429: {"description": "Rate limit exceeded"},
        502: {"description": "Upstream website unreachable or LLM generation failure"},
        503: {"description": "Missing LLM API credentials configuration"},
        504: {"description": "Upstream website fetch timed out"},
    },
)
async def analyze_link(
    payload: LinkAnalysisRequest,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> LinkAnalysisResponse:
    """Fetch, validate, and analyze a public website URL using AI."""
    try:
        return await analysis_service.analyze_url(payload.url)
    except SSRFProtectionError as exc:
        logger.warning("SSRF protection blocked URL '%s': %s", payload.url, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ssrf_protection_blocked",
                "message": str(exc),
            },
        ) from exc
    except URLValidationError as exc:
        logger.info("URL validation failed for '%s': %s", payload.url, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_url",
                "message": str(exc),
            },
        ) from exc
    except WebsiteExtractionError as exc:
        logger.warning("Website extraction failed for '%s': %s", payload.url, exc.message)
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": "website_extraction_failed",
                "message": exc.message,
            },
        ) from exc
    except LLMConfigurationError as exc:
        safe_msg = redact_secrets(str(exc))
        logger.error("LLM configuration error: %s", safe_msg)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "missing_api_key",
                "message": safe_msg,
            },
        ) from exc
    except LLMAuthenticationError as exc:
        safe_msg = redact_secrets(str(exc))
        logger.error("LLM authentication error: %s", safe_msg)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_api_key",
                "message": safe_msg,
            },
        ) from exc
    except LLMServiceError as exc:
        safe_msg = redact_secrets(str(exc))
        logger.error("LLM generation error for '%s': %s", payload.url, safe_msg)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "llm_generation_failed",
                "message": safe_msg,
            },
        ) from exc


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all handler ensuring internal stack traces are never leaked in responses."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {
                "error": "internal_server_error",
                "message": "An unexpected internal error occurred while processing the request.",
            }
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development",
    )

