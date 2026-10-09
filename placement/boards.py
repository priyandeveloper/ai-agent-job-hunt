"""Greenhouse fallback. The hunt does not import this module.

Live search is Firecrawl in placement/scrape.py. These helpers stay so a
known board token can still be parsed without a search.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html import unescape
from urllib.request import Request, urlopen

# WORKSHOP: add one company. The token is the slug in its Greenhouse URL.
BOARDS = (
    {"company": "Groww", "token": "groww"},
    {"company": "Duolingo", "token": "duolingo"},
    {"company": "Figma", "token": "figma"},
    {"company": "GitLab", "token": "gitlab"},
)

TIMEOUT = 8


@dataclass(frozen=True)
class Listing:
    company: str
    title: str
    url: str
    token: str
    job_id: str


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_greenhouse(company: str, token: str, payload: dict) -> list[Listing]:
    found: list[Listing] = []
    for job in payload.get("jobs") or []:
        title = str(job.get("title") or "").strip()
        url = str(job.get("absolute_url") or "").strip()
        job_id = str(job.get("id") or "").strip()
        if title and url and job_id:
            found.append(Listing(company, title, url, token, job_id))
    return found


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "placement-fit-workshop"})
    with urlopen(request, timeout=TIMEOUT) as response:
        body = json.loads(response.read().decode())
    if not isinstance(body, dict):
        raise ValueError("expected a JSON object")
    return body


def _one_board(board: dict) -> list[Listing]:
    token = board["token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        payload = _get_json(url)
    except Exception as err:
        print(f"Skip {board['company']}: {err}")
        return []
    return parse_greenhouse(board["company"], token, payload)


def fetch_titles() -> list[Listing]:
    """Titles and apply links from every board, at the same time."""
    found: list[Listing] = []
    with ThreadPoolExecutor(max_workers=len(BOARDS)) as pool:
        for batch in pool.map(_one_board, BOARDS):
            found.extend(batch)
    return found


def fetch_jd(listing: Listing) -> str:
    """The recruiter's posted description, for one job."""
    url = (
        "https://boards-api.greenhouse.io/v1/boards/"
        f"{listing.token}/jobs/{listing.job_id}"
    )
    payload = _get_json(url)
    return html_to_text(str(payload.get("content") or ""))[:3500]
