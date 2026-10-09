"""Strands agent. Two tools, then it stops.

scan_jobs searches and filters URLs. It spends no chat tokens on the resume.
score_jobs scrapes the survivors and asks Jev to score them.
"""

from strands import Agent, tool
from strands.models.openai import OpenAIModel

from placement.hunt import ScoredJob, collect_hits, evaluate, print_shortlist, scrape_top
from placement.profile import profile_resume
from placement.scrape import JobHit
from placement.settings import Settings
from placement.spend import Spend

SYSTEM = """
You are a placement assistant for one student.
Call scan_jobs once. Then call score_jobs once. Then stop.
Do not search again. Do not invent jobs. Do not write a cold email.
When you stop, list each scored job as: title, apply link, fit.
The tools already printed the full cards. Your list is a short recap.
""".strip()

_SESSION: dict = {}


@tool
def scan_jobs() -> str:
    """Search the web for recruiter job links that match the loaded resume and what the student wants. Returns titles and apply links. Does not score them."""
    session = _SESSION
    if session.get("hits") is not None:
        hits: list[JobHit] = session["hits"]
        return f"Already scanned {len(hits)} links. Call score_jobs."
    query = session["query"]
    hits = collect_hits(session["resume"], session["want"], query, session["settings"])
    session["hits"] = hits
    if not hits:
        return f"Search '{query}' returned no recruiter links. Stop."
    lines = [f"Search: {query}", f"{len(hits)} links. Call score_jobs once."]
    lines.extend(f"- {hit.title} | {hit.url}" for hit in hits)
    return "\n".join(lines)


@tool
def score_jobs() -> str:
    """Scrape the links from scan_jobs, keep real job descriptions, and score them with Jev. Returns the shortlist."""
    session = _SESSION
    hits = session.get("hits")
    if not hits:
        return "No links yet. Call scan_jobs first."
    if session.get("scored") is not None:
        return "Already scored. Stop and recap the shortlist."
    target_limit = session.get("limit", 20)
    postings = scrape_top(hits, session["settings"], session["spend"], limit=target_limit)
    scored = evaluate(
        session["resume"],
        session["want"],
        session["settings"],
        postings,
        session["spend"],
        limit=target_limit,
    )
    session["scored"] = scored
    if not scored:
        return "No job descriptions to score. Stop."
    lines = []
    for job in scored:
        lines.append(f"- {job.posting.title} | {job.posting.url} | {job.fit.decision}")
    return "\n".join(lines)


def _chat_tokens(metrics: object) -> tuple[int, int]:
    usage = getattr(metrics, "accumulated_usage", None) or {}
    if not isinstance(usage, dict):
        usage = {}
    chat_in = usage.get("inputTokens", usage.get("input_tokens", 0))
    chat_out = usage.get("outputTokens", usage.get("output_tokens", 0))
    return int(chat_in or 0), int(chat_out or 0)


def run_agent(resume: str, settings: Settings, want: str = "", limit: int = 20) -> tuple[list[ScoredJob], Spend, int, int]:
    spend = Spend(chat_model=settings.chat_model, jev_model=settings.jev_model)
    looking_for = want.strip()
    profile = profile_resume(resume, settings, looking_for)
    spend.add_jev(profile.input_tokens, getattr(profile, "output_tokens", 0))
    print(f"Search: {profile.query}")
    _SESSION.clear()
    _SESSION.update(
        resume=resume,
        want=looking_for,
        query=profile.query,
        settings=settings,
        spend=spend,
        limit=limit,
        hits=None,
        scored=None,
    )

    model = OpenAIModel(
        client_args={
            "api_key": settings.futurex_api_key,
            "base_url": settings.futurex_base_url,
        },
        model_id=settings.chat_model,
        params={"temperature": 0},
    )
    agent = Agent(
        model=model,
        tools=[scan_jobs, score_jobs],
        system_prompt=SYSTEM,
        callback_handler=None,
    )
    prompt = "Hunt jobs for the loaded resume."
    if want.strip():
        prompt += f" They are looking for: {want.strip()[:300]}"
    result = agent(prompt)

    print()
    print(str(result).strip())
    scored = _SESSION.get("scored") or []
    print_shortlist(scored)

    # Ingest real response telemetry, cycle traces, and token usage from AgentResult metrics
    spend.record_agent_metrics(result.metrics)
    chat_in, chat_out = _chat_tokens(result.metrics)
    print()
    print(spend.report(chat_in, chat_out))
    return scored, spend, chat_in, chat_out
