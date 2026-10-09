"""The two steps the agent's tools call, written in order.

scan is search plus a URL filter. score is cache, scrape, JD check, then Jev.
match.py is merged here: ranking sits next to the pipeline that uses it.
"""

import os
import time
from dataclasses import dataclass

from placement.cache import cache_fit, cache_posting, cached_fit, cached_posting, fit_key
from placement.filters import (
    company_name,
    dedup_key,
    looks_like_jd,
    looks_like_job_url,
    looks_like_listing_title,
    posting_closed,
)
from placement.score import TOP_N, Fit, score_fit
from placement.scrape import FREE_SCRAPE_PER_MINUTE, JobHit, Posting, scrape_url, search_jobs
from placement.settings import Settings
from placement.spend import Spend

# ---------------------------------------------------------------------------
# Ranking (merged from match.py)
# ---------------------------------------------------------------------------

SKILLS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "sql",
    "fastapi",
    "django",
    "node",
    "kotlin",
    "android",
    "machine learning",
    "golang",
    "go",
)

ROLE_WORDS = ("engineer", "developer", "intern", "sde", "software")
ORDER = {"apply": 0, "stretch": 1, "ask": 2, "skip": 3}


def signals(resume: str) -> list[str]:
    text = resume.lower()
    found = [skill for skill in SKILLS if skill in text]
    if any(word in text for word in ("intern", "student", "b.tech", "final year", "final-year")):
        found.append("intern")
    return found


ATS_DOMAINS = ("greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com", "bamboohr.com")


def rank_listings(listings: list, words: list[str], limit: int = 15) -> list:
    """Best title matches and direct ATS links first."""
    scored: list[tuple[int, object]] = []
    rest: list[object] = []
    for listing in listings:
        title = getattr(listing, "title", "").lower()
        url = getattr(listing, "url", "").lower()
        score = sum(2 for word in words if word in title)
        if any(role in title for role in ROLE_WORDS):
            score += 1
        # Direct ATS domains are significantly higher probability real job descriptions
        if any(ats in url for ats in ATS_DOMAINS):
            score += 3
        if score:
            scored.append((score, listing))
        else:
            rest.append(listing)
    scored.sort(key=lambda item: item[0], reverse=True)
    ordered = [listing for _, listing in scored] + rest
    return ordered[:limit]


def rank_scored(jobs: list, limit: int = 3) -> list:
    ranked = sorted(
        jobs,
        key=lambda job: (
            ORDER.get(job.fit.decision, 9),
            -job.fit.skill_index,
            job.fit.bond,
        ),
    )
    return ranked[:limit]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

SEARCH_LIMIT = 60
SCRAPE_CAP = int(os.getenv("FIRECRAWL_SCRAPE_LIMIT", "30").strip() or "30")


@dataclass
class ScoredJob:
    posting: Posting
    fit: Fit


def collect_hits(resume: str, want: str, query: str, settings: Settings) -> list[JobHit]:
    """Firecrawl search, URL filter, dedup. No model."""
    try:
        hits = search_jobs(query, settings, limit=SEARCH_LIMIT)
    except SystemExit as exc:
        print(exc)
        hits = []
    seen: set[str] = set()
    kept: list[JobHit] = []
    for hit in hits:
        if not looks_like_job_url(hit.url):
            continue
        # Pre-screen obvious aggregator listing headings without scraping
        if looks_like_listing_title(hit.title):
            continue
        # Pre-screen closed listings from snippet or title
        snippet = getattr(hit, "snippet", "") or ""
        if posting_closed(hit.title) or (snippet and posting_closed(snippet)):
            continue
        key = dedup_key(hit.url, hit.title)
        if key in seen:
            continue
        seen.add(key)
        kept.append(hit)
    words = signals(resume + "\n" + want)
    return rank_listings(kept, words, limit=SEARCH_LIMIT)


def scrape_top(
    hits: list[JobHit],
    settings: Settings,
    spend: Spend,
    limit: int = TOP_N,
) -> list[Posting]:
    """Open pages one at a time. Supports up to `limit` jobs (10 to 30)."""
    postings: list[Posting] = []
    for hit in hits:
        if len(postings) >= limit:
            break
        # Guard: check cached posting first (free, 0 Firecrawl calls)
        posting = cached_posting(hit.url)
        if posting is not None:
            spend.add_cache_hit()
            print(f"  cached {hit.url}")
        else:
            # Check rate limit / scrape cap
            if spend.firecrawl_scrapes >= SCRAPE_CAP:
                print(f"Firecrawl scrape cap reached ({spend.firecrawl_scrapes} scrapes). Proceeding to score.")
                break
            # Pre-screen before spending a precious scrape
            if looks_like_listing_title(hit.title) or not looks_like_job_url(hit.url):
                continue
            snippet = getattr(hit, "snippet", "") or ""
            if posting_closed(hit.title) or (snippet and posting_closed(snippet)):
                print(f"  skip {hit.url}\n    pre-screened as closed")
                continue

            spend.add_scrape()
            try:
                posting = scrape_url(hit.url, settings)
                time.sleep(0.35)  # Polite pacing delay to prevent rate limit bursts
            except (SystemExit, Exception) as exc:
                reason = " ".join(str(exc).split())
                if "429" in reason:
                    print(f"Firecrawl rate limit (429). Proceeding with {len(postings)} collected postings.")
                    break
                if len(reason) > 180:
                    reason = reason[:180].rstrip() + "..."
                print(f"  skip {hit.url}\n    {reason}")
                continue

        if looks_like_listing_title(posting.title) or not looks_like_job_url(posting.url):
            print(f"  skip {hit.url}\n    portal search page, not one company job")
            continue
        if posting_closed(posting.text):
            print(f"  skip {hit.url}\n    posting is closed")
            continue
        if not looks_like_jd(posting.text):
            print(f"  skip {hit.url}\n    page is not a job description")
            continue
        cache_posting(posting)
        postings.append(posting)
    return postings


def evaluate(
    resume: str,
    want: str,
    settings: Settings,
    postings: list[Posting],
    spend: Spend,
    limit: int = TOP_N,
) -> list[ScoredJob]:
    scored: list[ScoredJob] = []
    for posting in postings[:limit]:
        key = fit_key(posting.url, resume, want)
        fit = cached_fit(key)
        if fit is not None:
            spend.add_cache_hit()
            print(f"  cached {posting.title} -> {fit.decision}")
        else:
            fit = score_fit(resume, posting, settings, want=want)
            spend.add_jev(fit.input_tokens, getattr(fit, "output_tokens", 0))
            cache_fit(key, fit)
            print(f"  scored {posting.title} -> {fit.decision}")
        scored.append(ScoredJob(posting, fit))
    return rank_scored(scored, limit=limit)


def print_shortlist(jobs: list[ScoredJob]) -> None:
    print()
    if not jobs:
        print("No job descriptions survived the search. Try a more specific --want.")
        return
    print(f"{len(jobs)} jobs")
    print(f"{'#':>2}  {'match':>5}  role")
    for index, job in enumerate(jobs, start=1):
        title = " ".join(job.posting.title.split())
        print(f"{index:>2}  {job.fit.skill_score / 4:>4.0%}  {title}")
        print(f"    {company_name(job.posting.url)}  {job.posting.url}")
