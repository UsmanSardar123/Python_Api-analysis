"""Website extraction service using HTTPX and BeautifulSoup4 with SSRF protection."""

import json
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Comment

from app.config import Settings, get_settings
from app.schemas import ExtractedBusinessSignals, ExtractedLink, WebsiteExtractedData
from app.utils.validators import (
    SSRFProtectionError,
    URLValidationError,
    validate_and_normalize_url,
)

# Regex patterns for extracting factual business signals
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,15}\b")
PHONE_REGEX = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-])\d{3,4}[\s.-]\d{3,4}\b"
)

SOCIAL_DOMAINS = (
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "github.com",
    "tiktok.com",
)

CTA_KEYWORDS = (
    "get started",
    "contact us",
    "book a demo",
    "request a demo",
    "start free",
    "free trial",
    "sign up",
    "schedule a call",
    "get a quote",
    "pricing",
    "learn more",
    "buy now",
    "subscribe",
)


class WebsiteExtractionError(Exception):
    """Raised when fetching or parsing the target website fails."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class WebsiteExtractorService:
    """Fetches, validates, cleans, and extracts structured content from a webpage."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def extract_from_url(self, raw_url: str) -> WebsiteExtractedData:
        """Validate URL, safely fetch HTML with redirect and size protection, and parse facts.

        Args:
            raw_url: The user-submitted website URL.

        Returns:
            WebsiteExtractedData populated with extracted HTML facts.

        Raises:
            URLValidationError: If the URL is syntactically invalid.
            SSRFProtectionError: If the URL or any redirect target resolves to a blocked IP/host.
            WebsiteExtractionError: If the website is unreachable, times out, or returns non-HTML/error status.
        """
        normalized_url = validate_and_normalize_url(raw_url, resolve_dns=True)
        final_url, status_code, html_content = await self._fetch_html_safely(normalized_url)
        return self.parse_html(
            html_content=html_content,
            requested_url=normalized_url,
            final_url=final_url,
            http_status_code=status_code,
        )

    async def _fetch_html_safely(self, initial_url: str) -> tuple[str, int, str]:
        """Fetch HTML with manual redirect validation, timeout enforcement, and byte limits."""
        timeout = httpx.Timeout(
            timeout=self.settings.http_timeout_seconds,
            connect=min(10.0, self.settings.http_timeout_seconds),
        )
        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        current_url = initial_url
        redirects_followed = 0

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers=headers,
            verify=True,
            trust_env=False,
        ) as client:
            while True:
                try:
                    async with client.stream("GET", current_url) as response:
                        # Handle redirects manually to enforce SSRF validation on every hop
                        if response.status_code in {301, 302, 303, 307, 308}:
                            if redirects_followed >= self.settings.max_redirects:
                                raise WebsiteExtractionError(
                                    f"Maximum redirect limit ({self.settings.max_redirects}) exceeded.",
                                    status_code=422,
                                )
                            location = response.headers.get("location")
                            if not location:
                                raise WebsiteExtractionError(
                                    f"Redirect response ({response.status_code}) missing Location header.",
                                    status_code=502,
                                )
                            next_url = urljoin(current_url, location.strip())
                            # Validate the redirect target against SSRF and URL rules
                            current_url = validate_and_normalize_url(next_url, resolve_dns=True)
                            redirects_followed += 1
                            continue

                        if response.status_code >= 400:
                            raise WebsiteExtractionError(
                                f"Website returned HTTP status {response.status_code} for '{current_url}'.",
                                status_code=422 if response.status_code < 500 else 502,
                            )

                        content_type = (response.headers.get("content-type") or "").lower()
                        if content_type and not any(
                            allowed in content_type
                            for allowed in ("text/html", "application/xhtml+xml", "text/plain")
                        ):
                            raise WebsiteExtractionError(
                                f"Unsupported Content-Type '{content_type}'. Expected an HTML webpage.",
                                status_code=422,
                            )

                        content_length_header = response.headers.get("content-length")
                        if content_length_header and content_length_header.isdigit():
                            if int(content_length_header) > self.settings.max_response_bytes:
                                raise WebsiteExtractionError(
                                    f"Response Content-Length ({content_length_header} bytes) exceeds limit of {self.settings.max_response_bytes} bytes.",
                                    status_code=413,
                                )

                        chunks: list[bytes] = []
                        total_bytes = 0
                        async for chunk in response.aiter_bytes(chunk_size=16_384):
                            total_bytes += len(chunk)
                            if total_bytes > self.settings.max_response_bytes:
                                raise WebsiteExtractionError(
                                    f"Website response exceeded maximum allowed size of {self.settings.max_response_bytes} bytes.",
                                    status_code=413,
                                )
                            chunks.append(chunk)

                        raw_bytes = b"".join(chunks)
                        encoding = response.encoding or "utf-8"
                        try:
                            html_text = raw_bytes.decode(encoding, errors="replace")
                        except LookupError:
                            html_text = raw_bytes.decode("utf-8", errors="replace")

                        return current_url, response.status_code, html_text

                except (URLValidationError, SSRFProtectionError, WebsiteExtractionError):
                    raise
                except httpx.TimeoutException as exc:
                    raise WebsiteExtractionError(
                        f"Timed out while fetching '{current_url}' after {self.settings.http_timeout_seconds}s.",
                        status_code=504,
                    ) from exc
                except httpx.RequestError as exc:
                    raise WebsiteExtractionError(
                        f"Unable to connect to website '{current_url}': {exc}",
                        status_code=502,
                    ) from exc

    def parse_html(
        self,
        html_content: str,
        requested_url: str,
        final_url: str,
        http_status_code: int = 200,
    ) -> WebsiteExtractedData:
        """Parse HTML content using BeautifulSoup, removing clutter and extracting key facts."""
        if not html_content or not html_content.strip():
            raise WebsiteExtractionError("Website returned an empty HTML document.", status_code=422)

        soup = BeautifulSoup(html_content, "html.parser")
        parsed_final = urlparse(final_url)
        domain = (parsed_final.hostname or "").lower()

        # 1. Extract metadata and JSON-LD before removing tags
        page_title = self._extract_title(soup)
        meta_description = self._extract_meta_description(soup)
        meta_keywords = self._extract_meta_keywords(soup)
        canonical_url = self._extract_canonical_url(soup, final_url)
        schema_org_types = self._extract_schema_org_types(soup)

        # 2. Extract links and business signals before stripping nav/footer
        links, social_links, cta_phrases = self._extract_links_and_ctas(soup, final_url, domain)

        # 3. Remove scripts, styles, comments, and non-content elements
        for tag in soup(
            [
                "script",
                "style",
                "noscript",
                "iframe",
                "svg",
                "canvas",
                "template",
                "form",
                "button",
            ]
        ):
            tag.decompose()

        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Extract emails and phone numbers from visible text before removing footer/header
        full_visible_text = soup.get_text(separator=" ", strip=True)
        emails = self._extract_emails(full_visible_text)
        phone_numbers = self._extract_phones(full_visible_text)

        # Remove navigation, header, footer, and aside clutter for main content extraction
        for clutter_tag in soup.find_all(["nav", "footer", "aside"]):
            clutter_tag.decompose()

        for attr_clutter in soup.find_all(
            attrs={
                "role": re.compile(r"^(navigation|banner|contentinfo|complementary)$", re.I)
            }
        ):
            attr_clutter.decompose()

        # 4. Extract deduplicated headings (H1, H2, H3)
        headings = self._extract_headings(soup)

        # 5. Extract deduplicated paragraphs and meaningful list items
        paragraphs = self._extract_paragraphs(soup)

        word_count = sum(len(p.split()) for p in paragraphs) + sum(
            len(h.split()) for h_list in headings.values() for h in h_list
        )

        return WebsiteExtractedData(
            requested_url=requested_url,
            final_url=final_url,
            domain=domain,
            http_status_code=http_status_code,
            page_title=page_title,
            meta_description=meta_description,
            meta_keywords=meta_keywords,
            canonical_url=canonical_url,
            headings=headings,
            paragraphs=paragraphs,
            links=links,
            business_signals=ExtractedBusinessSignals(
                emails=emails,
                phone_numbers=phone_numbers,
                social_links=social_links,
                schema_org_types=schema_org_types,
                detected_cta_phrases=cta_phrases,
            ),
            word_count=word_count,
        )

    @staticmethod
    def _clean_whitespace(text: str) -> str:
        """Collapse multiple whitespace characters into a single space."""
        return re.sub(r"\s+", " ", text or "").strip()

    def _extract_title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            title = self._clean_whitespace(soup.title.string)
            if title:
                return title[:300]

        for prop in ("og:title", "twitter:title"):
            meta = soup.find("meta", attrs={"property": prop}) or soup.find(
                "meta", attrs={"name": prop}
            )
            if meta and meta.get("content"):
                return self._clean_whitespace(str(meta["content"]))[:300]

        h1 = soup.find("h1")
        if h1:
            return self._clean_whitespace(h1.get_text())[:300]

        return ""

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        for attr_key, attr_val in (
            ("name", "description"),
            ("property", "og:description"),
            ("name", "twitter:description"),
        ):
            meta = soup.find(
                "meta", attrs={attr_key: re.compile(f"^{attr_val}$", re.I)}
            )
            if meta and meta.get("content"):
                desc = self._clean_whitespace(str(meta["content"]))
                if desc:
                    return desc[:600]
        return ""

    def _extract_meta_keywords(self, soup: BeautifulSoup) -> list[str]:
        meta = soup.find("meta", attrs={"name": re.compile(r"^keywords$", re.I)})
        if meta and meta.get("content"):
            raw = str(meta["content"])
            keywords = [self._clean_whitespace(k) for k in raw.split(",")]
            seen: set[str] = set()
            deduped: list[str] = []
            for kw in keywords:
                if kw and kw.lower() not in seen:
                    seen.add(kw.lower())
                    deduped.append(kw)
            return deduped[:25]
        return []

    def _extract_canonical_url(self, soup: BeautifulSoup, base_url: str) -> str:
        link = soup.find("link", attrs={"rel": lambda r: r and "canonical" in r})
        if link and link.get("href"):
            return urljoin(base_url, str(link["href"]).strip())
        return ""

    def _extract_schema_org_types(self, soup: BeautifulSoup) -> list[str]:
        types: list[str] = []
        seen: set[str] = set()
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw_json = script.string or script.get_text()
            if not raw_json:
                continue
            try:
                data = json.loads(raw_json)
            except Exception:
                continue
            self._collect_schema_types(data, types, seen)
        return types[:15]

    def _collect_schema_types(
        self, node: object, acc: list[str], seen: set[str]
    ) -> None:
        if isinstance(node, dict):
            node_type = node.get("@type")
            if isinstance(node_type, str) and node_type not in seen:
                seen.add(node_type)
                acc.append(node_type)
            elif isinstance(node_type, list):
                for item in node_type:
                    if isinstance(item, str) and item not in seen:
                        seen.add(item)
                        acc.append(item)
            for value in node.values():
                self._collect_schema_types(value, acc, seen)
        elif isinstance(node, list):
            for item in node:
                self._collect_schema_types(item, acc, seen)

    def _extract_headings(self, soup: BeautifulSoup) -> dict[str, list[str]]:
        headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        for level in ("h1", "h2", "h3"):
            seen: set[str] = set()
            for tag in soup.find_all(level):
                text = self._clean_whitespace(tag.get_text(separator=" "))
                if len(text) < 2:
                    continue
                norm = text.lower()
                if norm not in seen:
                    seen.add(norm)
                    headings[level].append(text[:250])
                if len(headings[level]) >= 25:
                    break
        return headings

    def _extract_paragraphs(self, soup: BeautifulSoup) -> list[str]:
        paragraphs: list[str] = []
        seen: set[str] = set()

        for tag in soup.find_all(["p", "li", "article", "section"]):
            # Avoid duplicating parent containers if they contain nested p tags
            if tag.name in {"article", "section"} and tag.find(["p", "li"]):
                continue
            text = self._clean_whitespace(tag.get_text(separator=" "))
            # Filter out very short UI fragments or boilerplate
            if len(text) < 25:
                continue
            norm = text.lower()
            if norm not in seen:
                seen.add(norm)
                paragraphs.append(text[:800])
            if len(paragraphs) >= 40:
                break

        # Fallback if page uses divs without standard <p> tags
        if not paragraphs:
            for div in soup.find_all("div"):
                if div.find(["div", "p", "section"]):
                    continue
                text = self._clean_whitespace(div.get_text(separator=" "))
                if len(text) >= 25:
                    norm = text.lower()
                    if norm not in seen:
                        seen.add(norm)
                        paragraphs.append(text[:800])
                if len(paragraphs) >= 25:
                    break

        return paragraphs

    def _extract_links_and_ctas(
        self, soup: BeautifulSoup, base_url: str, base_domain: str
    ) -> tuple[list[ExtractedLink], list[str], list[str]]:
        links: list[ExtractedLink] = []
        social_links: list[str] = []
        cta_phrases: list[str] = []

        seen_hrefs: set[str] = set()
        seen_socials: set[str] = set()
        seen_ctas: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            raw_href = str(a_tag["href"]).strip()
            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            resolved = urljoin(base_url, raw_href)
            parsed = urlparse(resolved)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue

            link_host = parsed.hostname.lower()
            text = self._clean_whitespace(a_tag.get_text(separator=" "))

            # Check for social media links
            if any(
                link_host == soc or link_host.endswith(f".{soc}")
                for soc in SOCIAL_DOMAINS
            ):
                if resolved not in seen_socials:
                    seen_socials.add(resolved)
                    social_links.append(resolved)

            # Check for CTA phrases
            if text and any(cta in text.lower() for cta in CTA_KEYWORDS):
                norm_cta = text.lower()
                if norm_cta not in seen_ctas and len(text) <= 60:
                    seen_ctas.add(norm_cta)
                    cta_phrases.append(text)

            if resolved not in seen_hrefs and len(links) < 40:
                seen_hrefs.add(resolved)
                is_internal = (
                    link_host == base_domain
                    or link_host.endswith(f".{base_domain}")
                    or base_domain.endswith(f".{link_host}")
                )
                links.append(
                    ExtractedLink(
                        text=(text or parsed.path or resolved)[:120],
                        href=resolved,
                        is_internal=is_internal,
                    )
                )

        return links, social_links[:15], cta_phrases[:15]

    @staticmethod
    def _extract_emails(text: str) -> list[str]:
        found = EMAIL_REGEX.findall(text)
        seen: set[str] = set()
        emails: list[str] = []
        for email in found:
            lower = email.lower()
            if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
                continue
            if lower not in seen:
                seen.add(lower)
                emails.append(email)
            if len(emails) >= 10:
                break
        return emails

    @staticmethod
    def _extract_phones(text: str) -> list[str]:
        found = PHONE_REGEX.findall(text)
        seen: set[str] = set()
        phones: list[str] = []
        for phone in found:
            cleaned = re.sub(r"\s+", " ", phone).strip()
            digits = re.sub(r"\D", "", cleaned)
            if 7 <= len(digits) <= 15 and digits not in seen:
                seen.add(digits)
                phones.append(cleaned)
            if len(phones) >= 10:
                break
        return phones
