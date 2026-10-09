"""Search the live web, keep real job descriptions, score each one.

scan is search plus a URL filter. score is a scrape, a JD check, then Jev.
"""

from dataclasses import dataclass

from placement.filters import company_name, looks_like_jd, looks_like_job_url, looks_like_listing_title
from placement.gate import TOP_N
from placement.match import rank_listings, rank_scored, signals
from placement.profile import Profile, profile_resume
from placement.score import Fit, score_fit
from placement.scrape import FREE_SCRAPE_PER_MINUTE, JobHit, Posting, scrape_url, search_jobs
from placement.settings import Settings
from placement.spend import Spend

SEARCH_LIMIT = 25


@dataclass
class ScoredJob:
    posting: Posting
    fit: Fit


def collect_hits(resume: str, want: str, query: str, settings: Settings) -> list[JobHit]:
    """Firecrawl search plus a URL filter. No model."""
    try:
        hits = search_jobs(query, settings, limit=SEARCH_LIMIT)
    except SystemExit as exc:
        print(exc)
        hits = []
    kept = [hit for hit in hits if looks_like_job_url(hit.url)]
    words = signals(resume + "\n" + want)
    return rank_listings(kept, words, limit=SEARCH_LIMIT)


def search_hits(resume: str, want: str, settings: Settings) -> tuple[Profile, list[JobHit]]:
    profile = profile_resume(resume, settings, want)
    return profile, collect_hits(resume, want, profile.query, settings)


def scrape_top(
    hits: list[JobHit],
    settings: Settings,
    spend: Spend,
    limit: int = TOP_N,
) -> list[Posting]:
    """Open pages one at a time. Free Firecrawl allows 10 scrapes a minute and 2 at once."""
    postings: list[Posting] = []
    for hit in hits:
        if len(postings) >= limit or spend.firecrawl_scrapes >= FREE_SCRAPE_PER_MINUTE:
            break
        spend.add_scrape()
        try:
            posting = scrape_url(hit.url, settings)
        except (SystemExit, Exception) as exc:
            reason = " ".join(str(exc).split())
            if "429" in reason:
                print("Firecrawl free plan: 10 scrapes per minute. Stopping.")
                break
            if len(reason) > 180:
                reason = reason[:180].rstrip() + "..."
            print(f"  skip {hit.url}\n    {reason}")
            continue
        if looks_like_listing_title(posting.title) or not looks_like_job_url(posting.url):
            print(f"  skip {hit.url}\n    portal search page, not one company job")
            continue
        if not looks_like_jd(posting.text):
            print(f"  skip {hit.url}\n    page is not a job description")
            continue
        postings.append(posting)
    return postings


def evaluate(
    resume: str,
    want: str,
    settings: Settings,
    postings: list[Posting],
    spend: Spend,
) -> list[ScoredJob]:
    scored: list[ScoredJob] = []
    for posting in postings[:TOP_N]:
        fit = score_fit(resume, posting, settings, want=want)
        spend.add_jev(fit.input_tokens)
        scored.append(ScoredJob(posting, fit))
        print(f"  scored {posting.title} -> {fit.decision}")
    return rank_scored(scored, limit=TOP_N)


def print_shortlist(jobs: list[ScoredJob]) -> None:
    print()
    if not jobs:
        print("No job descriptions survived the search. Try a more specific --want.")
        return
    print(f"{len(jobs)} jobs")
    print(f"{'#':>2}  {'skill':>5}  {'level':>5}  {'fit':<8}  {'jev':<8}  {'bond':>5}  {'exp':>5}  role")
    for index, job in enumerate(jobs, start=1):
        fit = job.fit
        title = " ".join(job.posting.title.split())
        print(
            f"{index:>2}  {fit.skill_score:>5.2f}  {fit.skill_index:>2}/4   "
            f"{fit.decision:<8}  {fit.jev_verdict:<8}  {fit.bond:>4.0%}  {fit.above_fresher:>4.0%}  {title}"
        )
        print(f"    {company_name(job.posting.url)}  {job.posting.url}")


def hunt(resume: str, settings: Settings, spend: Spend, want: str = "") -> list[ScoredJob]:
    """The same two steps as the agent, written in order so you can read them."""
    profile, hits = search_hits(resume, want, settings)
    spend.add_jev(profile.input_tokens)
    print(f"Search: {profile.query}")
    print(f"{len(hits)} recruiter links")
    postings = scrape_top(hits, settings, spend)
    print(f"{len(postings)} job descriptions")
    scored = evaluate(resume, want, settings, postings, spend)
    print_shortlist(scored)
    return scored
