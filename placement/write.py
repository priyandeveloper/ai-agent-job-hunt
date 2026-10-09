"""One chat call. Drafts a cold email from lines that are already in the resume."""

from openai import OpenAI

from placement.scrape import Posting
from placement.settings import Settings

SYSTEM = """You draft a cold email a student can send the same day.

Rules:
- Use only facts that appear in the resume. Do not invent employers, metrics, tools, or years.
- Start with a subject line, then the email. Keep the body under 150 words.
- Name one project from the resume that matches the role.
- Do not say the student has already applied.
"""


def draft_selected(resume: str, posting: Posting, want: str, settings: Settings, match: str) -> str:
    """One chat call. Only this job is in the prompt, not the rest of the hunt."""
    client = OpenAI(
        api_key=settings.futurex_api_key,
        base_url=settings.futurex_base_url,
    )
    looking = want.strip() or "a role that fits this resume"
    user = (
        f"What the student wants: {looking}\n"
        f"Match: {match}\n"
        f"Role: {posting.title}\n"
        f"Apply link: {posting.url}\n\n"
        f"Job description:\n{posting.text[:3500]}\n\n"
        f"Resume:\n{resume[:2500]}"
    )
    response = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    text = response.choices[0].message.content
    if not text:
        raise SystemExit("The chat model returned an empty draft.")
    return text.strip()
