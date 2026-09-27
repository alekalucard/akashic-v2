#!/usr/bin/env python3
"""
Internet Research Fairy - Web Scouring for Knowledge
=====================================================

Searches the internet for information when needed by other fairies.
Uses DuckDuckGo (no API key needed) and can scrape web pages.

Capabilities:
- Web search via DuckDuckGo
- Page content extraction
- Documentation lookup
- Code example finding
- Knowledge card creation from web sources

Usage:
    Research topics requested by other fairies
    Store findings as SRM cards
    Report to thought circulation
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import urllib.request
import urllib.parse

# Configuration
AKASHIC_ROOT = Path("/home/ace/akashic")
SRM_INTAKE = AKASHIC_ROOT / "SRM_Intake" / datetime.now().strftime("%Y-%m-%d")
THOUGHT_CIRCULATION = AKASHIC_ROOT / "thought_circulation"
RESEARCH_CACHE = AKASHIC_ROOT / "research_cache"


class InternetResearchFairy:
    """
    Fairy that scours the internet for knowledge.

    Uses DuckDuckGo for searching (no API key needed).
    Extracts content from web pages.
    Creates SRM cards from findings.
    """

    name = "InternetResearchFairy"
    plane = "P40_Sensory"

    def __init__(self):
        self.ensure_dirs()
        self.research_log = []
        self.user_agent = "Mozilla/5.0 (compatible; AkashicResearchBot/1.0)"

    def ensure_dirs(self):
        """Ensure required directories exist."""
        for d in [SRM_INTAKE, THOUGHT_CIRCULATION, RESEARCH_CACHE]:
            d.mkdir(parents=True, exist_ok=True)

    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search DuckDuckGo and return results.

        Returns list of {title, url, snippet}
        """
        # DuckDuckGo HTML search (no API key needed)
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        try:
            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": self.user_agent}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

            # Parse results (simple regex parsing)
            results = []

            # Find result blocks
            result_pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
            snippet_pattern = r'<a[^>]+class="result__snippet"[^>]*>([^<]+)</a>'

            urls = re.findall(result_pattern, html)
            snippets = re.findall(snippet_pattern, html)

            for i, (url, title) in enumerate(urls[:max_results]):
                result = {
                    "title": title.strip(),
                    "url": url,
                    "snippet": snippets[i] if i < len(snippets) else ""
                }
                results.append(result)

            return results

        except Exception as e:
            return [{"error": str(e)}]

    def fetch_page_content(self, url: str, max_length: int = 10000) -> str:
        """
        Fetch and extract text content from a URL.

        Strips HTML tags and returns plain text.
        """
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.user_agent}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')

            # Strip HTML tags (simple approach)
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            return text[:max_length]

        except Exception as e:
            return f"Error fetching {url}: {e}"

    def research_topic(self, topic: str, depth: str = "normal") -> Dict:
        """
        Research a topic thoroughly.

        Args:
            topic: What to research
            depth: "quick" (just search), "normal" (search + top result), "deep" (search + multiple pages)

        Returns research results as a card-ready dict.
        """
        self.log(f"Researching: {topic} (depth={depth})")

        results = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "search_results": [],
            "content": [],
            "summary": ""
        }

        # Search
        search_results = self.search_duckduckgo(topic, max_results=5 if depth == "deep" else 3)
        results["search_results"] = search_results

        if depth == "quick":
            results["summary"] = f"Found {len(search_results)} results for '{topic}'"
            return results

        # Fetch content from top results
        pages_to_fetch = 1 if depth == "normal" else 3
        for i, sr in enumerate(search_results[:pages_to_fetch]):
            if "url" in sr and "error" not in sr:
                content = self.fetch_page_content(sr["url"])
                results["content"].append({
                    "url": sr["url"],
                    "title": sr.get("title", ""),
                    "content": content[:5000]  # Limit per page
                })
                time.sleep(1)  # Be polite

        # Create summary
        total_content = sum(len(c.get("content", "")) for c in results["content"])
        results["summary"] = f"Researched '{topic}': {len(search_results)} search results, {len(results['content'])} pages fetched, {total_content} chars of content"

        return results

    def create_knowledge_card(self, research: Dict, tags: List[str] = None) -> Dict:
        """
        Create an SRM card from research results.
        """
        card = {
            "id": f"research_{int(time.time()*1000)}",
            "ts": time.time(),
            "kind": "research.web",
            "helix": {
                "L": {
                    "concept": research["topic"],
                    "w": {
                        "who": "InternetResearchFairy",
                        "what": f"Web research on: {research['topic']}",
                        "when": research["timestamp"],
                        "where": "internet",
                        "why": "knowledge_acquisition",
                        "how": "web_search"
                    }
                },
                "R": {"concept": "research", "w": {}},
                "C": {"affect": "curious", "energy": 0.7, "coherence": 0.8}
            },
            "content": json.dumps(research, indent=2),
            "tags": tags or ["research", "web", research["topic"].split()[0].lower()],
            "ownership": "SYSTEM",
            "sources": [sr.get("url", "") for sr in research.get("search_results", []) if "url" in sr]
        }
        return card

    def save_to_srm(self, card: Dict):
        """Save a card to SRM intake."""
        card_file = SRM_INTAKE / f"{card['id']}.json"
        card_file.write_text(json.dumps(card, indent=2))
        self.log(f"Saved card: {card['id']}")

    def report_finding(self, finding: str, topic: str):
        """Report a finding to thought circulation."""
        thought = {
            "type": "research_finding",
            "from": self.name,
            "topic": topic,
            "finding": finding,
            "timestamp": datetime.now().isoformat()
        }
        thought_file = THOUGHT_CIRCULATION / f"research_{int(time.time()*1000)}.json"
        thought_file.write_text(json.dumps(thought, indent=2))

    def log(self, msg: str):
        """Log activity."""
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.research_log.append(entry)
        print(f"[InternetResearchFairy] {msg}")

    # =========================================================================
    # Specialized Research Functions
    # =========================================================================

    def research_wow_topic(self, topic: str) -> Dict:
        """Research a WoW-specific topic."""
        # Add WoW-specific search terms
        wow_query = f"WoW 3.3.5a {topic} AzerothCore Eluna"
        return self.research_topic(wow_query, depth="normal")

    def research_eluna_api(self, function_name: str) -> Dict:
        """Research a specific Eluna API function."""
        query = f"Eluna {function_name} API documentation example"
        return self.research_topic(query, depth="deep")

    def research_dbc_format(self, dbc_name: str) -> Dict:
        """Research a specific DBC file format."""
        query = f"WoW {dbc_name}.dbc format structure 3.3.5a"
        return self.research_topic(query, depth="normal")


# ============================================================================
# Standalone Execution / Testing
# ============================================================================

def main():
    """Test the Internet Research Fairy."""
    fairy = InternetResearchFairy()

    # Test search
    print("Testing DuckDuckGo search...")
    results = fairy.search_duckduckgo("AzerothCore Eluna Lua scripting", max_results=3)
    print(f"Found {len(results)} results:")
    for r in results:
        print(f"  - {r.get('title', 'No title')}: {r.get('url', 'No URL')}")

    print("\nTesting full research...")
    research = fairy.research_topic("WoW 3.3.5a custom class creation", depth="normal")
    print(f"Research summary: {research['summary']}")

    # Create and save card
    card = fairy.create_knowledge_card(research, tags=["wow", "custom_class", "development"])
    fairy.save_to_srm(card)
    print(f"\nSaved card: {card['id']}")

    # Report finding
    fairy.report_finding(
        "Found documentation on custom class creation for WoW 3.3.5a",
        "custom_class"
    )
    print("Reported finding to thought circulation")


if __name__ == "__main__":
    main()
