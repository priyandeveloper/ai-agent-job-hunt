"""Turn a job URL into text. Firecrawl does the fetching."""

from dataclasses import dataclass

from firecrawl import Firecrawl

from placement.settings import Settings

# Jev reads the posting as state. A full career site is larger than we need.
MAX_CHARS = 12_000


@dataclass(frozen=True)
class Posting:
    source: str
    title: str
    text: str


def _field(obj: object, name: str, default: str = "") -> str:
    if isinstance(obj, dict):
        value = obj.get(name, default)
    else:
        value = getattr(obj, name, default)
    return value if isinstance(value, str) else default


def scrape_url(url: str, settings: Settings) -> Posting:
    """Fetch one page and keep the main text."""
    client = Firecrawl(api_key=settings.firecrawl_api_key)
    doc = client.scrape(url, formats=["markdown"], only_main_content=True)

    text = _field(doc, "markdown").strip()
    if not text:
        raise SystemExit(f"Firecrawl returned no markdown for {url}")

    metadata = doc.get("metadata") if isinstance(doc, dict) else getattr(doc, "metadata", None)
    title = _field(metadata, "title") or _field(metadata, "ogTitle") or url

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[truncated]"

    return Posting(source=url, title=title.strip() or url, text=text)
