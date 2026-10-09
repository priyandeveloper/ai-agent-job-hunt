"""Firecrawl: search for job links, then open one page."""

from dataclasses import dataclass

from firecrawl import Firecrawl

from placement.settings import Settings

# Jev reads the posting as state. A full career site is larger than we need.
MAX_CHARS = 12_000

# Firecrawl free plan, per minute. Search and scrape are separate counters.
# https://docs.firecrawl.dev/rate-limits
FREE_SCRAPE_PER_MINUTE = 10
FREE_CONCURRENT_BROWSERS = 2


@dataclass(frozen=True)
class Posting:
    source: str
    title: str
    text: str

    @property
    def url(self) -> str:
        return self.source


@dataclass(frozen=True)
class JobHit:
    title: str
    url: str
    snippet: str


def _field(obj: object, name: str, default: str = "") -> str:
    if isinstance(obj, dict):
        value = obj.get(name, default)
    else:
        value = getattr(obj, name, default)
    return value if isinstance(value, str) else default


def _any(obj: object, name: str) -> object:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _hits(payload: object) -> list:
    web = _any(payload, "web")
    if web:
        return list(web)
    data = _any(payload, "data")
    if data is not None:
        nested = _any(data, "web")
        if nested:
            return list(nested)
    if isinstance(payload, list):
        return payload
    return []


def search_jobs(query: str, settings: Settings, limit: int = 5) -> list[JobHit]:
    """Search the web for job links. Does not open the pages."""
    client = Firecrawl(api_key=settings.firecrawl_api_key)
    payload = client.search(query, limit=limit)
    found: list[JobHit] = []
    for item in _hits(payload):
        url = _field(item, "url")
        if not url:
            continue
        found.append(
            JobHit(
                title=_field(item, "title") or url,
                url=url,
                snippet=_field(item, "description") or _field(item, "snippet"),
            )
        )
    if not found:
        raise SystemExit(f"Firecrawl search returned no links for: {query}")
    return found


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
