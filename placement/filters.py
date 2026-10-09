"""Which links count as a recruiter posting, and what pay the text states. No network."""

import re
from urllib.parse import urlparse

# Search boards. A link on these hosts is a portal page, not the company's own job URL.
PORTAL_HOSTS = (
    "naukri.com",
    "internshala.com",
    "wellfound.com",
    "cutshort.io",
    "linkedin.com",
    "indeed.com",
    "foundit.in",
    "instahyre.com",
    "glassdoor.",
    "jobschat.ai",
    "huntboard.ai",
    "timesjobs.com",
    "shine.com",
    "freshersworld.com",
    "iimjobs.com",
    "hirist.com",
    "apna.co",
    "monsterindia.com",
    "simplyhired.com",
)

LISTING_WORDS = {
    "jobs",
    "job",
    "careers",
    "openings",
    "search",
    "bengaluru",
    "bangalore",
    "india",
    "remote",
    "hyderabad",
    "chennai",
    "pune",
    "mumbai",
    "delhi",
    "noida",
}

JD_MARKERS = (
    "responsibilit",
    "requirement",
    "qualif",
    "what you",
    "about the role",
    "about the job",
    "we are looking",
    "years of experience",
    "apply",
    "skills",
    "who you are",
    "what you'll do",
    "job description",
    "role overview",
    "key responsibilities",
    "candidate",
)

_PAY = re.compile(
    r"(?:stipend|salary|ctc|₹|rs\.?)[^.\n]{0,48}?\d[\d,]*(?:\s*(?:lpa|per month|/month|a month))?",
    re.IGNORECASE,
)


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def looks_like_job_url(url: str) -> bool:
    """True for one company's job page. False for a portal search such as Naukri's jobs-in page."""
    parsed = urlparse(url.split("?")[0])
    host = _host(url)
    parts = [part for part in parsed.path.lower().split("/") if part]
    path = "/" + "/".join(parts)

    if any(portal in host for portal in PORTAL_HOSTS):
        return False
    if host.endswith("greenhouse.io"):
        return len(parts) >= 3 and parts[-2] == "jobs" and parts[-1].isdigit()
    if host.endswith(("lever.co", "ashbyhq.com")):
        return len(parts) >= 2
    if not any(piece in path for piece in ("/jobs/", "/job/", "/careers/", "/apply")):
        return False
    if not parts or parts[-1] in {"jobs", "job", "careers", "openings", "search"}:
        return False
    listing_bits = sum(
        1 for part in parts if part in LISTING_WORDS or part.endswith("-developer") or part.endswith("-engineer")
    )
    if len(parts) <= 3 and listing_bits >= 2:
        return False
    return True


def looks_like_listing_title(title: str) -> bool:
    """True when the page title is a search results heading, not one role at one company."""
    sample = title.lower()
    return any(
        phrase in sample
        for phrase in ("jobs in", "job vacancies", "openings", "vacancies in", "job search")
    )


def looks_like_jd(text: str) -> bool:
    """True when the page text reads like a job description."""
    sample = text.lower()
    return len(text) >= 250 and any(marker in sample for marker in JD_MARKERS)


def company_name(url: str) -> str:
    """Best-effort employer from an apply link. ATS hosts hide it in the path."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]
    if host.endswith(("greenhouse.io", "lever.co", "ashbyhq.com")) and parts:
        return parts[0]
    labels = host.split(".")
    if labels and labels[0] in {"jobs", "boards", "careers", "job-boards"} and len(labels) > 2:
        return labels[1]
    return labels[0] if labels else host


def pay_amount(text: str) -> str:
    """A stipend or salary phrase copied from the posting, if one is written there."""
    match = _PAY.search(text)
    if not match:
        return ""
    return " ".join(match.group(0).split())


# Closure banners a portal prints on a dead posting. Checking this before Jev
# means a filled job never costs a scoring call. (Idea from career-ops liveness.)
CLOSED_PHRASES = (
    "no longer available",
    "no longer accepting applications",
    "position has been filled",
    "role has been filled",
    "job has been filled",
    "this job has expired",
    "posting has expired",
    "this role is closed",
    "this position is no longer",
    "job not found",
    "applications are closed",
    "no longer open",
)


def posting_closed(text: str) -> bool:
    """True when the page says the job is gone. Zero tokens."""
    sample = text.lower().replace("’", "'").replace("‘", "'")
    return any(phrase in sample for phrase in CLOSED_PHRASES)


def dedup_key(url: str, title: str) -> str:
    """One key per job. The same role on Greenhouse and the company site dedups to one."""
    company = company_name(url)
    clean_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return f"{company}|{clean_title}"
