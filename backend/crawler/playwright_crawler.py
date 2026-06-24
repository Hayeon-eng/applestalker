"""
Fast HTTP Crawler (Optimized for Speed)
No browser automation - pure HTTP requests for maximum speed.
Saves data to PostgreSQL database, no file storage.
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path

from bs4 import BeautifulSoup
import json
import httpx


class PlaywrightCrawler:
    """
    High-speed async crawler using httpx.
    No browser automation - optimized for speed.
    All data saved to database, no file storage.
    """

    def __init__(
        self,
        screenshots_dir: str = "./screenshots",
        snapshots_dir: str = "./snapshots",
        user_agent: str = None,
        use_playwright: bool = True,  # 이미지 추출을 위해 Playwright 사용
        max_concurrent: int = 3,
        timeout_ms: int = 60000,  # 60 초 - 이미지 로딩 시간 고려
    ):
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.max_concurrent = max_concurrent
        self.timeout_ms = timeout_ms
        self.screenshots_dir = Path(screenshots_dir)
        self.snapshots_dir = Path(snapshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        # HTTP client with connection pooling
        self.client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        # Playwright for image extraction
        self.use_playwright = use_playwright
        self.browser = None

    async def start(self):
        """Initialize HTTP client and Playwright browser"""
        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=httpx.Timeout(60.0, connect=15.0),  # 60 초 (이미지 로딩 고려)
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
        
        # Initialize Playwright for image extraction if enabled
        if self.use_playwright:
            try:
                from playwright.async_api import async_playwright
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ]
                )
            except Exception as e:
                print(f"Playwright initialization failed: {e}")
                self.browser = None

    async def close(self):
        """Close HTTP client and Playwright browser"""
        if self.client:
            await self.client.aclose()
        if self.browser:
            await self.browser.close()

    async def crawl_page(
        self,
        url: str,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """
        Crawl a single page and extract all data.
        Fast HTTP-only, no screenshots.
        Data saved to database.

        Returns:
            Dictionary containing:
            - url, title, meta_description, canonical_url
            - h1, h2, h3, body_content
            - ctas, faqs, structured_data
            - navigation, internal_links, images
            - html_content (stored in DB)
            - status_code, load_time_ms, word_count
        """
        async with self._semaphore:  # Limit concurrent requests
            result = {
                "url": url,
                "status_code": 200,
                "load_time_ms": 0,
                "error": None,
                "html_content": None,  # Store in DB
            }

            try:
                start_time = datetime.now()
                timeout = timeout or self.timeout_ms

                if self.browser:
                    # Use Playwright: JS rendering + screenshots
                    pw_result = await self._crawl_with_playwright(url, timeout)
                    result.update(pw_result)
                else:
                    # Fallback: pure httpx (no JS, no screenshots)
                    response = await self.client.get(url, timeout=timeout/1000)
                    result["status_code"] = response.status_code
                    html = response.text
                    result.update(self._extract_page_data(BeautifulSoup(html, "lxml"), html))
                    result["html_content"] = html

                result["load_time_ms"] = int((datetime.now() - start_time).total_seconds() * 1000)

            except Exception as e:
                result["error"] = str(e)
                result["status_code"] = 0

            return result

    async def _crawl_with_playwright(self, url: str, timeout: int) -> Dict[str, Any]:
        """Crawl page using Playwright: JS rendering + screenshots"""
        result = {
            "status_code": 200,
            "error": None,
            "screenshot_path": None,
            "html_content": None,
        }

        try:
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent,
            )
            page = await context.new_page()

            # Navigate and wait for network to settle
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            result["status_code"] = response.status if response else 200

            # Wait for JS to render (lazy content, schemas injected by JS)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await page.wait_for_timeout(3000)

            # Take desktop screenshot (1920x1080)
            safe_name = self._sanitize_filename(url)
            screenshot_path = self.screenshots_dir / f"desktop_{safe_name}.png"
            await page.screenshot(path=str(screenshot_path), full_page=False)
            result["screenshot_path"] = str(screenshot_path)

            # Get fully rendered HTML (includes JS-injected JSON-LD etc.)
            html = await page.content()
            result["html_content"] = html

            # Parse and extract all data from rendered HTML
            soup = BeautifulSoup(html, "lxml")
            result.update(self._extract_page_data(soup, html))

            await context.close()

        except Exception as e:
            result["error"] = str(e)
            result["status_code"] = 0
            # Fallback to httpx if Playwright fails
            try:
                response = await self.client.get(url, timeout=30.0)
                html = response.text
                result["status_code"] = response.status_code
                result["html_content"] = html
                result.update(self._extract_page_data(BeautifulSoup(html, "lxml"), html))
                result["error"] = None
            except Exception:
                pass

        return result

    async def _crawl_with_httpx(self, url: str, timeout: int) -> Dict[str, Any]:
        """Crawl page using httpx (fallback)"""
        result = {
            "status_code": 200,
            "error": None,
            "screenshot_path": None,
            "mobile_screenshot_path": None,
            "full_screenshot_path": None,
            "html_snapshot_path": None,
        }

        try:
            response = await self.client.get(url, timeout=timeout/1000)
            result["status_code"] = response.status_code
            html = response.text
            
            # Save HTML snapshot
            result["html_snapshot_path"] = self._save_html_snapshot(html, url)
            
            # Parse HTML
            soup = BeautifulSoup(html, "lxml")
            result.update(self._extract_page_data(soup, html))
            
        except Exception as e:
            result["error"] = str(e)
            result["status_code"] = 0
        
        return result

    def _extract_page_data(self, soup: BeautifulSoup, html: str) -> Dict[str, Any]:
        """Extract all relevant data from page HTML with enhanced GEO/AEO analysis"""
        data = {}

        # Title
        title_tag = soup.find("title")
        data["title"] = title_tag.get_text(strip=True) if title_tag else None

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        data["meta_description"] = meta_desc.get("content", "").strip() if meta_desc else None

        # Open Graph data for GEO
        og_title = soup.find("meta", attrs={"property": "og:title"})
        og_description = soup.find("meta", attrs={"property": "og:description"})
        og_image = soup.find("meta", attrs={"property": "og:image"})
        data["og_data"] = {
            "title": og_title.get("content", "") if og_title else "",
            "description": og_description.get("content", "") if og_description else "",
            "image": og_image.get("content", "") if og_image else "",
        }

        # Canonical URL
        canonical = soup.find("link", attrs={"rel": "canonical"})
        data["canonical_url"] = canonical.get("href") if canonical else None

        # Headings
        h1 = soup.find("h1")
        data["h1"] = h1.get_text(strip=True) if h1 else None

        h2s = soup.find_all("h2")
        data["h2"] = [h2.get_text(strip=True) for h2 in h2s if h2.get_text(strip=True)]

        h3s = soup.find_all("h3")
        data["h3"] = [h3.get_text(strip=True) for h3 in h3s if h3.get_text(strip=True)]

        # Body content (text only, cleaned)
        body = soup.find("body")
        if body:
            # Remove script and style tags
            for tag in body(["script", "style", "noscript"]):
                tag.decompose()
            data["body_content"] = body.get_text(separator="\n", strip=True)
        else:
            data["body_content"] = ""

        # Word count
        data["word_count"] = len(data.get("body_content", "").split())

        # CTAs (buttons and links with commercial intent)
        data["ctas"] = self._extract_ctas(soup)

        # FAQs - Enhanced extraction
        data["faqs"] = self._extract_faqs(soup)

        # Structured Data (JSON-LD) - Enhanced extraction
        data["structured_data"] = self._extract_structured_data(soup)

        # Navigation
        data["navigation"] = self._extract_navigation(soup)

        # Internal links
        data["internal_links"] = self._extract_internal_links(soup)

        # Images - Enhanced with dimensions
        data["images"] = self._extract_images(soup)

        # Videos
        data["videos"] = self._extract_videos(soup)

        # GEO/AEO signals - New
        data["geo_aeo_signals"] = self._extract_geo_aeo_signals(soup)

        # Speakable schema - New
        data["speakable"] = self._extract_speakable(soup)

        return data

    def _extract_ctas(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract CTA buttons and links"""
        ctas = []
        cta_keywords = ["buy", "shop", "purchase", "learn more", "explore", "get started", "order"]

        # Button elements
        for btn in soup.find_all(["button", "a"]):
            text = btn.get_text(strip=True).lower()
            if any(kw in text for kw in cta_keywords):
                ctas.append({
                    "text": btn.get_text(strip=True),
                    "href": btn.get("href", ""),
                    "type": "button" if btn.name == "button" else "link",
                })

        return ctas[:20]  # Limit to 20 CTAs

    def _extract_faqs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract FAQ items from page"""
        faqs = []

        # Look for FAQ schema
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get("@type") == "FAQPage":
                        for item in data.get("mainEntity", []):
                            if item.get("@type") == "Question":
                                faqs.append({
                                    "question": item.get("name", ""),
                                    "answer": item.get("acceptedAnswer", {}).get("text", ""),
                                    "source": "schema",
                                })
                    # Handle nested schema
                    if "@graph" in data:
                        for graph_item in data["@graph"]:
                            if graph_item.get("@type") == "FAQPage":
                                for item in graph_item.get("mainEntity", []):
                                    if item.get("@type") == "Question":
                                        faqs.append({
                                            "question": item.get("name", ""),
                                            "answer": item.get("acceptedAnswer", {}).get("text", ""),
                                            "source": "schema",
                                        })
            except (json.JSONDecodeError, AttributeError):
                continue

        # Look for FAQ sections in HTML
        faq_sections = soup.find_all(attrs={"class": lambda x: x and "faq" in x.lower()})
        for section in faq_sections[:10]:  # Limit processing
            questions = section.find_all(attrs={"class": lambda x: x and "question" in x.lower()})
            for q in questions[:5]:
                answer = q.find_next_sibling()
                if not answer:
                    answer = q.find(attrs={"class": lambda x: x and "answer" in x.lower()})
                faqs.append({
                    "question": q.get_text(strip=True),
                    "answer": answer.get_text(strip=True) if answer else "",
                    "source": "html",
                })

        return faqs[:20]  # Limit to 20 FAQs

    def _extract_structured_data(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract JSON-LD structured data"""
        structured_data = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                structured_data.append(data)
            except (json.JSONDecodeError, AttributeError):
                continue

        return structured_data

    def _extract_navigation(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract navigation structure"""
        navigation = {"main": [], "footer": []}

        # Main navigation
        nav = soup.find("nav")
        if nav:
            for link in nav.find_all("a", href=True):
                navigation["main"].append({
                    "text": link.get_text(strip=True),
                    "href": link.get("href", ""),
                })

        # Footer navigation
        footer = soup.find("footer")
        if footer:
            for link in footer.find_all("a", href=True):
                navigation["footer"].append({
                    "text": link.get_text(strip=True),
                    "href": link.get("href", ""),
                })

        return navigation

    def _extract_internal_links(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract all internal links"""
        links = []
        seen = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href and href not in seen and not href.startswith(("javascript:", "mailto:", "#")):
                seen.add(href)
                links.append({
                    "text": link.get_text(strip=True),
                    "href": href,
                })

        return links[:100]  # Limit to 100 links

    def _extract_images(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract image information"""
        images = []

        for img in soup.find_all("img")[:50]:  # Limit to 50 images
            images.append({
                "src": img.get("src", ""),
                "alt": img.get("alt", ""),
                "width": img.get("width", ""),
                "height": img.get("height", ""),
            })

        return images

    def _extract_videos(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract video information"""
        videos = []

        for video in soup.find_all("video")[:10]:
            videos.append({
                "src": video.get("src", ""),
                "poster": video.get("poster", ""),
                "autoplay": video.has_attr("autoplay"),
            })

        # Also check for iframe embeds (YouTube, etc.)
        for iframe in soup.find_all("iframe")[:10]:
            src = iframe.get("src", "")
            if any(platform in src for platform in ["youtube", "vimeo", "dailymotion"]):
                videos.append({
                    "src": src,
                    "type": "embed",
                })

        return videos

    def _extract_geo_aeo_signals(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract GEO/AEO (Generative Engine Optimization / Answer Engine Optimization) signals.
        These help content appear in AI-generated answers.
        """
        signals = []

        # Check for definition-style content (What is, How to, etc.)
        definition_patterns = ["what is", "how to", "how does", "why is", "when to", "where to"]
        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = heading.get_text(strip=True).lower()
            for pattern in definition_patterns:
                if text.startswith(pattern):
                    signals.append({
                        "type": "definition_heading",
                        "content": heading.get_text(strip=True),
                        "tag": heading.name,
                    })

        # Check for Q&A format content
        question_indicators = ["?", "질문", "답변", "FAQ"]
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if any(ind in text for ind in question_indicators):
                # Check if followed by answer
                next_sibling = p.find_next_sibling()
                if next_sibling and len(next_sibling.get_text(strip=True)) > 50:
                    signals.append({
                        "type": "qa_format",
                        "question": text[:100],
                        "answer_preview": next_sibling.get_text(strip=True)[:100],
                    })

        # Check for list-based content (good for featured snippets)
        for ul in soup.find_all("ul")[:5]:
            items = ul.find_all("li")
            if len(items) >= 3:
                signals.append({
                    "type": "list_content",
                    "item_count": len(items),
                    "context": ul.get_text(strip=True)[:100],
                })

        # Check for table content (structured data for AI)
        for table in soup.find_all("table")[:3]:
            rows = table.find_all("tr")
            if len(rows) >= 2:
                signals.append({
                    "type": "table_content",
                    "row_count": len(rows),
                    "has_header": table.find("th") is not None,
                })

        # Check for HowTo schema
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    schema_type = data.get("@type", "")
                    if schema_type in ["HowTo", "FAQPage", "QAPage", "Article"]:
                        signals.append({
                            "type": "structured_data",
                            "schema_type": schema_type,
                            "geo_optimized": True,
                        })
            except (json.JSONDecodeError, AttributeError):
                continue

        return signals

    def _extract_speakable(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract speakable content for voice search optimization.
        Based on Google's Speakable schema specification.
        """
        speakable = {
            "has_speakable_schema": False,
            "css_selectors": [],
            "speakable_content": [],
        }

        # Check for SpeakableSpecification schema
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get("@type") == "SpeakableSpecification":
                        speakable["has_speakable_schema"] = True
                        speakable["css_selectors"] = data.get("cssSelector", [])
            except (json.JSONDecodeError, AttributeError):
                continue

        # Extract potential speakable content (concise, definition-style paragraphs)
        for p in soup.find_all("p")[:20]:
            text = p.get_text(strip=True)
            # Good speakable content is 1-3 sentences, under 200 characters
            if 50 < len(text) < 200 and text.count(".") <= 3:
                # Check if it's definition-style
                if any(text.lower().startswith(w) for w in ["the ", "a ", "an ", "this ", "it "]):
                    speakable["speakable_content"].append({
                        "text": text,
                        "length": len(text),
                        "sentence_count": text.count(".") + 1,
                    })

        return speakable

    def _save_html_snapshot(self, html: str, url: str) -> str:
        """Save HTML snapshot to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._sanitize_filename(url)
        filename = f"{safe_name}_{timestamp}.html"
        filepath = self.snapshots_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        return str(filepath)

    def _sanitize_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        safe = url.replace("https://", "").replace("http://", "")
        safe = safe.replace("/", "_").replace("?", "_").replace("=", "_")
        safe = safe.replace("&", "_").replace("#", "_")
        # Limit length
        if len(safe) > 100:
            safe = safe[:100]
        return safe

    async def quick_crawl(self, url: str) -> Dict[str, Any]:
        """
        Quick crawl for URL discovery using httpx.
        """
        async with self._semaphore:
            result = {"url": url, "html": None, "links": [], "error": None, "status_code": 200}

            try:
                response = await self.client.get(url, timeout=15.0)
                result["status_code"] = response.status_code
                result["html"] = response.text

                # Extract links quickly
                soup = BeautifulSoup(result["html"], "lxml")
                for link in soup.find_all("a", href=True):
                    result["links"].append({
                        "text": link.get_text(strip=True),
                        "href": link.get("href", ""),
                    })

            except Exception as e:
                result["error"] = str(e)

            return result

    async def crawl_full_site(
        self,
        base_url: str,
        max_pages: int = 50,
        same_domain_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Crawl entire site starting from base_url.
        Discovers links recursively up to max_pages.
        
        Args:
            base_url: Starting URL
            max_pages: Maximum pages to crawl
            same_domain_only: Only crawl same domain
            
        Returns:
            List of crawl results
        """
        from urllib.parse import urlparse
        
        visited = set()
        to_visit = [base_url]
        results = []
        
        base_domain = urlparse(base_url).netloc
        
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
                
            visited.add(url)
            
            try:
                result = await self.crawl_page(url)
                results.append(result)
                
                # Extract new links to visit
                if result.get("internal_links"):
                    for link in result["internal_links"]:
                        href = link.get("href", "")
                        if href and not href.startswith(("javascript:", "mailto:", "#")):
                            # Convert relative to absolute
                            if href.startswith("/"):
                                parsed = urlparse(base_url)
                                href = f"{parsed.scheme}://{parsed.netloc}{href}"
                            
                            # Check if same domain
                            if same_domain_only:
                                link_domain = urlparse(href).netloc
                                if link_domain != base_domain:
                                    continue
                            
                            if href not in visited and href not in to_visit:
                                to_visit.append(href)
                                
            except Exception as e:
                results.append({"url": url, "error": str(e)})
        
        return results
