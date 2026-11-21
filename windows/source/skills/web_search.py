"""
Web Search Skill for Multi-AI Orchestrator.

Provides asynchronous web search capabilities using DuckDuckGo HTML/Lite endpoints
with structured result parsing and robust error handling.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from core.security_guard import SecurityGuard
from core.skill_manager import BaseSkill

try:
    import httpx  # type: ignore

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class WebSearchSkill(BaseSkill):
    """
    Skill for searching the web and retrieving structured links and snippets.
    
    Queries DuckDuckGo search engines, parses HTML responses, cleans snippets,
    and returns sanitized structured results.
    """

    name: str = "web_search"
    description: str = "Search the web for information"
    required_permissions: list[str] = ["web_search"]

    _USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
    )

    def __init__(self, security_guard: Optional[SecurityGuard] = None) -> None:
        """
        Initialize WebSearchSkill with reference to SecurityGuard.

        Args:
            security_guard: Optional SecurityGuard instance. If None, uses singleton.
        """
        self._security = security_guard if security_guard is not None else SecurityGuard()

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Tool parameter schema for web_search skill."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query keywords or phrase",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default: 5, max: 20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    def _clean_text(self, raw_html: str) -> str:
        """Strip HTML tags and unescape entities."""
        cleaned = re.sub(r"<[^>]+>", " ", raw_html)
        cleaned = html.unescape(cleaned)
        return " ".join(cleaned.split())

    def _extract_target_url(self, raw_url: str) -> str:
        """Extract actual destination URL from redirect wrapper if necessary."""
        if "uddg=" in raw_url:
            parsed = urllib.parse.urlparse(raw_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in query_params and query_params["uddg"]:
                return query_params["uddg"][0]
        if raw_url.startswith("//"):
            return "https:" + raw_url
        return raw_url

    def _parse_ddg_html(self, html_content: str, max_results: int) -> list[dict[str, str]]:
        """
        Extract titles, URLs, and snippets from DuckDuckGo HTML response.

        Args:
            html_content: Raw HTML text from DuckDuckGo.
            max_results: Limit of results to extract.

        Returns:
            list[dict[str, str]]: Parsed results with 'title', 'url', 'snippet'.
        """
        results: list[dict[str, str]] = []

        # Pattern 1: DDG HTML standard result blocks
        # Looking for <a class="result__a" href="...">title</a> and <a class="result__snippet" ...>snippet</a>
        result_blocks = re.findall(
            r'<div class="result\s+results_links[^"]*".*?</div>\s*</div>\s*</div>',
            html_content,
            re.DOTALL,
        )

        for block in result_blocks:
            title_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)

            if title_match:
                raw_url = title_match.group(1)
                raw_title = title_match.group(2)
                snippet = snippet_match.group(1) if snippet_match else ""

                url = self._extract_target_url(raw_url)
                title = self._clean_text(raw_title)
                cleaned_snippet = self._clean_text(snippet)

                if url and title:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": cleaned_snippet,
                    })

            if len(results) >= max_results:
                break

        # Pattern 2: DDG Lite table format fallback
        if not results:
            rows = re.findall(
                r'<tr>.*?<a class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?</tr>(?:\s*<tr>.*?<td class="result-snippet"[^>]*>(.*?)</td>.*?</tr>)?',
                html_content,
                re.DOTALL,
            )
            for raw_url, raw_title, snippet in rows:
                url = self._extract_target_url(raw_url)
                title = self._clean_text(raw_title)
                cleaned_snippet = self._clean_text(snippet) if snippet else ""

                if url and title:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": cleaned_snippet,
                    })
                if len(results) >= max_results:
                    break

        # Pattern 3: Generic link and paragraph fallback
        if not results:
            matches = re.findall(
                r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>',
                html_content,
                re.DOTALL,
            )
            for raw_url, raw_title in matches:
                url = self._extract_target_url(raw_url)
                title = self._clean_text(raw_title)
                if url.startswith("http") and title:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": "",
                    })
                if len(results) >= max_results:
                    break

        return results[:max_results]

    async def _fetch_url_async(self, url: str, data: Optional[dict[str, str]] = None) -> str:
        """Fetch URL content asynchronously using httpx or urllib."""
        headers = {
            "User-Agent": self._USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        if HAS_HTTPX:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                if data:
                    resp = await client.post(url, data=data, headers=headers)
                else:
                    resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text

        # Fallback to urllib
        def _sync_fetch() -> str:
            import urllib.request

            req_data = urllib.parse.urlencode(data).encode("utf-8") if data else None
            req = urllib.request.Request(url, data=req_data, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode("utf-8", errors="replace")

        return await asyncio.to_thread(_sync_fetch)

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute web search query.

        Args:
            params: Dictionary containing:
                - 'query': Search query string (required)
                - 'num_results': Number of results (optional, default 5, max 20)

        Returns:
            dict[str, Any]: {'results': [{'title': str, 'url': str, 'snippet': str}]}
        """
        allowed, reason = self._security.check_permission("web_search")
        if not allowed:
            raise PermissionError(f"Security check failed: {reason}")

        query = params.get("query")
        if not query or not isinstance(query, str) or not query.strip():
            raise ValueError("Parameter 'query' is required and must be a non-empty string.")

        query = query.strip()
        num_results = max(1, min(int(params.get("num_results", 5)), 20))

        # Attempt 1: DuckDuckGo HTML endpoint
        results: list[dict[str, str]] = []
        try:
            html_text = await self._fetch_url_async(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": ""},
            )
            results = self._parse_ddg_html(html_text, num_results)
        except Exception as e:
            logger.warning("DuckDuckGo HTML search attempt failed: %s", e)

        # Attempt 2: DuckDuckGo Lite endpoint fallback
        if not results:
            try:
                lite_html = await self._fetch_url_async(
                    f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
                )
                results = self._parse_ddg_html(lite_html, num_results)
            except Exception as e:
                logger.warning("DuckDuckGo Lite search attempt failed: %s", e)

        # Attempt 3: Instant Answer API fallback
        if not results:
            try:
                import json

                api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
                api_resp = await self._fetch_url_async(api_url)
                data = json.loads(api_resp)

                # Heading / Abstract
                if data.get("AbstractText") and data.get("AbstractURL"):
                    results.append({
                        "title": data.get("Heading", query),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("AbstractText", ""),
                    })

                # RelatedTopics
                for topic in data.get("RelatedTopics", []):
                    if "Text" in topic and "FirstURL" in topic:
                        results.append({
                            "title": topic.get("Text", "")[:80],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                        })
                    if len(results) >= num_results:
                        break
            except Exception as e:
                logger.warning("DuckDuckGo Instant Answer API search failed: %s", e)

        return {
            "results": results[:num_results],
        }
