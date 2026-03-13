"""
Network Tools - Web search and HTTP requests
"""
import re
from typing import Annotated

from langchain_core.tools import tool


@tool
def search_web(query: Annotated[str, "Search query"]) -> str:
    """Search the web for information using DuckDuckGo"""
    try:
        # Use ddgs (new package name) with retries and timeout
        from ddgs import DDGS

        with DDGS(timeout=5) as ddgs:
            results = list(ddgs.text(query, max_results=5))

            if not results:
                return "No search results found"

            formatted_results = []
            for i, r in enumerate(results, 1):
                title = r.get('title', 'No title')
                href = r.get('href', 'No URL')
                body = r.get('body', 'No description')
                formatted_results.append(f"{i}. {title}\n   URL: {href}\n   {body}")

            return "\n\n".join(formatted_results)

    except Exception as e:
        return f"Search failed: {e}"


@tool
def fetch_url(url: Annotated[str, "Webpage URL"]) -> str:
    """Fetch content from a URL"""
    try:
        import httpx

        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

            html = response.text

            # Clean HTML
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()

            return text[:5000]

    except Exception as e:
        return f"Fetch failed: {e}"
